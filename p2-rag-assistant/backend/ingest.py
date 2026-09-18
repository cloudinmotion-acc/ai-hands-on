"""
Ingest pipeline: document -> chunks -> embeddings -> pgvector
Runs once per document upload.
"""

from dotenv import load_dotenv
import hashlib
import os
from pathlib import Path

import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document
from sqlalchemy import create_engine, text
from db import get_postgres_url

load_dotenv()

EMBED_MODEL   = os.getenv("NVIDIA_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")
COLLECTION    = "p2_docs"
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50


def _get_store() -> PGVector:
    embeddings = NVIDIAEmbeddings(model=EMBED_MODEL, verify_ssl=False)
    return PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION,
        connection=str(get_postgres_url()),
        use_jsonb=True,
    )


def _load_txt(path: str, original_name: str | None = None) -> list[Document]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return [Document(page_content=text, metadata={"source": original_name or Path(path).name, "page": 1})]


def _load_pdf(path: str, original_name: str | None = None) -> list[Document]:
    loader = PyPDFLoader(path)
    docs = loader.load()
    # PyPDFLoader stamps `source` with the path it was handed, which for an upload
    # is a throwaway temp file. Citations must name the document the user chose.
    for d in docs:
        d.metadata["source"] = original_name or Path(path).name
    return docs


def _load_excel(path: str, original_name: str | None = None) -> list[Document]:
    docs = []
    filename = original_name or Path(path).name
    with pd.ExcelFile(path) as xf:
        for sheet in xf.sheet_names:
            df = xf.parse(sheet)
            for start in range(0, len(df), 10):
                chunk_df = df.iloc[start: start + 10]
                lines = []
                for _, row in chunk_df.iterrows():
                    lines.append(" | ".join(f"{c}: {v}" for c, v in row.items() if pd.notna(v)))
                text = "\n".join(lines)
                if text.strip():
                    docs.append(Document(
                        page_content=text,
                        metadata={
                            "source": filename,
                            "sheet": sheet,
                            "row_start": start + 1,
                            "row_end": min(start + 10, len(df)),
                        }
                    ))
    return docs


def _chunk(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_documents(docs)


def _purge_source(source: str) -> int:
    """
    Remove every chunk previously stored for this document.

    Without this, re-uploading a file appends a second copy of every chunk, and
    retrieval then returns the same passage several times — which caps
    context_precision no matter how good the retriever is.
    """
    engine = create_engine(get_postgres_url())
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                DELETE FROM langchain_pg_embedding
                WHERE cmetadata->>'source' = :source
            """),
            {"source": source},
        )
        return result.rowcount or 0


def _chunk_ids(chunks: list[Document], source: str) -> list[str]:
    """
    Content-addressed ids so the same document always maps to the same rows.
    PGVector upserts on id conflict, making re-ingestion idempotent even if the
    delete above is skipped.
    """
    return [
        hashlib.sha256(f"{source}::{i}::{c.page_content}".encode("utf-8")).hexdigest()
        for i, c in enumerate(chunks)
    ]


def ingest_file(file_path: str, original_name: str | None = None) -> int:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        raw_docs = _load_pdf(file_path, original_name=original_name)
    elif ext in (".xlsx", ".xls"):
        raw_docs = _load_excel(file_path, original_name=original_name)
    elif ext == ".txt":
        raw_docs = _load_txt(file_path, original_name=original_name)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    chunks = _chunk(raw_docs)
    if not chunks:
        return 0

    source = original_name or Path(file_path).name
    removed = _purge_source(source)
    if removed:
        print(f"[ingest] replaced {removed} existing chunk(s) for {source}")

    store = _get_store()
    store.add_documents(chunks, ids=_chunk_ids(chunks, source))
    return len(chunks)
