async def run(scope: str, solution: str, hld: str, lld: str) -> str:
    """
    Assembles all four approved stage outputs into a structured markdown document.
    No LLM call  -  pure string formatting.
    """
    doc = f"""# System Design Document

## 1. Scope

{scope}

## 2. Solution Architecture

{solution}

## 3. High-Level Design

{hld}

## 4. Low-Level Design

{lld}
"""
    return doc.strip()
