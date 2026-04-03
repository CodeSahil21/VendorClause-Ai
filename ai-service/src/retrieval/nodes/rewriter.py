import logging
from typing import Any

from langchain_openai import ChatOpenAI

from src.retrieval.prompts import REWRITER_PROMPT
from src.retrieval.state import RetrievalState
from src.shared.langfuse_config import get_langfuse_handler
from src.shared.settings import settings

logger = logging.getLogger(__name__)

_LLM = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    request_timeout=60,
    api_key=settings.openai_api_key,
)


async def rewriter_node(state: RetrievalState) -> dict[str, Any]:
    question = state.get("question", "")
    chat_history = state.get("chat_history", [])

    handler = get_langfuse_handler()
    invoke_config = {"callbacks": [handler]} if handler else None

    prompt = REWRITER_PROMPT.format(chat_history=chat_history, question=question)
    response = await _LLM.ainvoke(prompt, config=invoke_config)
    rewritten_query = response.content.strip() if hasattr(response, "content") else str(response).strip()

    return {"rewritten_query": rewritten_query}
