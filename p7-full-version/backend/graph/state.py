from __future__ import annotations
from typing import TypedDict, Literal, Optional

Stage = Literal["scoping", "solution", "hld", "lld", "doc", "complete"]


class StageResult(TypedDict):
    content: str
    approved: bool
    edited: bool


class ArchitectState(TypedDict):
    requirement: str
    scope: Optional[StageResult]
    solution: Optional[StageResult]
    hld: Optional[StageResult]
    lld: Optional[StageResult]
    doc_text: Optional[str]
    docx_path: Optional[str]
    current_stage: Stage
