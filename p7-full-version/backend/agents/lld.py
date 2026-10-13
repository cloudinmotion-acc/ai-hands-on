from pathlib import Path
from langchain_core.messages import HumanMessage
from agents.base import get_llm, safe_format

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "lld.txt"
PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# Maximum characters of scope/solution to pass to LLD (context compaction)
_SUMMARY_LIMIT = 800


async def run(requirement: str, scope: str, solution: str, hld: str) -> str:
    llm = get_llm()
    scope_summary = scope[:_SUMMARY_LIMIT]
    solution_summary = solution[:_SUMMARY_LIMIT]
    msg = safe_format(
        PROMPT,
        requirement=requirement,
        scope_summary=scope_summary,
        solution_summary=solution_summary,
        hld=hld,
    )
    response = await llm.ainvoke([HumanMessage(content=msg)])
    return response.content
