import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

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
    with neo4j_driver.session() as session:
        for award in awards:
            session.execute_write(_write_award_subgraph, award)


def _write_award_subgraph(tx, award: dict):
    domain = award["domain"]

    # Create Domain node and link to Award in one go
    tx.run("""
        MERGE (dom:Domain {name: $domain})
        MERGE (a:Award {award_id: $award_id})
        SET a.title             = $title,
            a.abstract          = $abstract,
            a.amount            = $amount,
            a.year              = $year,
            a.agency            = $agency,
            a.date_awarded      = $date_awarded,
            a.date_expires      = $date_expires,
            a.duration_months   = $duration_months,
            a.is_early_career   = $is_early_career,
            a.is_collaborative  = $is_collaborative,
            a.source_url        = $source_url,
            a.program_name      = $program_name,
            a.ingested_at       = $ingested_at
        MERGE (dom)-[:CONTAINS]->(a)
    """,
        domain=domain,
        award_id=award["award_id"],
        title=award["title"],
        abstract=award["abstract"],
        amount=award["amount"],
        year=award["award_year"],
        agency=award["agency"],
        date_awarded=award["date_awarded"],
        date_expires=award["date_expires"],
        duration_months=award["award_duration_months"],
        is_early_career=award["is_early_career"],
        is_collaborative=award["is_collaborative"],
        source_url=award["source_url"],
        program_name=award["program_name"],
        ingested_at=award["ingested_at"],
    )

    # Everything else stays exactly the same — no domain param needed anywhere below
    if award.get("pi_name"):
        tx.run("""
            MERGE (p:PI {name: $pi_name})
            WITH p
            MATCH (a:Award {award_id: $award_id})
            MERGE (p)-[:RECEIVED]->(a)
        """, pi_name=award["pi_name"], award_id=award["award_id"])

    for co_pi in award.get("co_pi_names", []):
        if co_pi:
            tx.run("""
                MERGE (p:PI {name: $pi_name})
                WITH p
                MATCH (a:Award {award_id: $award_id})
                MERGE (p)-[:CO_RECEIVED]->(a)
            """, pi_name=co_pi, award_id=award["award_id"])

    if award.get("institution"):
        tx.run("""
            MERGE (i:Institution {name: $institution})
            SET i.state = $state
            WITH i
            MATCH (a:Award {award_id: $award_id})
            MERGE (a)-[:HOSTED_AT]->(i)
        """,
            institution=award["institution"],
            state=award.get("institution_state", ""),
            award_id=award["award_id"],
        )

        if award.get("pi_name"):
            tx.run("""
                MATCH (p:PI {name: $pi_name})
                MATCH (i:Institution {name: $institution})
                MERGE (p)-[:AFFILIATED_WITH]->(i)
            """, pi_name=award["pi_name"], institution=award["institution"])

    if award.get("program_directorate"):
        tx.run("""
            MERGE (d:Directorate {name: $directorate, agency: $agency})
            WITH d
            MATCH (a:Award {award_id: $award_id})
            MERGE (a)-[:FUNDED_BY]->(d)
        """,
            directorate=award["program_directorate"],
            agency=award["agency"],
            award_id=award["award_id"],
        )

    for topic in award.get("topics", []):
        if topic:
            tx.run("""
                MERGE (t:Topic {label: $topic})
                WITH t
                MATCH (a:Award {award_id: $award_id})
                MERGE (a)-[:TAGGED_WITH]->(t)
            """, topic=topic, award_id=award["award_id"])

    for method in award.get("methods", []):
        if method:
            tx.run("""
                MERGE (m:Method {name: $method})
                WITH m
                MATCH (a:Award {award_id: $award_id})
                MERGE (a)-[:USES_METHOD]->(m)
            """, method=method, award_id=award["award_id"])


