# Standard library
import json
import logging
import re
from typing import Any

# Local
from src.shared.settings import settings

try:
    from mem0 import MemoryClient as _Mem0MemoryClient
except ImportError:
    _Mem0MemoryClient = None

logger = logging.getLogger(__name__)
_MEM0_CLIENT: Any | None = None

_TRIPLE_EXTRACTION_PROMPT = """Extract legal facts from this answer as compact triples.

Rules:
- Each triple: "<subject> <predicate> <object>"
- subject: the legal entity or clause (e.g. "vendor", "PNWH2", "Section 3.1")
- predicate: the obligation or relationship (e.g. "must", "has right to", "is liable for")
- object: the specific fact, value, or condition (e.g. "30 days notice", "$1M coverage")
- Max 5 triples
- Only extract facts explicitly stated — no inference
- Output STRICT JSON array of strings only

Example output:
["vendor must provide 30 days written notice before termination",
 "PNWH2 has 60 days to dispute an invoice",
 "Section 3.1 auto-renews for 1-year periods"]

Answer: {answer}

Triples:"""


def _extract_triples(answer: str) -> list[str]:
    """Use a small LLM call to extract structured fact triples from the answer."""
    try:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,
            max_tokens=200,
            api_key=settings.openai_api_key,
        )
        prompt = _TRIPLE_EXTRACTION_PROMPT.format(answer=answer[:800])
        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON array
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        triples = json.loads(match.group(0))
        return [str(t).strip() for t in triples if isinstance(t, str) and t.strip()][:5]
    except Exception as exc:
        logger.warning("Triple extraction failed: %s", exc)
        return []


def get_mem0_client() -> Any | None:
    global _MEM0_CLIENT

    if _Mem0MemoryClient is None or not settings.mem0_api_key:
        return None

    if _MEM0_CLIENT is None:
        _MEM0_CLIENT = _Mem0MemoryClient(api_key=settings.mem0_api_key)

    return _MEM0_CLIENT


def load_mem0_context(user_id: str, query: str = "legal context preferences", limit: int = 5) -> str:
    if not user_id:
        return ""

    client = get_mem0_client()
    if client is None:
        return ""

    def _parse_memories(payload: Any) -> list[Any]:
        if isinstance(payload, dict):
            if isinstance(payload.get("results"), list):
                return payload["results"]
            if isinstance(payload.get("memories"), list):
                return payload["memories"]
            if isinstance(payload.get("data"), list):
                return payload["data"]
            return []
        if isinstance(payload, list):
            return payload
        return []

    search_attempts = [
        {"query": query, "user_id": user_id, "limit": limit, "filters": {"user_id": user_id}},
        {"query": query, "user_id": user_id, "limit": limit, "filters": {"user_id": {"$eq": user_id}}},
        {"query": query, "user_id": user_id, "limit": limit, "filter": {"user_id": user_id}},
        {"query": query, "user_id": user_id, "limit": limit, "filter": {"user_id": {"$eq": user_id}}},
    ]

    last_exc: Exception | None = None
    memories: list[Any] = []

    for kwargs in search_attempts:
        try:
            memories_raw = client.search(**kwargs)
            memories = _parse_memories(memories_raw)
            break
        except Exception as exc:
            last_exc = exc
            continue

    if last_exc and not memories:
        logger.warning("mem0 lookup failed for user_id=%s: %s", user_id, last_exc)
        return ""

    if not memories:
        return ""

    lines: list[str] = []
    for mem in memories:
        value = mem.get("memory") if isinstance(mem, dict) else str(mem)
        if value:
            lines.append(str(value))

    if not lines:
        return ""

    return "\n".join(lines)


def add_mem0_memory(user_id: str, answer: str, question: str = "") -> None:
    """Extract structured triples from the answer and store each as a compact fact.

    Storing triples instead of raw answer text prevents context bleed between
    queries — each fact is a short, self-contained sentence that mem0 can
    retrieve precisely without polluting unrelated queries.
    """
    if not user_id or not answer:
        return

    client = get_mem0_client()
    if client is None:
        return

    triples = _extract_triples(answer)
    if not triples:
        logger.debug("No triples extracted for user_id=%s, skipping mem0 store", user_id)
        return

    for triple in triples:
        try:
            client.add(triple, user_id=user_id)
            logger.debug("mem0 stored triple: %s", triple)
        except Exception as exc:
            logger.warning("mem0 add failed for user_id=%s triple=%r: %s", user_id, triple, exc)


__all__ = [
    "get_mem0_client",
    "load_mem0_context",
    "add_mem0_memory",
]
