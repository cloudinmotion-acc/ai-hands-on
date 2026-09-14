import os
from pydantic import BaseModel, Field

DEFAULT_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")


class Citation(BaseModel):
    source: str
    page: int | None
    sheet: str | None
    row_range: str | None
    snippet: str
    score: float


class LLMParams(BaseModel):
    temperature:       float = Field(default=0.2,  ge=0.0, le=2.0)
    max_tokens:        int   = Field(default=4096, ge=64,  le=16384)
    top_p:             float = Field(default=0.9,  ge=0.0, le=1.0)
    top_k:             int   = Field(default=40,   ge=1,   le=200)
    frequency_penalty: float = Field(default=0.3,  ge=0.0, le=2.0)
    enable_thinking:   bool  = False


class QueryRequest(BaseModel):
    question:       str
    model:          str = DEFAULT_MODEL
    prompt_version: str = "v1"
    top_k_chunks:   int = Field(default=4, ge=1, le=10)
    llm_params:     LLMParams = LLMParams()


class QueryResponse(BaseModel):
    answer:         str
    citations:      list[Citation]
    model_used:     str
    prompt_version: str
