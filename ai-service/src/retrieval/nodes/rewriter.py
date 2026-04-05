# Standard library
import logging
from typing import Any

# Local
from src.retrieval.llm import REWRITER_LLM
from src.retrieval.prompts import REWRITER_PROMPT
from src.retrieval.state import RetrievalState
from src.retrieval.utils import normalize_chat_history
from src.shared.langfuse_config import get_langfuse_handler, update_observation

logger = logging.getLogger(__name__)


async def rewriter_node(state: RetrievalState) -> dict[str, Any]:
    question = state.get("question", "")
    intent = state.get("intent", "factual")
    crag_gap_analysis = (state.get("crag_gap_analysis") or "").strip()
    chat_history = normalize_chat_history(state.get("chat_history", []))

    handler = get_langfuse_handler()
    invoke_config = {"callbacks": [handler]} if handler else None

    gap_focus = f"\n6. Focus on retrieving: {crag_gap_analysis}" if crag_gap_analysis else ""
    prompt = REWRITER_PROMPT.format(
        intent=intent,
        chat_history=chat_history,
        question=question,
        gap_focus=gap_focus,
    )
    response = await REWRITER_LLM.ainvoke(prompt, config=invoke_config)
    rewritten_query = response.content.strip() if hasattr(response, "content") else str(response).strip()

    update_observation("rewriter_node", {
        "rewritten_query": rewritten_query,
        "used_crag_gap_analysis": bool(crag_gap_analysis),
        "chat_history_len": len(chat_history),
    })

    return {"rewritten_query": rewritten_query, "sub_queries": []}
