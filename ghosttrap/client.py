"""Drop-in error reporter for ghosttrap.io.

Usage:
    import ghosttrap

    # with a token (recommended):
    ghosttrap.init("t_abc123def456")

    # or with a full URL:
    ghosttrap.init("https://ghosttrap.io/trap/owner/repo/")

Hooks into sys.excepthook (unhandled exceptions), Python logging
(logger.exception / logger.error with exc_info), and Celery task
failures (if Celery is installed). Django apps should add
ghosttrap.django.GhostTrapApp to INSTALLED_APPS and
ghosttrap.django.GhostTrapMiddleware to MIDDLEWARE. To report a
caught exception or a non-exception condition, call ghosttrap.trap().
"""

import json
import logging
import socket
import sys
import traceback
import urllib.request

GHOSTTRAP_SERVER = "https://ghosttrap.io"

_endpoint = None
_original_excepthook = None
_server_name = None
_send_user = False


def init(dsn, server=None, send_user=False):
    """Configure the reporter.

    Args:
        dsn: Either a token (e.g. "t_abc123") or a full URL
             (e.g. "https://ghosttrap.io/trap/owner/repo/")
        server: Base server URL. Only needed if dsn is a token and
                you're not using ghosttrap.io.
        send_user: If True, the Django integration attaches the
                authenticated user's id and username to reported errors.
                Default False — user data is PII and stays out of
                payloads unless you opt in.
    """
    global _endpoint, _original_excepthook, _server_name, _send_user
    if dsn.startswith("http://") or dsn.startswith("https://"):
        _endpoint = dsn.rstrip("/") + "/"
    else:
        base = (server or GHOSTTRAP_SERVER).rstrip("/")
        _endpoint = f"{base}/trap/{dsn}/"
    try:
        _server_name = socket.gethostname() or None
    except Exception:
        _server_name = None
    _send_user = bool(send_user)
    _original_excepthook = sys.excepthook
    sys.excepthook = _error_hook
    _install_logging_handler()
    _install_celery_hook()


def report(exc, user=None):
    """Report a caught exception. Kept for backward compatibility; prefer `trap`."""
    trap(exc, user=user)


def trap(exc_or_message, user=None):
    """Manually trap an event.

    Pass an exception instance to report a caught error (its type, message,
    and traceback are sent). Pass a string to report a synthetic event with
    the caller's current stack — labelled `TrappedEvent` so it's distinct
    from real exceptions.

    Args:
        exc_or_message: exception instance or string
        user: optional dict with user context (id, username). Only sent
              if init() was called with send_user=True.
    """
    if _endpoint is None:
        return
    if isinstance(exc_or_message, BaseException):
        exc = exc_or_message
        _post(_build_payload(type(exc), exc, exc.__traceback__, user=user))
    else:
        _post(_build_synthetic_payload(str(exc_or_message), user=user))


def _error_hook(exc_type, exc_value, exc_tb):
    _post(_build_payload(exc_type, exc_value, exc_tb))
    _original_excepthook(exc_type, exc_value, exc_tb)


def _install_logging_handler():
    handler = _GhostTrapLogHandler()
    handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(handler)


def _install_celery_hook():
    try:
        from celery.signals import task_failure
        task_failure.connect(_on_task_failure)
    except ImportError:
        pass


def _on_task_failure(sender, exception, traceback, **kwargs):
    report(exception)


class _GhostTrapLogHandler(logging.Handler):
    def emit(self, record):
        if record.exc_info and record.exc_info[1]:
            report(record.exc_info[1])


def _build_synthetic_payload(message, user=None):
    frames_obj = traceback.extract_stack()[:-2]  # drop trap() and this builder
    formatted = ["Traceback (most recent call last):\n"]
    formatted += traceback.format_list(frames_obj)
    formatted.append(f"TrappedEvent: {message}\n")
    payload = {
        "type": "TrappedEvent",
        "message": message,
        "traceback": formatted,
        "frames": [
            {"file": f.filename, "line": f.lineno, "function": f.name, "code": f.line}
            for f in frames_obj
        ],
    }
    if _server_name:
        payload["server_name"] = _server_name
    if user and _send_user:
        payload["user"] = user
    return payload


def _build_payload(exc_type, exc_value, exc_tb, user=None):
    frames = traceback.extract_tb(exc_tb) if exc_tb else []
    payload = {
        "type": exc_type.__name__,
        "message": str(exc_value),
        "traceback": traceback.format_exception(exc_type, exc_value, exc_tb) if exc_tb else [],
        "frames": [
            {
                "file": f.filename,
                "line": f.lineno,
                "function": f.name,
                "code": f.line,
            }
            for f in frames
        ],
    }
    if _server_name:
        payload["server_name"] = _server_name
    if user and _send_user:
        payload["user"] = user
    return payload


def _post(payload):
    try:
        req = urllib.request.Request(
            _endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass
