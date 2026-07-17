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

To capture browser-side JavaScript errors, include the relay
endpoint and serve the capture script from your base template:

    path("ghosttrap/", include("ghosttrap.django.urls")),

    <script src="{% static 'ghosttrap/ghosttrap.js' %}" defer></script>

The browser posts to your own domain, so the ghosttrap token never
appears in page source; the relay forwards through init()'s endpoint.
"""

import json
import logging
import re

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

# One stack line in either dialect:
#   Chrome/Edge:    "    at func (https://site/app.js:10:5)" or "    at https://site/app.js:10:5"
#   Firefox/Safari: "func@https://site/app.js:10:5" or "@https://site/app.js:10:5"
_STACK_LINE = re.compile(
    r"^\s*(?:at\s+(?:(?P<cfunc>.*?)\s+\()?|(?P<ffunc>[^@]*)@)"
    r"(?P<file>[^()\s]+?):(?P<line>\d+):\d+\)?\s*$"
)


def _parse_js_stack(stack):
    frames = []
    for raw in stack.splitlines():
        m = _STACK_LINE.match(raw)
        if not m:
            continue
        function = m.group("cfunc") or m.group("ffunc") or "?"
        frames.append({
            "file": m.group("file"),
            "line": int(m.group("line")),
            "function": function,
            "code": None,
        })
    # JS stacks are innermost-first; ghosttrap frames are innermost-last.
    frames.reverse()
    return frames


def _js_payload(data, user=None):
    name = str(data.get("name") or "Error")[:100]
    message = str(data.get("message") or "")[:2000]
    stack = str(data.get("stack") or "")[:8000]
    page = str(data.get("url") or "")[:500]
    kind = "unhandledrejection" if data.get("kind") == "unhandledrejection" else "error"

    # The capture script filters these too; re-check here since the endpoint is open.
    if not message and not stack:
        return None
    if message == "Script error." and not stack:
        return None
    if "-extension://" in stack or "-extension://" in message:
        return None

    header = f"JavaScript {kind} on {page}:\n" if page else f"JavaScript {kind}:\n"
    traceback_lines = [header]
    traceback_lines += [line + "\n" for line in stack.splitlines()]
    traceback_lines.append(f"{name}: {message}\n")

    payload = {
        "type": name,
        "message": message,
        "traceback": traceback_lines,
        "frames": _parse_js_stack(stack),
    }
    from ghosttrap import client
    if client._server_name:
        payload["server_name"] = client._server_name
    if user and client._send_user:
        payload["user"] = user
    return payload


@csrf_exempt
def js_report(request):
    """Same-origin relay for the browser capture script (static/ghosttrap/ghosttrap.js)."""
    from ghosttrap import client
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

    payload = _js_payload(data, user=_user_context(request))
    if payload is None:
        return JsonResponse({"ok": True, "dropped": True})
    if client._endpoint is None:
        return JsonResponse({"ok": True, "dropped": True})
    client._post(payload)
    return JsonResponse({"ok": True})
