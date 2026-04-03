import json
import logging
import re
from typing import Any

from langchain_openai import ChatOpenAI

from src.retrieval.prompts import SUPERVISOR_PROMPT
from src.retrieval.state import RetrievalState
from src.shared.langfuse_config import get_langfuse_handler, trace_retrieval, update_observation
from src.shared.settings import settings

logger = logging.getLogger(__name__)

_LLM = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    request_timeout=60,
    api_key=settings.openai_api_key,
)

_memory_client: Any | None = None


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _load_mem0_context(user_id: str) -> str:
    """Best-effort mem0 retrieval. Returns empty context when unavailable."""
    if not settings.mem0_api_key or not user_id:
        return ""

    try:
        global _memory_client
        if _memory_client is None:
            from mem0 import MemoryClient  # type: ignore

            _memory_client = MemoryClient(api_key=settings.mem0_api_key)

        client = _memory_client
        memories = client.search(query="legal context preferences", user_id=user_id, limit=5)
        if not memories:
            return ""

        lines: list[str] = []
        for mem in memories:
            value = mem.get("memory") if isinstance(mem, dict) else str(mem)
            if value:
                lines.append(str(value))
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("mem0 lookup failed for user_id=%s: %s", user_id, exc)
        return ""


@trace_retrieval(name="supervisor_node")
async def supervisor_node(state: RetrievalState) -> dict[str, Any]:
    question = state.get("question", "")
    chat_history = state.get("chat_history", [])
    user_id = state.get("user_id", "")

    mem0_context = _load_mem0_context(user_id)

    handler = get_langfuse_handler()
    invoke_config = {"callbacks": [handler]} if handler else None

    prompt = SUPERVISOR_PROMPT.format(
        mem0_context=mem0_context,
        chat_history=chat_history,
        question=question,
    )

    response = await _LLM.ainvoke(prompt, config=invoke_config)
    parsed = _extract_json(response.content if hasattr(response, "content") else str(response))

    update_observation(
        "supervisor_node",
        {
            "intent": parsed.get("intent"),
            "strategy": parsed.get("strategy"),
            "jurisdiction": parsed.get("jurisdiction"),
        },
    )

    return {
        "intent": parsed.get("intent", "factual"),
        "jurisdiction": parsed.get("jurisdiction", "unknown"),
        "clause_types": parsed.get("clause_types", []),
        "entities": parsed.get("entities", []),
        "strategy": parsed.get("strategy", "hybrid"),
        "mem0_context": mem0_context,
    }
