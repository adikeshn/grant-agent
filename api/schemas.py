from pydantic import BaseModel


class DomainRequest(BaseModel):
    name: str
    fetch_nsf: bool = False
    fetch_nih: bool = False
    keywords: list[str] = []
    date_from: str = ""
    date_to: str = ""
    max_results: int = 0

class DomainNamesResponse(BaseModel):
    unique_domains: list[str] = []

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
    sources: list = []
    history: list[dict]

class DomainResponse(BaseModel):
    task_id: str = ""
    status: str = "Pending"
    result: int = 0