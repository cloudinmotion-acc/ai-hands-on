from dataclasses import dataclass
from typing import Literal


@dataclass
class GuardResult:
    passed: bool
    action: Literal["allow", "block", "rewrite"]
    reason: str
    modified_text: str | None = None  # only set by PII scrubber
    guard_name: str = ""              # set by input_guard orchestrator
