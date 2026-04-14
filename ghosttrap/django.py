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
    """Catches unhandled view exceptions and reports them."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from ghosttrap.client import report
        report(exception)
        return None
