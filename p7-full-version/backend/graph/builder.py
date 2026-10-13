from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from graph.state import ArchitectState
from graph.nodes import scoping_node, solution_node, hld_node, lld_node, doc_node

STAGE_NODES = ["scoping", "solution", "hld", "lld", "doc"]
STAGE_ORDER = ["scoping", "solution", "hld", "lld", "doc"]


def build_graph(checkpointer: AsyncSqliteSaver):
    g: StateGraph = StateGraph(ArchitectState)

    g.add_node("scoping", scoping_node)
    g.add_node("solution", solution_node)
    g.add_node("hld", hld_node)
    g.add_node("lld", lld_node)
    g.add_node("doc", doc_node)

    g.set_entry_point("scoping")
    g.add_edge("scoping", "solution")
    g.add_edge("solution", "hld")
    g.add_edge("hld", "lld")
    g.add_edge("lld", "doc")
    g.add_edge("doc", END)

    return g.compile(
        checkpointer=checkpointer,
        interrupt_after=["scoping", "solution", "hld", "lld"],
    )
