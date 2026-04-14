# ghosttrap-sdk

Error reporting for Python apps, built for AI agents.

When your app breaks in production, ghosttrap captures the exception and streams it to Claude Code in real time. Claude reads the traceback, opens the file, and fixes the bug — no human reads the error.

## Quick start

```
pip install ghosttrap-sdk
```

```python
import ghosttrap
ghosttrap.init("t_your_token_here")
```

That's it. Unhandled exceptions, logged errors, and Celery task failures are all reported automatically.

Get your token by running [`ghosttrap setup`](https://github.com/arowley-predictive-power/ghosttrap-cli) in your project directory.

## What it hooks into

- **`sys.excepthook`** — unhandled exceptions that crash the process
- **Python logging** — any `logger.exception()` or `logger.error(..., exc_info=True)` call
- **Celery** — task failures via `celery.signals.task_failure` (auto-detected, no config needed)

## Django integration

Add to your settings:

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

`GhostTrapApp` re-attaches the logging handler after Django's logging setup. `GhostTrapMiddleware` catches unhandled view exceptions.

## Zero dependencies

The SDK is pure Python stdlib. No transitive dependencies, no version conflicts, no bloat in your production image.

## Links

- [ghosttrap-cli](https://github.com/arowley-predictive-power/ghosttrap-cli) — the developer-side listener that connects errors to Claude Code
- [ghosttrap.io](https://ghosttrap.io) — the server that routes errors from your app to your agent
