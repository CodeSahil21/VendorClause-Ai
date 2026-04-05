from typing import Literal, TypedDict


IntentType = Literal["factual", "comparison", "risk", "obligation", "procedural", "statutory_interpretation"]
StrategyType = Literal["vector_only", "hybrid", "graph_only"]
JurisdictionType = Literal["federal", "state", "international", "unknown"]
CRAGStatusType = Literal["sufficient", "partial", "insufficient"]


class RetrievalState(TypedDict, total=False):
    """Canonical LangGraph state for the retrieval pipeline.

    Fields are added gradually as nodes execute, so this TypedDict is
    intentionally partial (total=False).
    """

    # Input
    question: str
    session_id: str
    document_id: str
    user_id: str
    chat_history: list[dict]

    # Supervisor output
    intent: IntentType
    jurisdiction: JurisdictionType
    clause_types: list[str]
    entities: list[str]
    strategy: StrategyType
    mem0_context: str

    # Query processing
    rewritten_query: str
    sub_queries: list[str]

    # MCP results
    qdrant_results: list[dict]
    neo4j_chunk_ids: list[str]

    # Fusion and evaluation
    fused_chunks: list[dict]
    crag_iteration: int
    crag_status: CRAGStatusType
    crag_gap_analysis: str
    context_sufficient: bool

    # Generation
    response: str
    sources: list[dict]
    is_faithful: bool
