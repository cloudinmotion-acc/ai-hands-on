"""
Query pipeline: question -> embed -> top-k search -> LLM -> answer + citations
Runs on every user question.
"""

from dotenv import load_dotenv
import os
import time
from pathlib import Path

import httpx
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langchain_openai import ChatOpenAI
from langchain_postgres import PGVector
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from schemas import Citation, QueryRequest, QueryResponse
from db import get_postgres_url

load_dotenv()

EMBED_MODEL = os.getenv("NVIDIA_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")
COLLECTION  = "p2_docs"
PROMPTS_DIR  = Path(__file__).parent / "prompts"


def _load_prompt(version: str) -> str:
    path = PROMPTS_DIR / f"{version}.txt"
    if not path.exists():
        available = [p.stem for p in PROMPTS_DIR.glob("*.txt")]
        raise ValueError(f"Prompt version '{version}' not found. Available: {available}")
    return path.read_text()


def _get_store() -> PGVector:
    embeddings = NVIDIAEmbeddings(model=EMBED_MODEL, verify_ssl=False)
    return PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION,
        connection=str(get_postgres_url()),
        use_jsonb=True,
    )


def _build_citations(docs_with_scores) -> list[Citation]:
    citations = []
    for doc, score in docs_with_scores:
        meta = doc.metadata
        citations.append(Citation(
            source=meta.get("source", "unknown"),
            page=meta.get("page"),
            sheet=meta.get("sheet"),
            row_range=f"{meta['row_start']}-{meta['row_end']}" if "row_start" in meta else None,
            snippet=doc.page_content[:300],
            score=round(float(score), 4),
        ))
    return citations


def _call_with_retry(chain, payload: dict, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            return chain.invoke(payload)
        except Exception as e:
            is_timeout = "timeout" in str(e).lower() or "timed out" in str(e).lower()
            if attempt == retries - 1 or is_timeout:
                raise
            wait = 2 ** attempt
            print(f"[retry {attempt + 1}] {e} - waiting {wait}s")
            time.sleep(wait)
    raise RuntimeError("All retries exhausted")


def answer(req: QueryRequest) -> QueryResponse:
    print(f"[1/4] Loading prompt version '{req.prompt_version}'...")
    system_template = _load_prompt(req.prompt_version)

    print(f"[2/4] Retrieving top-{req.top_k_chunks} chunks from pgvector...")
    store = _get_store()
    docs_with_scores = store.similarity_search_with_score(req.question, k=req.top_k_chunks)
    citations = _build_citations(docs_with_scores)
    context = "\n\n---\n\n".join(doc.page_content for doc, _ in docs_with_scores)

    p = req.llm_params
    print(f"[3/4] Calling LLM ({req.model})...")
    llm = ChatOpenAI(
        model=req.model,
        temperature=p.temperature,
        max_tokens=p.max_tokens,
        top_p=p.top_p,
        frequency_penalty=p.frequency_penalty,
        base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        api_key=os.getenv("NVIDIA_API_KEY"),
        timeout=600,
        http_client=httpx.Client(verify=False),
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "{question}"),
    ])
    chain = prompt | llm | StrOutputParser()

    answer_text = _call_with_retry(chain, {"context": context, "question": req.question})

    print(f"[4/4] Done.")
    return QueryResponse(
        answer=answer_text,
        citations=citations,
        model_used=req.model,
        prompt_version=req.prompt_version,
    )
