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

Disabled for now. The relay shipped in 0.4.6–0.4.8 accepted anonymous posts by design (the browser can't hold a secret), and since ghosttrap streams now carry agent-to-agent messages that agents act on, an unauthenticated text channel into the stream is an injection risk we're not willing to carry. The `/ghosttrap/js/` route answers 410 and forwards nothing. It will return once ingest distinguishes write-only tokens and reserves message types.

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
