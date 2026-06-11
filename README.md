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

## User context

Off by default. Pass `send_user=True` to `init()` and the Django middleware will attach the authenticated user's `id` and `username` to each report. Has no effect outside Django.

```python
ghosttrap.init("t_your_token_here", send_user=True)
```

## Zero dependencies

Pure Python stdlib. No transitive dependencies in your production image.
