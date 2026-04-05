# Standard library
import logging
from typing import Any

# Local
from src.shared.settings import settings

try:
    from langgraph.checkpoint.mongodb import MongoDBSaver as _MongoDBSaver
except ImportError:
    _MongoDBSaver = None

logger = logging.getLogger(__name__)
_CHECKPOINTER: Any | None = None
_CHECKPOINTER_CM: Any | None = None


def build_checkpointer() -> Any | None:
    global _CHECKPOINTER, _CHECKPOINTER_CM

    if settings.checkpoint_backend.lower() != "mongodb":
        return None

    if not settings.mongodb_url:
        logger.warning("MongoDB checkpointing requested but mongodb_url is empty — running without checkpointer")
        return None

    if _MongoDBSaver is None:
        logger.info("langgraph-checkpoint-mongodb not installed — running without checkpointer")
        return None

    try:
        if _CHECKPOINTER is None:
            candidate = _MongoDBSaver.from_conn_string(
                settings.mongodb_url,
                db_name=settings.mongodb_database,
                checkpoint_collection_name=settings.mongodb_checkpoint_collection,
            )

            # Some versions return a saver directly, others return a context manager.
            if hasattr(candidate, "__enter__"):
                _CHECKPOINTER_CM = candidate
                _CHECKPOINTER = candidate.__enter__()
            else:
                _CHECKPOINTER = candidate

        return _CHECKPOINTER
    except Exception:
        logger.warning("MongoDBSaver init failed — running without checkpointer", exc_info=True)
        return None


def close_checkpointer_resources() -> None:
    global _CHECKPOINTER, _CHECKPOINTER_CM

    try:
        if _CHECKPOINTER_CM is not None and hasattr(_CHECKPOINTER_CM, "__exit__"):
            _CHECKPOINTER_CM.__exit__(None, None, None)
        elif _CHECKPOINTER is not None and hasattr(_CHECKPOINTER, "close"):
            _CHECKPOINTER.close()
    except Exception:
        logger.warning("Failed to close graph checkpointer resources", exc_info=True)
    finally:
        _CHECKPOINTER_CM = None
        _CHECKPOINTER = None


__all__ = [
    "build_checkpointer",
    "close_checkpointer_resources",
]
