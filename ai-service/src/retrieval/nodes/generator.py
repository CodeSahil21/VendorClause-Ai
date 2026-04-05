# Standard library
import logging
import asyncio
import re
from typing import Any

# Third-party
from redis.asyncio import Redis

# Local
from src.retrieval.llm import GENERATOR_LLM, HALLUCINATION_CHECKER_LLM
from src.retrieval.mem0_client import add_mem0_memory
from src.retrieval.prompts import GENERATOR_PROMPT, HALLUCINATION_CHECKER_PROMPT, RESPONSE_REFINEMENT_PROMPT
from src.retrieval.state import RetrievalState
from src.retrieval.utils import chunks_to_context, extract_json_object, publish_stream_event
from src.shared.database_service import get_database_service
from src.shared.langfuse_config import get_langfuse_handler, update_observation
from src.shared.redis_client import get_shared_redis

logger = logging.getLogger(__name__)

# Module-level service singletons.
_db = get_database_service()


async def generator_node(state: RetrievalState) -> dict[str, Any]:
    session_id = state.get("session_id", "")
    question = state.get("rewritten_query") or state.get("question", "")
    fused_chunks = state.get("fused_chunks", [])
    intent = state.get("intent", "factual")
    jurisdiction = state.get("jurisdiction", "unknown")
    mem0_context = state.get("mem0_context", "")
    crag_status = state.get("crag_status", "insufficient")
    mem0_block = f"Memory context (if relevant): {mem0_context}" if str(mem0_context).strip() else ""

    context = chunks_to_context(fused_chunks, limit=12)
    prompt = GENERATOR_PROMPT.format(
        question=question,
        context=context,
        intent=intent,
        jurisdiction=jurisdiction,
        mem0_block=mem0_block,
        crag_status=crag_status,
    ).strip()

    redis_client = await get_shared_redis()

    handler = get_langfuse_handler()
    invoke_config = {"callbacks": [handler]} if handler else None

    tokens: list[str] = []
    try:
        async for chunk in GENERATOR_LLM.astream(prompt, config=invoke_config):
            token = getattr(chunk, "content", None)
            if token:
                tokens.append(token)
                await publish_stream_event(redis_client, session_id, "stream:token", {"token": token})
    except Exception as exc:
        logger.error("Streaming generation failed: %s", exc)
        await publish_stream_event(redis_client, session_id, "stream:error", {"message": str(exc)})
        raise

    response_text = "".join(tokens).strip()
    # Safety: strip any raw chunk_id hashes that leaked through (40-char hex strings)
    response_text = re.sub(r"\[\s*[0-9a-f]{8,}\s*\]", "", response_text).strip()

    checker_prompt = HALLUCINATION_CHECKER_PROMPT.format(
        question=question,
        context=context,
        answer=response_text,
    )
    checker_response = await HALLUCINATION_CHECKER_LLM.ainvoke(checker_prompt, config=invoke_config)
    checker_json = extract_json_object(
        checker_response.content if hasattr(checker_response, "content") else str(checker_response)
    )

    is_faithful = bool(checker_json.get("is_faithful", False))
    action = checker_json.get("action", "accept")

    if not is_faithful and action in ("revise", "reject"):
        issues = checker_json.get("unsupported_claims") or checker_json.get("contradictions") or []
        refine_prompt = RESPONSE_REFINEMENT_PROMPT.format(
            issues=issues,
            context=context,
            answer=response_text,
            question=question,
        )
        revised = await GENERATOR_LLM.ainvoke(refine_prompt, config=invoke_config)
        response_text = revised.content.strip() if hasattr(revised, "content") else str(revised).strip()

    update_observation("generator_node", {
        "is_faithful": is_faithful,
        "action": action,
        "crag_status": crag_status,
        "fused_chunks_count": len(fused_chunks),
        "sources_count": min(len(fused_chunks), 10),
    })

    sources = [
        {
            "chunk_id": chunk.get("chunk_id"),
            "clause_type": chunk.get("clause_type"),
            "importance": chunk.get("importance"),
        }
        for chunk in fused_chunks[:10]
    ]

    # Persist assistant response.
    # len(tokens) counts streaming chunks, not real token count — pass None to avoid misleading data.
    if session_id and response_text:
        await asyncio.to_thread(
            _db.save_message,
            session_id,
            "AI",
            response_text,
            None,
        )

    await publish_stream_event(redis_client, session_id, "stream:sources", {"sources": sources})
    # Keep backward compatibility (`message`) and include sources for clients
    # that consume only the terminal event.
    await publish_stream_event(redis_client, session_id, "stream:done", {
        "message": response_text,
        "sources": sources,
    })

    # Best-effort mem0 update — skip fallback/insufficient answers to reduce retrieval bleed.
    should_store_mem0 = (
        bool(response_text)
        and is_faithful
        and "insufficient information in provided documents" not in response_text.lower()
    )
    if should_store_mem0:
        try:
            await asyncio.to_thread(
                add_mem0_memory,
                state.get("user_id", ""),
                response_text,
                question,
            )
        except Exception:
            logger.warning("mem0 update failed for user_id=%s", state.get("user_id"), exc_info=True)

    return {
        "response": response_text,
        "sources": sources,
        "is_faithful": is_faithful,
    }
