# Standard library
from typing import Any

# Local
from src.retrieval.llm import CRAG_EVALUATOR_LLM
from src.retrieval.prompts import CRAG_EVALUATOR_PROMPT
from src.retrieval.state import RetrievalState
from src.retrieval.utils import chunks_to_context, extract_json_object
from src.shared.langfuse_config import get_langfuse_handler, update_observation


async def crag_evaluator_node(state: RetrievalState) -> dict[str, Any]:
    question = state.get("rewritten_query") or state.get("question", "")
    fused_chunks = state.get("fused_chunks", [])
    crag_iteration = state.get("crag_iteration", 0)

    context = chunks_to_context(fused_chunks, limit=15)
    prompt = CRAG_EVALUATOR_PROMPT.format(question=question, context=context)

    handler = get_langfuse_handler()
    invoke_config = {"callbacks": [handler]} if handler else None
    response = await CRAG_EVALUATOR_LLM.ainvoke(prompt, config=invoke_config)
    parsed = extract_json_object(response.content if hasattr(response, "content") else str(response))

    status = parsed.get("status", "partial")
    gap_analysis = parsed.get("gap_analysis", "")
    if status not in ("sufficient", "partial", "insufficient"):
        status = "partial"

    next_iteration = crag_iteration
    context_sufficient = False

    if status == "sufficient":
        context_sufficient = True
    elif status == "insufficient":
        next_iteration = crag_iteration + 1

    update_observation("crag_evaluator_node", {
        "crag_status": status,
        "crag_iteration_in": crag_iteration,
        "crag_iteration_out": next_iteration,
        "context_sufficient": context_sufficient,
        "gap_analysis": gap_analysis,
        "fused_chunks_count": len(fused_chunks),
    })

    return {
        "crag_status": status,
        "crag_gap_analysis": gap_analysis,
        "crag_iteration": next_iteration,
        "context_sufficient": context_sufficient,
    }
