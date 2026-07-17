# ghosttrap-sdk

Error reporting for Python apps, built for AI agents. Part of [ghosttrap](https://github.com/alex-rowley/ghosttrap-cli).

## Install

```
pip install ghosttrap-sdk
```

## Use

```python
import ghosttrap
ghosttrap.init("t_your_token_here")
```

Get your token by running `ghosttrap setup` from [ghosttrap-cli](https://github.com/alex-rowley/ghosttrap-cli).

### Optional kwargs

```python
ghosttrap.init(
    "t_your_token_here",
    server="https://ghosttrap.io",  # override only if self-hosting
    send_user=False,                # see "User context" below
    trap_logs=False,                # see "Bare log errors" below
)
```

## What it hooks into

- **`sys.excepthook`** — unhandled exceptions
- **`threading.excepthook`** — unhandled exceptions in background threads (these never reach `sys.excepthook`)
- **Python logging** — `logger.exception()` and `logger.error(..., exc_info=True)`
- **Celery** — task failures via `celery.signals.task_failure` (auto-detected)

## Bare log errors (opt-in)

By default, only log records carrying an exception are reported. Pass `trap_logs=True` to also report `logger.error()` / `logger.critical()` calls with no exception — they arrive as type `LoggedError` / `LoggedCritical` with the log call site as the frame. Off by default deliberately: in a chatty codebase every error-level log line becomes an event, and error trackers that default this on are famous for the resulting floods. The server's 5-minute dedup window still applies either way.

## What it sends

Every report includes the exception type, message, traceback, frames (file/line/function/code), and the server's hostname (`socket.gethostname()`).

## Django

```python
INSTALLED_APPS = [
    ...
    "ghosttrap.django.GhostTrapApp",
]

MIDDLEWARE = [
    "ghosttrap.django.GhostTrapMiddleware",
    ...
]
```

## Browser / JavaScript errors

Errors in your users' browsers never reach the Python hooks. The Django integration ships a small relay so they land in the same stream. Two lines:

```python
# urls.py
path("ghosttrap/", include("ghosttrap.django.urls")),
```

```html
<!-- base template -->
<script src="{% static 'ghosttrap/ghosttrap.js' %}" defer></script>
```

The script hooks uncaught errors and unhandled promise rejections, drops known junk (opaque cross-origin `"Script error."`, browser-extension noise), deduplicates per page, and caps itself at 10 reports per page load. It posts to your own domain — the ghosttrap token never appears in page source — and the relay view forwards through the endpoint you configured with `init()`. No CORS setup, and ad blockers don't see a third-party request.

Browser events arrive with the JS error type (e.g. `TypeError`), the page URL in the traceback header, and the parsed JS stack as frames. Minified bundles produce minified frames — there's no source-map support. If you mount the relay somewhere other than `/ghosttrap/`, point the script at it with `data-endpoint="/your/path/js/"`.

## Manually trap an event

For errors you catch and handle but still want logged, or for non-exception conditions worth flagging:

```python
import ghosttrap

try:
    do_thing()
except ValueError as e:
    ghosttrap.trap(e)        # caught exception — sent with type, message, traceback
    fallback()

ghosttrap.trap("payment gateway returned 503")  # synthetic event labelled "TrappedEvent"
```

`trap()` accepts an exception instance or a string. Strings get the caller's stack attached and a `TrappedEvent` type so they're distinct from real exceptions in the CLI. Both go through the same 5-minute dedup window as the auto-hook.

## User context

Off by default. Pass `send_user=True` to `init()` and the Django middleware will attach the authenticated user's `id` and `username` to each report. Has no effect outside Django.

```python
ghosttrap.init("t_your_token_here", send_user=True)
```

## Zero dependencies

Pure Python stdlib. No transitive dependencies in your production image.
