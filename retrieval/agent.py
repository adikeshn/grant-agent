from .system_msg import CLASSIFIER_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from .retrieve import retrieve_chunk_rankings

from langchain_anthropic import ChatAnthropic
from anthropic import RateLimitError, APIStatusError
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
import json

def build_graph():
    llm = ChatAnthropic(model_name="claude-sonnet-4-6", timeout=None, stop=None)

    class GrantState(TypedDict):

        query: str
        query_type: str
        domain: str
        history: Annotated[list, add_messages]

        path: str
        top_k: int
        reasoning: str
        chunks: list[str]
        sources: list[dict]

        response: str
        error_msg: str


    def classify_retrieval(state: GrantState) -> dict:
        try:
            response = llm.invoke([
                SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT),
                HumanMessage(content=state["query"])
            ])


            if isinstance(response.content, str):
                res = json.loads(response.content)
        except RateLimitError:
            print("API rate limit error")
            return {"error_msg": "Rate limit exceeded, wait a bit so that my limit resets"}
        except APIStatusError as e:
            print(f"API error: {e.status_code} — {e.message}")
            return {"error_msg": f"API Error: {e.status_code} - {e.message}"}
        except Exception as e:
            return {"error_msg": f"Error during retrieval classification: {e}"}

        return res


    def chunk_retrieval(state: GrantState, config: RunnableConfig) -> dict:
        try:
            if "configurable" in config:
                bm25_indexes = config["configurable"]["bm25_indexes"]
            top_k_chunks = retrieve_chunk_rankings(bm25_indexes=bm25_indexes, domain=state["domain"],
                                    query_text=state["query"], top_dense=state["top_k"]*4, top_sparse=state["top_k"]*4,
                                    top_final=state["top_k"])

            return {"chunks": [chunk[1][1] for chunk in top_k_chunks], "sources": [chunk[2] for chunk in top_k_chunks]}


        except Exception as e:
            print("exception during chunk retrieval")
            return {"error_msg": f"Exception during chunk retrieval: {e}"}

    def invoke_llm(state: GrantState) -> dict:
        try:
            context = "\n\n".join(state["chunks"])
            messages = [SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT)]
            messages += state["history"]
            messages += [HumanMessage(content=
            f"""Question: {state["query"]}
            Retrieved award abstracts:
            {context}
            Answer the question using only the abstracts above as well as any prior char history.""")]
                
            response = llm.invoke(messages)
                
            return {"response": response.content, "history": [
                HumanMessage(content=state["query"]),
                AIMessage(content=response.content)
            ]}
        except Exception as e:
            print("error during llm invocation")
            return {"error_msg": f"exception during llm invocation: {e}"}


    def route_after_classify(state: GrantState) -> str:
        if "error_msg" in state or state.get("path", "") == "":
            return "END"
        elif state.get("path") == "chunk":
            return "chunk_retrieval"
        elif state.get("path") == "graph":
            return "graph_retrieval"
        else:
            return "END"
        
    def route_after_retrieval(state: GrantState) -> str:
        if "error_msg" in state or "chunks" not in state or "sources" not in state:
            return "END"
        return "invoke_llm"
    
    graph = StateGraph(GrantState)
    graph.add_node("classify_query", classify_retrieval)
    graph.add_node("chunk_retrieval", chunk_retrieval)
    graph.add_node("invoke_llm", invoke_llm)


    graph.add_edge(START, "classify_query")
    graph.add_conditional_edges(
        "classify_query",
        route_after_classify, {
            "END": END,
            "chunk_retrieval": "chunk_retrieval",
            "graph_retrieval": END # not implemented yet
        }
    )
    graph.add_conditional_edges(
        "chunk_retrieval",
        route_after_retrieval, {
            "END": END,
            "invoke_llm": "invoke_llm"
        }
    )

    return graph.compile()



