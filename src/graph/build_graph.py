"""LangGraph Builder.

Wires the agent nodes together into a StateGraph, implementing the topology
defined in the Multi-Agent Orchestrator Plan.
"""

from langgraph.graph import END, START, StateGraph

from src.agents.orchestrator import orchestrator_node
from src.agents.searcher import searcher_node
from src.agents.deep_diver import deep_diver_node
from src.agents.pain_diver import pain_diver_node
from src.agents.thinker import thinker_node
from src.agents.report_builder import report_builder as writer_node
from src.graph.state import ResearchState


def route_orchestrator(state: ResearchState) -> str:
    """Conditional routing based on orchestrator decision."""
    next_agent = state.get("next_agent", "searcher")
    if next_agent == "FINISH":
        return END
    return next_agent


def build_graph() -> StateGraph:
    """Build and compile the research agent graph."""
    builder = StateGraph(ResearchState)

    # 1. Add all nodes
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("searcher", searcher_node)
    builder.add_node("pain_diver", pain_diver_node)
    builder.add_node("deep_diver", deep_diver_node)
    builder.add_node("thinker", thinker_node)
    builder.add_node("writer", writer_node)

    # 2. Add edges
    
    # Entry point
    builder.add_edge(START, "orchestrator")
    
    # The orchestrator decides where to go next
    builder.add_conditional_edges("orchestrator", route_orchestrator)
    
    # Workers always report back to the orchestrator to decide the next step
    builder.add_edge("searcher", "orchestrator")
    builder.add_edge("pain_diver", "orchestrator")
    builder.add_edge("deep_diver", "orchestrator")
    builder.add_edge("thinker", "orchestrator")
    builder.add_edge("writer", "orchestrator")

    return builder.compile()
