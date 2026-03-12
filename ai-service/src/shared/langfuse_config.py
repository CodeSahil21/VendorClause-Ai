import logging

logger = logging.getLogger(__name__)

_observe = None

try:
    from .settings import settings

    if settings.langfuse_public_key and settings.langfuse_secret_key:
        import os
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host

        from langfuse.decorators import observe as _observe
        logger.info("✅ Langfuse connected")
    else:
        logger.info("⚠️  Langfuse keys not set, monitoring disabled")
except Exception as e:
    logger.warning(f"⚠️  Langfuse disabled: {str(e)}")


def trace_ingestion(name: str = "ingestion"):
    """Uses Langfuse @observe() if available, otherwise no-op"""
    if _observe:
        return _observe(name=name)
    def noop(func):
        return func
    return noop


def trace_query(name: str = "query"):
    """Uses Langfuse @observe() if available, otherwise no-op"""
    if _observe:
        return _observe(name=name)
    def noop(func):
        return func
    return noop
