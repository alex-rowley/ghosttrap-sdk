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
"""

import logging

from django.apps import AppConfig


class GhostTrapApp(AppConfig):
    name = "ghosttrap.django"
    label = "ghosttrap_django"
    verbose_name = "Ghosttrap"

    def ready(self):
        from ghosttrap.client import _install_logging_handler
        _install_logging_handler()


class GhostTrapMiddleware:
    """Catches unhandled view exceptions and reports them.

    Django's own control-flow exceptions are not errors: the framework
    converts Http404 -> 404, PermissionDenied -> 403 and
    SuspiciousOperation (incl. DisallowedHost) -> 400 after middleware
    sees them. Reporting those turns every bot probe of a login form or
    raw-IP request into a page, so they are ignored here."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from django.core.exceptions import PermissionDenied, SuspiciousOperation
        from django.http import Http404

        if isinstance(exception, (Http404, PermissionDenied, SuspiciousOperation)):
            return None
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
