import os
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn


def _set_title_style(doc: Document) -> None:
    """Ensure the document has expected styles; Word creates them automatically."""
    pass


def generate(session_id: str, doc_text: str) -> str:
    """
    Convert a markdown-like document string to a .docx file.

    Markdown conventions handled:
      # Title         → Title style (level 0 heading)
      ## Heading      → Heading 1
      ### Sub-heading → Heading 2
      #### Sub-sub    → Heading 3
      - item / * item → List Bullet
      (blank line)    → skipped
      everything else → Normal paragraph
    """
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    doc = Document()

    for line in doc_text.split("\n"):
        line = line.rstrip()

        if not line:
            continue

        if line.startswith("#### "):
            doc.add_heading(line[5:], level=3)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=2)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=1)
        elif line.startswith("# "):
            doc.add_heading(line[2:], level=0)
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(line[2:], style="List Bullet")
        else:
            doc.add_paragraph(line)

    path = str(out_dir / f"{session_id}.docx")
    doc.save(path)
    return path
