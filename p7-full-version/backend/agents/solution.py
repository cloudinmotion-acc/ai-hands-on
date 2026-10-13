from pathlib import Path
from langchain_core.messages import HumanMessage
from agents.base import get_llm, safe_format

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "solution.txt"
PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


async def run(requirement: str, scope: str) -> str:
    llm = get_llm()
    msg = safe_format(PROMPT, requirement=requirement, scope=scope)
    response = await llm.ainvoke([HumanMessage(content=msg)])
    return response.content
