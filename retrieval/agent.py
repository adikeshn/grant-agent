from .system_msg import CLASSIFIER_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT, GENERATE_CYPHER_QUERY_PROMPT
from .retrieve import retrieve_chunk_rankings, get_candidate_entities, run_cypher_queries

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
import json
from json import JSONDecodeError
import os
from dotenv import load_dotenv
import google.generativeai.generative_models as genai
from google.generativeai.client import configure

load_dotenv()

def build_graph():
    configure(api_key=os.getenv("GEMINI_API_KEY"))
    gemini_model = genai.GenerativeModel(model_name="gemini-2.5-flash-lite")
    llm_sonnet = ChatAnthropic(model_name="claude-sonnet-4-6", timeout=None, stop=None)
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
            prompt = f"{CLASSIFIER_SYSTEM_PROMPT}\n\n{state['query']}"
            response = gemini_model.generate_content(prompt)

            content = response.text
            if not content:
                return {"error_msg": "Classifier returned no text content"}

            clean = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            res = json.loads(clean)
        
        except JSONDecodeError as e:
            return {"error_msg": f"Classifier returned invalid JSON: {e}"}
        except Exception as e:
            err = str(e).lower()
            if "quota" in err or "rate" in err or "429" in err:
                print("API rate limit error")
                return {"error_msg": "Rate limit exceeded, wait a bit so that my limit resets"}
            if "invalid" in err or "api" in err:
                print(f"API error: {e}")
                return {"error_msg": f"API Error: {e}"}
            return {"error_msg": f"Error during retrieval classification: {e}"}

        return res


    def chunk_retrieval(state: GrantState, config: RunnableConfig) -> dict:
        try:
            if "configurable" in config:
                bm25_indexes = config["configurable"]["bm25_indexes"]
                pinecone_index = config["configurable"]["pinecone_index"]
                supabase_conn = config["configurable"]["supabase_conn"]
            top_k_chunks = retrieve_chunk_rankings(bm25_indexes=bm25_indexes, pinecone_index=pinecone_index, supabase_conn=supabase_conn, domain=state["domain"],
                                    query_text=state["query"], top_dense=state["top_k"]*4, top_sparse=state["top_k"]*4,
                                    top_final=state["top_k"])
            
            return {"chunks": [chunk[1][1] for chunk in top_k_chunks], "sources": [chunk[2] for chunk in top_k_chunks]}


        except Exception as e:
            print("exception during chunk retrieval")
            return {"error_msg": f"Exception during chunk retrieval: {e}"}

    def graph_retrieval(state: GrantState, config: RunnableConfig) -> dict:
        try:
            if "configurable" in config:
                neo4j_driver = config["configurable"]["neo4j_driver"]

            user_query = state["query"]
            domain = state["domain"]

            candidates = get_candidate_entities(neo4j_driver, user_query, domain)

            candidate_context = "\n".join([
                f"{entity_type}: {', '.join(names)}"
                for entity_type, names in candidates.items()
                if names
            ])
            prompt = GENERATE_CYPHER_QUERY_PROMPT(domain, candidate_context, user_query)
            response = gemini_model.generate_content(prompt)
            results, structured = run_cypher_queries(response, domain, neo4j_driver)

            sources = []
            for query_result in structured:
                for row in query_result.get("rows", []):
                    title = row.get("title") or row.get("a.title")
                    if title and title not in sources:
                        sources.append(title)

            return {"chunks": results, "sources": sources}
        except Exception as e:
            print("exception during graph retrieval")
            return {"error_msg": f"Exception during graph retrieval: {e}"}

    def invoke_llm(state: GrantState) -> dict:
        try:
            context = "\n\n".join(state["chunks"])
            messages = [SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT)]
            messages += state["history"]
            messages += [HumanMessage(content=
            f"""Question: {state["query"]}
            Retrieved award abstracts:
            {context}
            Answer the question using only the abstracts above as well as any prior chat history.""")]
                
            response = llm_sonnet.invoke(messages)
                
            return {"response": response.content, "history": [
                HumanMessage(content=state["query"]),
                AIMessage(content=response.content)
            ]}
        except Exception as e:
            print("error during llm invocation")
            return {"error_msg": f"exception during llm invocation: {e}"}


    def route_after_classify(state: GrantState) -> str:
        print("chosen path: " + state.get("path", "N/A"))
        print("reasoning: " + state.get("reasoning", "N/A"))
        if "error_msg" in state or state.get("path", "") == "":
            return "END"
        elif state.get("path") == "chunk":
            return "chunk_retrieval"
        elif state.get("path") == "graph":
            return "graph_retrieval"
        else:
            return "END"
        
    def route_after_retrieval(state: GrantState) -> str:
        if "error_msg" in state or "chunks" not in state:
            return "END"
        return "invoke_llm"
    
    graph = StateGraph(GrantState)
    graph.add_node("classify_query", classify_retrieval)
    graph.add_node("chunk_retrieval", chunk_retrieval)
    graph.add_node("invoke_llm", invoke_llm)
    graph.add_node("graph_retrieval", graph_retrieval)

    graph.add_edge(START, "classify_query")
    graph.add_conditional_edges(
        "classify_query",
        route_after_classify, {
            "END": END,
            "chunk_retrieval": "chunk_retrieval",
            "graph_retrieval": "graph_retrieval"
        }
    )
    graph.add_conditional_edges(
        "chunk_retrieval",
        route_after_retrieval, {
            "END": END,
            "invoke_llm": "invoke_llm"
        }
    )

    graph.add_conditional_edges(
        "graph_retrieval",
        route_after_retrieval, {
            "END": END,
            "invoke_llm": "invoke_llm"
        }
    )

    return graph.compile()



