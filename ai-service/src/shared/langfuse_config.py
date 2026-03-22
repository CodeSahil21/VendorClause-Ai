import logging
import os

logger = logging.getLogger(__name__)

_observe = None
_langfuse_enabled = False

try:
    from .settings import settings

    if settings.langfuse_public_key and settings.langfuse_secret_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host

        from langfuse.decorators import observe as _observe
        _langfuse_enabled = True
        logger.info("Langfuse connected")
    else:
        logger.info("Langfuse keys not configured, monitoring disabled")
except Exception as e:
    logger.warning(f"Langfuse disabled: {e}")


def get_langfuse_handler():
    """Returns a LangChain CallbackHandler for LLM token tracking, or None if Langfuse is not configured."""
    if not _langfuse_enabled:
        return None
    try:
        from langfuse.callback import CallbackHandler
        from .settings import settings
        return CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception as e:
        logger.warning(f"Failed to create Langfuse handler: {e}")
        return None


def _noop_decorator(func):
    return func


def trace_ingestion(name: str = "ingestion"):
    if _observe:
        return _observe(name=name)
    return _noop_decorator


def trace_query(name: str = "query"):
    if _observe:
        return _observe(name=name)
    return _noop_decorator
