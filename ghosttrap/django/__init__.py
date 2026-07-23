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

Browser-side JavaScript capture is quarantined by design. The relay
(include ghosttrap.django.urls + static/ghosttrap/ghosttrap.js in the
base template) forwards browser errors to the server's /trapjs/ ingest,
which only stores them: they never enter the agent stream — no WebSocket
fanout, no cursor — because browser senders are anonymous and streams
carry messages agents act on. Retrieval is pull-only: `ghosttrap jslogs`.
"""

import json
import logging
import urllib.request

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


_MAX_JS_BODY = 32 * 1024


def _js_endpoint():
    """The quarantined ingest URL, derived from the configured trap endpoint."""
    from ghosttrap import client
    if client._endpoint is None:
        return None
    return client._endpoint.replace("/trap/", "/trapjs/")


def _forward(endpoint, payload):
    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


@csrf_exempt
def js_report(request):
    """Same-origin relay for the browser capture script. Forwards to the
    server's quarantined /trapjs/ ingest — stored, capped, deduped, but
    never streamed to agents. The browser is anonymous; its events don't
    get to speak, only to be looked at (`ghosttrap jslogs`).
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    if len(request.body) > _MAX_JS_BODY:
        return JsonResponse({"error": "too large"}, status=413)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "bad json"}, status=400)

    message = str(data.get("message") or "")
    stack = str(data.get("stack") or "")
    # The capture script filters these too; re-check here since the endpoint is open.
    if not message and not stack:
        return JsonResponse({"ok": True, "dropped": True})
    if message == "Script error." and not stack:
        return JsonResponse({"ok": True, "dropped": True})
    if "-extension://" in stack or "-extension://" in message:
        return JsonResponse({"ok": True, "dropped": True})

    endpoint = _js_endpoint()
    if endpoint is None:
        return JsonResponse({"ok": True, "dropped": True})

    _forward(endpoint, {
        "name": str(data.get("name") or "Error")[:100],
        "message": message[:2000],
        "stack": stack[:8000],
        "url": str(data.get("url") or "")[:500],
        "kind": str(data.get("kind") or "error")[:32],
    })
    return JsonResponse({"ok": True})
