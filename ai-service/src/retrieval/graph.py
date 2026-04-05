# Third-party
from langgraph.graph import END, StateGraph

# Local — nodes
from src.retrieval.nodes.bridge_fusion import bridge_fusion_node
from src.retrieval.nodes.crag_evaluator import crag_evaluator_node
from src.retrieval.nodes.decomposer import decomposer_node
from src.retrieval.nodes.generator import generator_node
from src.retrieval.nodes.mcp_orchestrator import mcp_orchestrator_node
from src.retrieval.nodes.rewriter import rewriter_node
from src.retrieval.nodes.supervisor import supervisor_node

# Local — state + config
from src.retrieval.state import RetrievalState
from src.retrieval.routes import route_after_supervisor, route_after_rewriter, route_after_crag
from src.retrieval.checkpointer import build_checkpointer, close_checkpointer_resources


def build_graph():
    graph = StateGraph(RetrievalState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("rewriter", rewriter_node)
    graph.add_node("decomposer", decomposer_node)
    graph.add_node("mcp_orchestrator", mcp_orchestrator_node)
    graph.add_node("bridge_fusion", bridge_fusion_node)
    graph.add_node("crag_evaluator", crag_evaluator_node)
    graph.add_node("generator", generator_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "rewriter": "rewriter",
            "mcp_orchestrator": "mcp_orchestrator",
        },
    )
    graph.add_conditional_edges(
        "rewriter",
        route_after_rewriter,
        {
            "decomposer": "decomposer",
            "mcp_orchestrator": "mcp_orchestrator",
        },
    )
    graph.add_edge("decomposer", "mcp_orchestrator")
    graph.add_edge("mcp_orchestrator", "bridge_fusion")
    graph.add_edge("bridge_fusion", "crag_evaluator")
    graph.add_conditional_edges(
        "crag_evaluator",
        route_after_crag,
        {
            "rewriter": "rewriter",
            "generator": "generator",
        },
    )
    graph.add_edge("generator", END)

    checkpointer = build_checkpointer()
    return graph.compile(checkpointer=checkpointer) if checkpointer else graph.compile()


def close_graph_resources() -> None:
    close_checkpointer_resources()
