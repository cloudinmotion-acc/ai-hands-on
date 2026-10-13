import os
import httpx
from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ["AGENT_MODEL"],
        base_url=os.environ["NVIDIA_BASE_URL"],
        api_key=os.environ["NVIDIA_API_KEY"],
        http_client=httpx.Client(verify=False),
        temperature=0.4,
        streaming=True,
    )


def safe_format(template: str, **kwargs: str) -> str:
    """Replace {placeholder} tokens in a prompt template without interpreting any other
    {curly braces} that appear inside the variable values (e.g. JSON schemas, code blocks)."""
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", value)
    return template
