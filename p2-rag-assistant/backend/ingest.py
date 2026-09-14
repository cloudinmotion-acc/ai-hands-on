"""
Ingest pipeline: document -> chunks -> embeddings -> pgvector
Runs once per document upload.
"""

from dotenv import load_dotenv
import os
from pathlib import Path

import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document
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


def _load_pdf(path: str) -> list[Document]:
    loader = PyPDFLoader(path)
    return loader.load()


def _load_excel(path: str) -> list[Document]:
    docs = []
    xf = pd.ExcelFile(path)
    filename = Path(path).name
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


def ingest_file(file_path: str) -> int:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        raw_docs = _load_pdf(file_path)
    elif ext in (".xlsx", ".xls"):
        raw_docs = _load_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    chunks = _chunk(raw_docs)
    store = _get_store()
    store.add_documents(chunks)
    return len(chunks)
