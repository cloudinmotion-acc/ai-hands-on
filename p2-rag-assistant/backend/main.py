from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import tempfile, os, shutil, traceback
from dotenv import load_dotenv
from sqlalchemy import create_engine, text as sql_text

from schemas import QueryRequest, QueryResponse
from ingest import ingest_file
from query import answer
from db import get_postgres_url

load_dotenv()

app = FastAPI(title="P2 RAG Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"\n[ERROR] {request.method} {request.url}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".pdf", ".xlsx", ".xls", ".txt"):
        raise HTTPException(400, "Only PDF, Excel, and TXT files are supported.")

    # mkstemp gives an explicit fd we close before handing the path to ingest.
    # NamedTemporaryFile keeps a Windows exclusive lock even after the with-block
    # exits, causing WinError 32 when pandas tries to open the same file.
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            shutil.copyfileobj(file.file, f)
        # fd is now fully closed — no lock held when ingest_file opens it
        count = ingest_file(tmp_path, original_name=file.filename)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    os.unlink(tmp_path)

    return {"filename": file.filename, "chunks_stored": count}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    return answer(req)


@app.get("/sources")
async def list_sources():
    """Return every distinct source document currently stored in pgvector."""
    engine = create_engine(get_postgres_url())
    with engine.connect() as conn:
        rows = conn.execute(sql_text(
            "SELECT cmetadata->>'source' AS name, COUNT(*) AS chunks "
            "FROM langchain_pg_embedding "
            "GROUP BY name ORDER BY name"
        )).fetchall()
    return {"sources": [{"name": row[0], "chunks": int(row[1])} for row in rows]}


@app.delete("/sources")
async def clear_sources():
    """Delete all embeddings from pgvector. Destructive — use for demo resets."""
    engine = create_engine(get_postgres_url())
    with engine.begin() as conn:
        result = conn.execute(sql_text("DELETE FROM langchain_pg_embedding"))
        deleted = result.rowcount or 0
    return {"deleted": deleted}


@app.get("/health")
def health():
    return {"status": "ok"}
