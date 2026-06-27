from ingestion.fetch_grants import fetch_grant_data
from ingestion.write_to_graph import connect_neo4j_db, ingest_graph_nodes
from api.schemas import DomainRequest
from ingestion.injest import gen_topics_methods, run_injest_pipeline

def test_connect():
    neo4j_index = connect_neo4j_db()
    neo4j_index.verify_connectivity()

def test_graph():
    inj_domain = DomainRequest(name="reinforcement learning", fetch_nih=False, fetch_nsf=True,
                               keywords=["reinforcement learning"], 
                               date_to="", max_results=60).model_dump()
    run_injest_pipeline(inj_domain)
test_graph()