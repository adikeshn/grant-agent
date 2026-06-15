from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ingestion.injest import run_injest_pipeline
from celery.result import AsyncResult

api = FastAPI()
api.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


bm25_indexes = []

class Domain(BaseModel):
    name: str
    fetch_nsf: bool = False
    fetch_nih: bool = False
    keywords: list[str] = []
    date_from: str = ""
    date_to: str = ""
    max_results: int = 0


class TaskResponse(BaseModel):
    task_id: str = ""
    status: str = "Pending"
    result: int = 0


@api.get("/")
def init():
    return "grant RAG project"

@api.post("/injest")
def add_domain(new_domain: Domain) -> TaskResponse:
    task = run_injest_pipeline.delay(new_domain)
    return TaskResponse(task_id=task.id)

@api.get("/poll")
def poll_injest_response(task_id: str = "") -> TaskResponse:
    task = AsyncResult(task_id)
    return TaskResponse(task_id=task_id, status=task.status, result=task.result)

