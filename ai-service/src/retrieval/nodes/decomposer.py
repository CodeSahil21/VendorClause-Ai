# Standard library
from typing import Any

# Local
from src.retrieval.llm import DECOMPOSER_LLM
from src.retrieval.prompts import DECOMPOSER_PROMPT
from src.retrieval.state import RetrievalState
from src.retrieval.utils import extract_json_array
from src.shared.langfuse_config import get_langfuse_handler, update_observation


async def decomposer_node(state: RetrievalState) -> dict[str, Any]:
    question = state.get("rewritten_query") or state.get("question", "")

    handler = get_langfuse_handler()
    invoke_config = {"callbacks": [handler]} if handler else None

    prompt = DECOMPOSER_PROMPT.format(question=question)
    response = await DECOMPOSER_LLM.ainvoke(prompt, config=invoke_config)
    text = response.content if hasattr(response, "content") else str(response)

    sub_queries = extract_json_array(text)
    if not sub_queries:
        sub_queries = [question]

    update_observation("decomposer_node", {
        "sub_queries_count": len(sub_queries),
        "sub_queries": sub_queries,
    })

    return {"sub_queries": sub_queries}
