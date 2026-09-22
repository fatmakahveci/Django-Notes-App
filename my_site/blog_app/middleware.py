from datetime import datetime, timezone as datetime_timezone
from math import ceil

from django.conf import settings
from django.db.models import F
from django.shortcuts import render
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.deprecation import MiddlewareMixin

from .models import AuthAttempt


class AuthenticationThrottleMiddleware(MiddlewareMixin):
    """Limit login (including admin) and signup POSTs across all app workers."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != "POST":
            return None
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
                identity = request.META.get("REMOTE_ADDR", "unknown")
            else:
                identity = request.POST.get("username", "").strip().casefold()
            window = int(now.timestamp()) // seconds
            expires_at = datetime.fromtimestamp((window + 1) * seconds, tz=datetime_timezone.utc)
            key = salted_hmac(
                "auth-attempt", f"{name}:{identity_type}:{identity}:{window}", algorithm="sha256",
            ).hexdigest()
            AuthAttempt.objects.get_or_create(key=key, defaults={"expires_at": expires_at})
            allowed = AuthAttempt.objects.filter(key=key, attempts__lt=limit).update(attempts=F("attempts") + 1)
            if not allowed:
                retry_after = max(1, ceil((expires_at - now).total_seconds()))
                response = render(request, "rate_limited.html", {"retry_after": retry_after}, status=429)
                response["Retry-After"] = str(retry_after)
                response["Cache-Control"] = "no-store"
                return response
        return None
