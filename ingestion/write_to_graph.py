import os
from dotenv import load_dotenv
from neo4j import GraphDatabase, TrustCustomCAs

load_dotenv()               
instance_id = os.getenv("GRAPH_ID")
neo4j_password = os.getenv("GRAPH_PASSWORD")

def connect_neo4j_db():
    
    if not neo4j_password or not instance_id:
        raise ValueError("Missing GRAPH_ID or GRAPH_PASSWORD")
    
    URI = f"neo4j+s://{instance_id}.databases.neo4j.io"
    AUTH = (instance_id, neo4j_password)
    
    
    return GraphDatabase.driver(
        URI,
        auth=AUTH,
    )

def ingest_graph_nodes(awards: list[dict], neo4j_driver):
    """
    awards: list of normalized award dicts, each containing:
        award_id, title, abstract, amount, year, agency, domain,
        pi_name, institution, city, state, directorate,
        topics (list[str]), methods (list[str])
    """
    with neo4j_driver.session() as session:
        for award in awards:
            session.execute_write(_write_award_subgraph, award)


def _write_award_subgraph(tx, award: dict):
    tx.run("""
        MERGE (a:Award {award_id: $award_id})
        SET a.title      = $title,
            a.abstract   = $abstract,
            a.amount     = $amount,
            a.year       = $year,
            a.agency     = $agency,
            a.domain     = $domain
    """, **{k: award[k] for k in
            ["award_id", "title", "abstract", "amount", "year", "agency", "domain"]})

    tx.run("""
        MERGE (p:PI {name: $pi_name})
        WITH p
        MATCH (a:Award {award_id: $award_id})
        MERGE (p)-[:RECEIVED]->(a)
    """, pi_name=award["pi_name"], award_id=award["award_id"])

    tx.run("""
        MERGE (i:Institution {name: $institution})
        SET i.city  = $city,
            i.state = $state
        WITH i
        MATCH (a:Award  {award_id: $award_id})
        MATCH (p:PI     {name:     $pi_name})
        MERGE (a)-[:HOSTED_AT]->(i)
        MERGE (p)-[:AFFILIATED_WITH]->(i)
    """, institution=award["institution"],
         city=award.get("city", ""),
         state=award.get("state", ""),
         award_id=award["award_id"],
         pi_name=award["pi_name"])

    tx.run("""
        MERGE (d:Directorate {name: $directorate, agency: $agency})
        WITH d
        MATCH (a:Award {award_id: $award_id})
        MERGE (a)-[:FUNDED_BY]->(d)
    """, directorate=award["directorate"],
         agency=award["agency"],
         award_id=award["award_id"])

    for topic in award.get("topics", []):
        tx.run("""
            MERGE (t:Topic {label: $topic})
            WITH t
            MATCH (a:Award {award_id: $award_id})
            MERGE (a)-[:TAGGED_WITH]->(t)
        """, topic=topic, award_id=award["award_id"])

    for method in award.get("methods", []):
        tx.run("""
            MERGE (m:Method {name: $method})
            WITH m
            MATCH (a:Award {award_id: $award_id})
            MERGE (a)-[:USES_METHOD]->(m)
        """, method=method, award_id=award["award_id"])
    