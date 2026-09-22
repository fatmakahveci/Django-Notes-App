from datetime import datetime, timezone as datetime_timezone
from math import ceil
from ipaddress import ip_address

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UsernameField
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.db.models import F
from django.core.exceptions import SuspiciousOperation
from django.shortcuts import render
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.deprecation import MiddlewareMixin

from .models import AuthAttempt


class TrustedProxyMiddleware(MiddlewareMixin):
    """Use the proxy's overwritten client IP only in the isolated production stack."""

    def process_request(self, request):
        if settings.TRUST_PROXY_HEADERS and "HTTP_X_REAL_IP" in request.META:
            try:
                request.META["REMOTE_ADDR"] = str(ip_address(request.META["HTTP_X_REAL_IP"]))
            except ValueError as error:
                raise SuspiciousOperation("Invalid proxy client address.") from error


class BoundedUploadHandler(FileUploadHandler):
    """Cap aggregate file bytes before memory or temporary-file handlers see them."""

    def __init__(self, request):
        super().__init__(request)
        self.received = 0
        self.exceeded = False

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > settings.NOTE_UPLOAD_MAX_BYTES:
            self.exceeded = True
            # Close open temporary files without draining the rest of the upload.
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None


class UploadLimitMiddleware(MiddlewareMixin):
    def process_request(self, request):
        try:
            content_length = int(request.META.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            content_length = 0  # Django's request parser handles invalid lengths.
        if content_length > settings.NOTE_REQUEST_MAX_BYTES:
            return self.too_large(request)
        if request.method == "POST" and request.content_type == "multipart/form-data":
            request.note_upload_limit = BoundedUploadHandler(request)
            request.upload_handlers.insert(0, request.note_upload_limit)
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(request, "note_upload_limit"):
            # StopUpload can leave earlier files in FILES. Reject the entire request
            # before CSRF or the view can act on a partially parsed submission.
            request.POST
            if request.note_upload_limit.exceeded:
                return self.too_large(request)
        return None

    @staticmethod
    def too_large(request):
        response = render(request, "413.html", status=413)
        response["Cache-Control"] = "no-store"
        return response


class AuthenticationThrottleMiddleware(MiddlewareMixin):
    """Limit login (including admin) and signup POSTs across all app workers."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != "POST":
            return None
        # Public and admin login share a URL name and therefore the same counters.
        name = request.resolver_match.url_name
        if name not in {"login", "signup"}:
            return None
        if name == "signup" and request.user.is_authenticated:
            return None
        rules = settings.AUTH_ATTEMPT_LIMITS[name]
        now = timezone.now()
        AuthAttempt.objects.filter(expires_at__lte=now).delete()
        for identity_type, limit, seconds in rules:
            if identity_type == "ip":
                # Forwarded headers are client-controlled unless a trusted proxy validates them.
                identity = request.META.get("REMOTE_ADDR", "unknown")
            else:
                user_model = get_user_model()
                username_field = user_model._meta.get_field(user_model.USERNAME_FIELD)
                # Match AuthenticationForm's bounded NFKC normalization, so
                # equivalent Unicode spellings cannot get separate counters.
                identity = UsernameField(max_length=username_field.max_length or 254).to_python(
                    request.POST.get("username", ""),
                ).casefold()
            # Align fixed windows across workers rather than starting one per request.
            window = int(now.timestamp()) // seconds
            expires_at = datetime.fromtimestamp((window + 1) * seconds, tz=datetime_timezone.utc)
            # Keyed hashes keep raw usernames and IP addresses out of stored counters.
            key = salted_hmac(
                "auth-attempt", f"{name}:{identity_type}:{identity}:{window}", algorithm="sha256",
            ).hexdigest()
            AuthAttempt.objects.get_or_create(key=key, defaults={"expires_at": expires_at})
            # Check and increment in one SQL update to avoid concurrent lost updates.
            allowed = AuthAttempt.objects.filter(key=key, attempts__lt=limit).update(attempts=F("attempts") + 1)
            if not allowed:
                retry_after = max(1, ceil((expires_at - now).total_seconds()))
                response = render(request, "errors/rate_limited.html", {"retry_after": retry_after}, status=429)
                response["Retry-After"] = str(retry_after)
                response["Cache-Control"] = "no-store"
                return response
        return None
