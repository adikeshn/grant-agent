import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.injest import run_injest_pipeline
from retrieval.agent import build_graph
from langchain_core.messages import HumanMessage, AIMessage

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from celery.result import AsyncResult

bm25_indexes: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bm25_indexes = bm25_indexes
    app.state.agent_graph = build_graph()
    yield
    bm25_indexes.clear()

api = FastAPI(lifespan=lifespan)

api.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class DomainRequest(BaseModel):
    name: str
    fetch_nsf: bool = False
    fetch_nih: bool = False
    keywords: list[str] = []
    date_from: str = ""
    date_to: str = ""
    max_results: int = 0

class MessageDict(BaseModel):
    role: str
    content: str
class QueryRequest(BaseModel):
    query: str
    domain: str
    history: list[MessageDict] = []

class QueryResponse(BaseModel):
    error: bool
    response: str
    sources: list[dict] = []
    history: list[dict]

class DomainResponse(BaseModel):
    task_id: str = ""
    status: str = "Pending"
    result: int = 0


@api.get("/")
def init():
    return "grant RAG project"

@api.post("/injest")
def add_domain(new_domain: DomainRequest) -> DomainResponse:
    task = run_injest_pipeline.delay(new_domain)
    return DomainResponse(task_id=task.id)

@api.get("/poll_injest")
def poll_injest_response(task_id: str = "") -> DomainResponse:
    task = AsyncResult(task_id)
    return DomainResponse(task_id=task_id, status=task.status, result=task.result)

def deserialize_messages(messages: list[MessageDict]):
    result = []
    for m in messages:
        if m.role == "user":
            result.append(HumanMessage(content=m.content))
        else:
            result.append(AIMessage(content=m.content))
    return result


@api.get("/query")
async def get_chunks(input: QueryRequest, req: Request) -> QueryResponse:
    result = await req.app.state.agent_graph.ainvoke(
        {"question": input.query, "domain": input.domain, "history": deserialize_messages(input.history)},
        config={"configurable": {"bm25_indexes": req.app.state.bm25_indexes}}
    )
    
    serialized_messages = [
        {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
        for m in result["history"]
    ]
    return QueryResponse(error=("error_msg" in result), 
                         response=(result.get("error_msg", result.get("response"))), history=serialized_messages)