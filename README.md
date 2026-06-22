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
)
```

## What it hooks into

- **`sys.excepthook`** — unhandled exceptions
- **Python logging** — `logger.exception()` and `logger.error(..., exc_info=True)`
- **Celery** — task failures via `celery.signals.task_failure` (auto-detected)

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
