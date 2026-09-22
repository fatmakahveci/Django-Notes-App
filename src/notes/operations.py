"""Small operational endpoints that do not expose application data."""

import logging

from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .models import Post

logger = logging.getLogger(__name__)


@never_cache
@require_safe
def health(request):
    # Checking the note table catches both unavailable databases and missing schema.
    try:
        Post.objects.exists()
    except DatabaseError:
        logger.warning("Health check could not read the note table.", exc_info=True)
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@never_cache
def csrf_failure(request, reason=""):
    # The framework logs the reason; keep tokens and diagnostic details off the page.
    return render(request, "errors/csrf_failure.html", status=403)
