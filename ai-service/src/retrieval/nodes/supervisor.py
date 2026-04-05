# Standard library
import logging
import asyncio
from typing import Any

# Local
from src.retrieval.llm import SUPERVISOR_LLM
from src.retrieval.mem0_client import load_mem0_context
from src.retrieval.prompts import SUPERVISOR_PROMPT
from src.retrieval.state import RetrievalState
from src.retrieval.utils import extract_json_object, normalize_chat_history
from src.shared.langfuse_config import get_langfuse_handler, update_observation

logger = logging.getLogger(__name__)

VALID_CLAUSE_TYPES = {
    "Indemnification",
    "Termination",
    "Payment",
    "Liability",
    "Warranty",
    "Insurance",
    "Confidentiality",
    "IPOwnership",
    "DisputeResolution",
    "ForceMajeure",
    "Assignment",
    "Definition",
    "Administrative",
    "General",
}

CLAUSE_TYPE_NORMALIZATION = {
    "indemnification": "Indemnification",
    "termination": "Termination",
    "terminationclause": "Termination",
    "payment": "Payment",
    "paymentterm": "Payment",
    "paymentterms": "Payment",
    "liability": "Liability",
    "liabilityclause": "Liability",
    "limitationofliability": "Liability",
    "warranty": "Warranty",
    "insurance": "Insurance",
    "confidentiality": "Confidentiality",
    "confidentialityagreement": "Confidentiality",
    "ipownership": "IPOwnership",
    "intellectualproperty": "IPOwnership",
    "disputeresolution": "DisputeResolution",
    "disputeresolutionclause": "DisputeResolution",
    "forcemajeure": "ForceMajeure",
    "assignment": "Assignment",
    "definition": "Definition",
    "administrative": "Administrative",
    "general": "General",
}

VALID_STRATEGIES = {"vector_only", "hybrid", "graph_only"}
VALID_INTENTS = {
    "factual",
    "comparison",
    "risk",
    "obligation",
    "procedural",
    "statutory_interpretation",
}
VALID_JURISDICTIONS = {"federal", "state", "international", "unknown"}


async def supervisor_node(state: RetrievalState) -> dict[str, Any]:
    question = state.get("question", "")
    chat_history = normalize_chat_history(state.get("chat_history", []))[-6:]
    user_id = state.get("user_id", "")

    mem0_context = await asyncio.to_thread(load_mem0_context, user_id)

    handler = get_langfuse_handler()
    invoke_config = {"callbacks": [handler]} if handler else None

    prompt = SUPERVISOR_PROMPT.format(
        mem0_context=mem0_context,
        chat_history=chat_history,
        question=question,
    )

    response = await SUPERVISOR_LLM.ainvoke(prompt, config=invoke_config)
    parsed = extract_json_object(response.content if hasattr(response, "content") else str(response))

    raw_clause_types = parsed.get("clause_types", [])
    clause_types: list[str] = []
    for value in raw_clause_types if isinstance(raw_clause_types, list) else []:
        key = str(value).strip().replace(" ", "")
        normalized = CLAUSE_TYPE_NORMALIZATION.get(key.lower())
        if normalized and normalized in VALID_CLAUSE_TYPES and normalized not in clause_types:
            clause_types.append(normalized)

    entities_raw = parsed.get("entities", [])
    entities = [str(entity).strip() for entity in entities_raw if str(entity).strip()][:5]

    raw_strategy = str(parsed.get("strategy", "hybrid")).strip().lower()
    strategy = raw_strategy if raw_strategy in VALID_STRATEGIES else "hybrid"

    raw_intent = str(parsed.get("intent", "factual")).strip().lower()
    intent = raw_intent if raw_intent in VALID_INTENTS else "factual"

    raw_jurisdiction = str(parsed.get("jurisdiction", "unknown")).strip().lower()
    jurisdiction = raw_jurisdiction if raw_jurisdiction in VALID_JURISDICTIONS else "unknown"

    update_observation(
        "supervisor_node",
        {
            "intent": parsed.get("intent"),
            "strategy": parsed.get("strategy"),
            "jurisdiction": parsed.get("jurisdiction"),
        },
    )

    return {
        "intent": intent,
        "jurisdiction": jurisdiction,
        "clause_types": clause_types,
        "entities": entities,
        "strategy": strategy,
        "mem0_context": mem0_context,
        # Keep query fields initialized even when graph_only path skips rewriter.
        "rewritten_query": question,
        "sub_queries": [],
    }
