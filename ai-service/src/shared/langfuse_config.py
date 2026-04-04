# Standard library
import importlib
import logging
import os
import sys
import types

# Local
from .settings import settings

logger = logging.getLogger(__name__)

_observe = None
_langfuse_context = None
_langfuse_enabled = False


def _ensure_langchain_v1_compat() -> None:
    """Patch legacy langchain module paths that langfuse v2 callback expects."""
    try:
        importlib.import_module("langchain.callbacks.base")
        importlib.import_module("langchain.schema.agent")
        importlib.import_module("langchain.schema.document")
        return
    except Exception:
        pass

    from langchain_core.agents import AgentAction, AgentFinish
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.documents import Document

    cb_pkg = sys.modules.setdefault("langchain.callbacks", types.ModuleType("langchain.callbacks"))
    cb_base = types.ModuleType("langchain.callbacks.base")
    cb_base.BaseCallbackHandler = BaseCallbackHandler
    cb_pkg.base = cb_base
    sys.modules["langchain.callbacks.base"] = cb_base

    sc_pkg = sys.modules.setdefault("langchain.schema", types.ModuleType("langchain.schema"))
    sc_agent = types.ModuleType("langchain.schema.agent")
    sc_agent.AgentAction = AgentAction
    sc_agent.AgentFinish = AgentFinish
    sc_pkg.agent = sc_agent
    sys.modules["langchain.schema.agent"] = sc_agent

    sc_doc = types.ModuleType("langchain.schema.document")
    sc_doc.Document = Document
    sc_pkg.document = sc_doc
    sys.modules["langchain.schema.document"] = sc_doc


# ── Bootstrap: set env vars so SDK auto-discovers credentials everywhere ──────
if settings.langfuse_public_key and settings.langfuse_secret_key:
    _base_url = settings.langfuse_base_url or settings.langfuse_host
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_BASE_URL"] = _base_url
    os.environ["LANGFUSE_HOST"] = _base_url

    try:
        from langfuse.decorators import langfuse_context as _langfuse_context
        from langfuse.decorators import observe as _observe
        _langfuse_enabled = True
        logger.info("Langfuse initialized (public_key=%s...)", settings.langfuse_public_key[:12])
    except ImportError:
        try:
            import langfuse.decorators as _d
            _observe = _d.observe
            _langfuse_context = _d.langfuse_context
            _langfuse_enabled = True
            logger.info("Langfuse legacy decorators initialized")
        except Exception as exc:
            logger.warning("Langfuse disabled: %s", exc)
else:
    logger.info("Langfuse keys not configured — monitoring disabled")


# ── Public helpers ─────────────────────────────────────────────────────────────

def get_langfuse_handler():
    """Create a LangChain CallbackHandler that reports to the current trace.

    MUST be called inside an active @observe scope (i.e. inside a function
    decorated with @trace_ingestion / @trace_query) so the handler is
    automatically nested under the correct parent span.

    Returns None if Langfuse is disabled — callers must handle that.
    """
    if not _langfuse_enabled:
        return None
    try:
        _ensure_langchain_v1_compat()
        try:
            CallbackHandler = importlib.import_module("langfuse.langchain").CallbackHandler
        except ImportError:
            CallbackHandler = importlib.import_module("langfuse.callback").CallbackHandler
        return CallbackHandler()
    except Exception as exc:
        if "Please install langchain" not in str(exc):
            logger.warning("Failed to create Langfuse handler: %s", exc)
        return None


def update_trace(metadata: dict) -> None:
    """Annotate the current active Langfuse trace with arbitrary metadata.

    Uses update_current_trace() (root-level) so metadata is always visible
    on the trace card in the Langfuse dashboard regardless of nesting depth.
    Safe to call anywhere — silently no-ops when Langfuse is off or when
    called outside an @observe scope.
    """
    if _langfuse_context is None:
        return
    try:
        _langfuse_context.update_current_trace(metadata=metadata)
    except Exception:
        # Outside an @observe scope — silently ignore
        pass


def update_observation(name: str, metadata: dict) -> None:
    """Annotate the current active Langfuse *span* (observation).

    Use this to label a specific stage within the trace with a name and
    metadata. Silently no-ops when Langfuse is off or outside @observe.
    """
    if _langfuse_context is None:
        return
    try:
        _langfuse_context.update_current_observation(name=name, metadata=metadata)
    except Exception:
        pass


def _noop(func):
    return func


def trace_ingestion(name: str = "ingestion"):
    """Decorator — creates a root Langfuse trace for the decorated function.

    Only decorate the single TOP-LEVEL entry point per pipeline run
    (process_document_job in the worker). Everything called from inside
    that function shares the same trace automatically via contextvars.
    """
    if _observe:
        return _observe(name=name)
    return _noop


def trace_retrieval(name: str = "retrieval"):
    """Same as trace_ingestion but for retrieval pipeline entry points."""
    if _observe:
        return _observe(name=name)
    return _noop


def trace_query(name: str = "query"):
    """Backward-compatible alias for older query pipeline naming."""
    return trace_retrieval(name=name)
