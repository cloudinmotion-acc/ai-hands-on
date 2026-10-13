"""
Completeness evaluator: LLM-as-judge scores each checklist item per stage.

Uses httpx directly (same as P2/P3) — proven to work through the Accenture proxy.

IMPORTANT — the judge is a REASONING model (nemotron-3-super-120b-a12b).
It emits `reasoning_content` before `content`.  If max_tokens is too small the
whole budget is spent reasoning, the response is cut off (finish_reason="length")
and `content` comes back EMPTY — which silently scored every stage 0.0.
Budget must cover reasoning (~800 tokens) + the JSON answer (~40 tokens).
If a call still gets truncated we retry once with reasoning disabled
(`chat_template_kwargs={"thinking": False}`), which answers in ~35 tokens.
"""

import asyncio
import json
import logging
import re

import httpx

logger = logging.getLogger("p8.completeness")

# Reasoning alone uses ~820 tokens on a full-size prompt; leave generous headroom.
MAX_TOKENS_REASONING = 3000
# With thinking disabled the model answers in ~35 tokens.
MAX_TOKENS_NO_THINK = 512

# How much of a stage document the judge is allowed to see.
#
# This was 5,000 — which silently measured only the first ~13% of an LLD
# (real LLDs run 40k-51k chars).  Checklist items that live in the back half
# of the document (endpoint catalogues, error codes, pagination, sequence
# flows) were scored 0 purely because the judge never saw them: measured
# A/B on four real LLDs showed 57.5% truncated vs 100% on the full document,
# with the gained items being exactly the ones past the cut.
# 60k chars is ~15k tokens — comfortably inside the judge's context window.
MAX_CONTENT_CHARS = 60_000

JUDGE_PROMPT = """\
You are a senior software architect. Score the following checklist against the document.

STAGE: __STAGE__

DOCUMENT:
__CONTENT__

CHECKLIST:
__ITEMS_TEXT__

Rules:
- Score 1 if the item is clearly and specifically addressed in the document.
- Score 0 if absent, vague, or only implied.
- Output ONLY the JSON below — no prose, no markdown fences, no explanation.

{"scores": [__SCORE_PLACEHOLDERS__]}"""


def _build_prompt(stage: str, content: str, items: list[str]) -> str:
    items_text = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
    score_placeholders = ", ".join(["0"] * len(items))
    # str.replace() avoids KeyError when content contains {curly braces}
    # (JSON schemas, DDL and API contracts are full of them)
    return (
        JUDGE_PROMPT
        .replace("__STAGE__", stage)
        .replace("__CONTENT__", content[:MAX_CONTENT_CHARS])
        .replace("__ITEMS_TEXT__", items_text)
        .replace("__SCORE_PLACEHOLDERS__", score_placeholders)
    )


def _parse_scores(text: str, expected_len: int) -> list[int]:
    text = text.strip()

    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Strategy 1: whole response is valid JSON
    try:
        data = json.loads(text)
        scores = data.get("scores", [])
        if len(scores) == expected_len:
            return [max(0, min(1, int(float(s)))) for s in scores]
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Strategy 2: regex — find the "scores" array anywhere in the text
    m = re.search(r'"scores"\s*:\s*\[([^\]]*)\]', text, re.DOTALL)
    if m:
        try:
            raw_vals = [v.strip() for v in m.group(1).split(",") if v.strip()]
            scores = [max(0, min(1, int(float(v)))) for v in raw_vals]
            if len(scores) == expected_len:
                return scores
        except (ValueError, TypeError):
            pass

    logger.warning(f"Cannot parse scores (len={len(text)}): {text[:80]!r}")
    return [0] * expected_len


async def _post_judge(
    *, client: httpx.AsyncClient, base_url: str, api_key: str,
    judge_model: str, prompt: str, no_think: bool,
) -> tuple[int, str, str]:
    """Returns (status_code, content, finish_reason)."""
    payload: dict = {
        "model": judge_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": MAX_TOKENS_NO_THINK if no_think else MAX_TOKENS_REASONING,
    }
    if no_think:
        payload["chat_template_kwargs"] = {"thinking": False}

    resp = await client.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
    )
    if resp.status_code != 200:
        return resp.status_code, "", ""

    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message", {}).get("content") or "").strip()
    return 200, content, choice.get("finish_reason", "")


async def _judge_stage(
    *,
    api_key: str,
    base_url: str,
    judge_model: str,
    stage: str,
    content: str,
    items: list[str],
    max_retries: int = 3,
) -> float:
    if not content or not content.strip():
        logger.warning(f"No content for stage={stage}, skipping judge")
        return 0.0

    prompt = _build_prompt(stage, content, items)

    async with httpx.AsyncClient(verify=False, timeout=240) as client:
        for attempt in range(max_retries):
            if attempt > 0:
                wait = 5 * attempt
                logger.info(f"Judge [{stage}] retry {attempt}/{max_retries-1} in {wait}s")
                await asyncio.sleep(wait)

            try:
                status, raw, finish = await _post_judge(
                    client=client, base_url=base_url, api_key=api_key,
                    judge_model=judge_model, prompt=prompt, no_think=False,
                )

                if status == 429:
                    logger.warning(f"Judge [{stage}] 429 rate-limited")
                    await asyncio.sleep(10 * (attempt + 1))
                    continue
                if status != 200:
                    logger.error(f"Judge [{stage}] HTTP {status}")
                    continue

                # Reasoning ate the whole budget — fall back to no-think mode.
                if not raw and finish == "length":
                    logger.warning(
                        f"Judge [{stage}] truncated by reasoning (finish=length); "
                        f"retrying with thinking disabled"
                    )
                    status, raw, finish = await _post_judge(
                        client=client, base_url=base_url, api_key=api_key,
                        judge_model=judge_model, prompt=prompt, no_think=True,
                    )

                if not raw:
                    logger.warning(f"Judge [{stage}] empty content (finish={finish}), retrying")
                    continue

                logger.info(f"Judge [{stage}] raw: {raw[:100]!r}")
                scores = _parse_scores(raw, len(items))
                score = round(sum(scores) / len(items), 3)
                logger.info(f"Judge [{stage}] score={score} ({sum(scores)}/{len(items)} items)")
                return score

            except Exception as exc:
                logger.error(f"Judge [{stage}] failed: {exc}")

    logger.error(f"Judge [{stage}] exhausted retries, returning 0.0")
    return 0.0


async def evaluate(
    *,
    outputs: dict[str, str],
    checklists: dict[str, list[str]],
    api_key: str,
    base_url: str,
    judge_model: str,
    sem: asyncio.Semaphore | None = None,
) -> dict:
    """
    Evaluate completeness for one scenario across all stages.

    `sem` lets the caller cap concurrency across ALL scenarios at once —
    a burst of 12+ simultaneous requests does draw a real 429 from NVIDIA.

    Returns:
        {"scoping": 0.8, "solution": 0.7, "hld": 0.9, "lld": 0.65, "mean": 0.76}
    """
    sem = sem or asyncio.Semaphore(3)
    stages = list(checklists.keys())

    async def _run_one(stage: str):
        async with sem:
            score = await _judge_stage(
                api_key=api_key,
                base_url=base_url,
                judge_model=judge_model,
                stage=stage,
                content=outputs.get(stage, ""),
                items=checklists[stage],
            )
            return stage, score

    results = await asyncio.gather(*[_run_one(s) for s in stages])
    scores = {stage: score for stage, score in results}
    scores_list = list(scores.values())
    mean = round(sum(scores_list) / len(scores_list), 3) if scores_list else 0.0
    return {**scores, "mean": mean}
