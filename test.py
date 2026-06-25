from ingestion.fetch_grants import fetch_grant_data
from ingestion.write_to_graph import connect_neo4j_db, ingest_graph_nodes
from api.schemas import DomainRequest
from ingestion.injest import gen_topics_methods

def test_connect():
    neo4j_index = connect_neo4j_db()
    neo4j_index.verify_connectivity()

def test_graph():
    inj_domain = DomainRequest(name="reinforcement learning", fetch_nih=True, fetch_nsf=True,
                               keywords=["reinforcement learning", "deep reinforcement learning"
    ,"agent"
    , "inverse reinforcement learning"
    , "Markov decision process"
    , "policy gradient"
    , "AI"], date_to="", max_results=20)
    neo4j_index = connect_neo4j_db()
    neo4j_index.verify_connectivity()
    data, domain = fetch_grant_data(inj_domain)
    gen_topics_methods(data)
    print("injesting graph")
    ingest_graph_nodes(data, neo4j_index)
test_graph()