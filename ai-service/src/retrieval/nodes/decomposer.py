import json
import re
from typing import Any

from langchain_openai import ChatOpenAI

from src.retrieval.prompts import DECOMPOSER_PROMPT
from src.retrieval.state import RetrievalState
from src.shared.langfuse_config import get_langfuse_handler
from src.shared.settings import settings

_LLM = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
    request_timeout=60,
    api_key=settings.openai_api_key,
)


def _extract_json_array(text: str) -> list[str]:
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        return []
    return []


async def decomposer_node(state: RetrievalState) -> dict[str, Any]:
    question = state.get("rewritten_query") or state.get("question", "")

    handler = get_langfuse_handler()
    invoke_config = {"callbacks": [handler]} if handler else None

    prompt = DECOMPOSER_PROMPT.format(question=question)
    response = await _LLM.ainvoke(prompt, config=invoke_config)
    text = response.content if hasattr(response, "content") else str(response)

    sub_queries = _extract_json_array(text)
    if not sub_queries:
        sub_queries = [question]

    return {"sub_queries": sub_queries}
