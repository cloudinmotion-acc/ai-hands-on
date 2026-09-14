from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import tempfile, os, shutil, traceback
from dotenv import load_dotenv

from schemas import QueryRequest, QueryResponse
from ingest import ingest_file
from query import answer

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
    if ext not in (".pdf", ".xlsx", ".xls"):
        raise HTTPException(400, "Only PDF and Excel files are supported.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        count = ingest_file(tmp_path)
    except Exception as e:
        os.unlink(tmp_path)
        raise
    os.unlink(tmp_path)

    return {"filename": file.filename, "chunks_stored": count}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    return answer(req)


@app.get("/health")
def health():
    return {"status": "ok"}
