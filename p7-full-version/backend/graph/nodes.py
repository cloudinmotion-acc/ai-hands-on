from graph.state import ArchitectState
from agents import scoping as scoping_agent
from agents import solution as solution_agent
from agents import hld as hld_agent
from agents import lld as lld_agent
from agents import doc_assembler


async def scoping_node(state: ArchitectState) -> dict:
    content = await scoping_agent.run(state["requirement"])
    return {
        "scope": {"content": content, "approved": False, "edited": False},
        "current_stage": "scoping",
    }


async def solution_node(state: ArchitectState) -> dict:
    scope = state["scope"]
    if scope is None:
        raise ValueError("scope must be set before solution")
    content = await solution_agent.run(state["requirement"], scope["content"])
    return {
        "solution": {"content": content, "approved": False, "edited": False},
        "current_stage": "solution",
    }


async def hld_node(state: ArchitectState) -> dict:
    scope = state["scope"]
    solution = state["solution"]
    if scope is None or solution is None:
        raise ValueError("scope and solution must be set before hld")
    content = await hld_agent.run(
        state["requirement"], scope["content"], solution["content"]
    )
    return {
        "hld": {"content": content, "approved": False, "edited": False},
        "current_stage": "hld",
    }


async def lld_node(state: ArchitectState) -> dict:
    scope = state["scope"]
    solution = state["solution"]
    hld = state["hld"]
    if scope is None or solution is None or hld is None:
        raise ValueError("scope, solution, and hld must be set before lld")
    # Compaction: pass scope+solution content; lld agent truncates internally
    content = await lld_agent.run(
        requirement=state["requirement"],
        scope=scope["content"],
        solution=solution["content"],
        hld=hld["content"],
    )
    return {
        "lld": {"content": content, "approved": False, "edited": False},
        "current_stage": "lld",
    }


async def doc_node(state: ArchitectState) -> dict:
    scope = state["scope"]
    solution = state["solution"]
    hld = state["hld"]
    lld = state["lld"]
    if scope is None or solution is None or hld is None or lld is None:
        raise ValueError("all stages must be set before doc")
    doc_text = await doc_assembler.run(
        scope=scope["content"],
        solution=solution["content"],
        hld=hld["content"],
        lld=lld["content"],
    )
    return {"doc_text": doc_text, "current_stage": "doc"}
