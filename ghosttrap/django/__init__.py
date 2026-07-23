"""Django integration for ghosttrap.

Add to INSTALLED_APPS:

    INSTALLED_APPS = [
        ...
        "ghosttrap.django.GhostTrapApp",
    ]

This re-attaches the ghosttrap logging handler after Django's
dictConfig runs (which typically clobbers handlers added during
init()). Also provides the GhostTrapMiddleware for catching
unhandled view exceptions.

Browser-side JavaScript capture (the /ghosttrap/js/ relay) is disabled:
the endpoint was anonymous by design, and now that agents act on stream
events, unauthenticated attacker-controlled text is an injection channel.
It returns 410 until ingest has write-only tokens and reserved-type
protection. See the repo history (v0.4.6-v0.4.8) for the implementation.
"""

import logging

from django.apps import AppConfig
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


class GhostTrapApp(AppConfig):
    name = "ghosttrap.django"
    label = "ghosttrap_django"
    verbose_name = "Ghosttrap"

    def ready(self):
        from ghosttrap.client import _install_logging_handler
        _install_logging_handler()


class GhostTrapMiddleware:
    """Catches unhandled view exceptions and reports them."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from ghosttrap.client import report
        report(exception, user=_user_context(request))
        return None


def _user_context(request):
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return {
        "id": getattr(user, "pk", None),
        "username": getattr(user, "get_username", lambda: None)(),
    }


@csrf_exempt
def js_report(request):
    """Disabled browser-capture relay. Kept as a stub so existing
    include("ghosttrap.django.urls") lines don't break on upgrade —
    the route answers 410 and forwards nothing.
    """
    return JsonResponse({"error": "browser capture is disabled in this release"}, status=410)
