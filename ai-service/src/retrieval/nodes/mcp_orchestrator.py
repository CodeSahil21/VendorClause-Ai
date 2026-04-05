# Standard library
import logging
import time
from typing import Any

# Local
from src.retrieval.mcp_client import MCPClient, MCPToolCall
from src.retrieval.state import RetrievalState
from src.shared.langfuse_config import update_observation

# Module-level MCP client singleton — shared across all requests.
_mcp_client = MCPClient()
logger = logging.getLogger(__name__)


def _build_query_list(state: RetrievalState) -> list[str]:
    sub_queries = [q for q in state.get("sub_queries", []) if q]
    if sub_queries:
        return sub_queries

    rewritten = state.get("rewritten_query")
    if rewritten:
        return [rewritten]

    question = state.get("question", "")
    return [question] if question else []


async def mcp_orchestrator_node(state: RetrievalState) -> dict[str, Any]:
    t0 = time.perf_counter()
    queries = list(dict.fromkeys(_build_query_list(state)))[:4]
    per_query_top_k = 7 if len(queries) > 1 else 10
    document_id = state.get("document_id", "")
    entities = state.get("entities", [])
    strategy = state.get("strategy", "hybrid")
    intent = state.get("intent", "factual")

    if strategy == "graph_only" and not entities:
        logger.warning("graph_only strategy with no entities; downgrading to hybrid")
        strategy = "hybrid"

    if strategy == "vector_only" and entities:
        logger.debug("vector_only strategy selected; skipping graph call despite extracted entities")

    calls: list[MCPToolCall] = []

    if strategy != "graph_only":
        for query in queries:
            calls.append(
                MCPToolCall(
                    server="qdrant",
                    tool_name="vector_search",
                    params={
                        "query_text": query,
                        "document_id": document_id,
                        "top_k": per_query_top_k,
                        "use_sparse": True,
                    },
                )
            )

    if strategy in ("hybrid", "graph_only") and entities:
        calls.append(
            MCPToolCall(
                server="neo4j",
                tool_name="graph_traverse",
                params={
                    "entity_names": entities,
                    "document_id": document_id,
                    "relationship_types": [],
                    "depth": 2,
                },
            )
        )

    if not calls:
        update_observation("mcp_orchestrator_node", {
            "strategy": strategy,
            "queries_count": len(queries),
            "entities_count": len(entities),
            "calls_count": 0,
            "qdrant_results_count": 0,
            "neo4j_chunk_ids_count": 0,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        })
        return {"qdrant_results": [], "neo4j_chunk_ids": []}

    dispatch_results = await _mcp_client.parallel_dispatch(calls)

    qdrant_results: list[dict[str, Any]] = []
    neo4j_records: list[dict[str, Any]] = []
    for call, result in zip(calls, dispatch_results):
        if isinstance(result, dict) and result.get("success") is False:
            continue
        if not isinstance(result, list):
            continue

        if call.tool_name == "vector_search":
            for row in result:
                if isinstance(row, dict):
                    qdrant_results.append(row)
        elif call.tool_name == "graph_traverse":
            for row in result:
                if isinstance(row, dict):
                    neo4j_records.append(row)

    # Collect BOTH source and target chunk IDs from graph traversals.
    chunk_ids: set[str] = set()
    for row in neo4j_records:
        source_id = row.get("source_chunk_id")
        target_id = row.get("target_chunk_id")
        if source_id:
            chunk_ids.add(source_id)
        if target_id:
            chunk_ids.add(target_id)

    extract_calls_made = 0
    should_extract_second_pass = (
        strategy in ("hybrid", "graph_only")
        and bool(entities)
        and intent in ("factual", "obligation", "risk")
        and len(chunk_ids) == 0
    )

    if should_extract_second_pass:
        extract_calls = [
            MCPToolCall(
                server="neo4j",
                tool_name="extract_entity",
                params={
                    "entity_name": entity,
                    "document_id": document_id,
                },
            )
            for entity in entities[:2]
        ]
        extract_calls_made = len(extract_calls)
        extract_results = await _mcp_client.parallel_dispatch(extract_calls)

        for result in extract_results:
            if isinstance(result, dict) and result.get("success") is False:
                continue
            if not isinstance(result, list):
                continue
            for row in result:
                if not isinstance(row, dict):
                    continue
                chunk_id = row.get("chunk_id")
                if chunk_id:
                    chunk_ids.add(chunk_id)
                for connected_id in row.get("connected_chunk_ids", []):
                    if connected_id:
                        chunk_ids.add(connected_id)

    update_observation("mcp_orchestrator_node", {
        "strategy": strategy,
        "queries_count": len(queries),
        "entities_count": len(entities),
        "calls_count": len(calls),
        "second_pass_extract_calls": extract_calls_made,
        "qdrant_results_count": len(qdrant_results),
        "neo4j_records_count": len(neo4j_records),
        "neo4j_chunk_ids_count": len(chunk_ids),
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
    })

    return {
        "qdrant_results": qdrant_results,
        "neo4j_chunk_ids": list(chunk_ids),
    }
