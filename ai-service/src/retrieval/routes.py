# Local
from src.retrieval.state import RetrievalState


def route_after_supervisor(state: RetrievalState) -> str:
    # Always rewrite first to resolve pronouns and normalize references.
    return "rewriter"


def route_after_rewriter(state: RetrievalState) -> str:
    rewritten_query = state.get("rewritten_query") or ""
    q = rewritten_query.lower()

    # Prefer decomposition only when query appears genuinely multi-part.
    has_multi_question = rewritten_query.count("?") >= 2
    has_compare_terms = any(term in q for term in ["compare", "difference", "versus", " vs "])
    has_enumeration = any(token in q for token in ["first", "second", "third", "1.", "2.", "3."])
    long_compound = len(rewritten_query.split()) > 35 and (" and " in q or " or " in q)

    if has_multi_question or has_compare_terms or has_enumeration or long_compound:
        return "decomposer"
    return "mcp_orchestrator"


def route_after_crag(state: RetrievalState) -> str:
    if state.get("context_sufficient", False):
        return "generator"

    # Hard-stop safeguard even if evaluator output is malformed.
    if state.get("crag_iteration", 0) >= 2:
        return "generator"

    # Retry only for genuinely insufficient retrieval; partial can proceed.
    if state.get("crag_status") == "insufficient":
        return "rewriter"
    return "generator"


__all__ = [
    "route_after_supervisor",
    "route_after_rewriter",
    "route_after_crag",
]
