import xml.etree.ElementTree as ET
import time
import ssl
import certifi
import requests
import json
import yaml
from pathlib import Path
from datetime import date
from normalize import normalize
from chunk import chunk_award

def load_config(yaml_file_path: str):
    path = Path(f"config/{yaml_file_path}.yaml")
    with open(path) as f:
        return yaml.safe_load(f)
    
def fetch_nsf(config: dict):

    url = "http://api.nsf.gov/services/v1/awards.json"
    seen_ids = set()
    query_string = [f'"{keyword}"' for keyword in config["keywords"]]
    offset = 1
    awards = []
    max_results = config["max_results"]
    while len(awards) < max_results:
        curr_results = min(25, max_results - offset + 1)
        query_parameters = {
            "keyword": query_string,
            "startDateStart": config["date_from"],
            "rpp": curr_results,       
            "offset": offset     
        }

        response = requests.get(url, params=query_parameters)
        if response.status_code == 200:
            data = response.json()
            award_list = data.get("response", {}).get("award", [])
            if not award_list:
                print("no more awards")
                break
            else:
                for award in award_list:
                    proj_id = award.get("id", "")
                    if proj_id and proj_id not in seen_ids:
                        seen_ids.add(proj_id)
                        awards.append(award)
                offset += curr_results
            
        else:
            print(f"Error {response.status_code}: {response.text}")
            break
    return awards

def fetch_nih(source: dict, last_run: str | None = None) -> list[dict]:
    date_from = last_run or source["date_from"]
    date_to = source.get("date_to") or date.today().strftime("%Y-%m-%d")
    all_results = []
    seen_ids = set()
    payload = {
        "criteria": {
            'advanced_text_search': { 
                'operator': "and", 
                'search_field': "projecttitle,terms,abstracttext", 
                "search_text": ' OR '.join(f"\"{keyword}\"" for keyword in source["keywords"])},
            "award_notice_date": {
                "from_date": date_from,
                "to_date": date_to
            },
        },
        "limit": source["max_results"],
        "offset": 0,
        "fields": [
            "ProjectNum", "ProjectTitle", "AbstractText",
            "PrincipalInvestigator", "Organization",
            "AwardAmount", "ProjectStartDate", "ProjectEndDate",
            "AgencyIcAdmin"
        ]
    }

    if source.get("institutes"):
        payload["criteria"]["agencies"] = source["institutes"]

    response = requests.post(
        "https://api.reporter.nih.gov/v2/projects/search",
        json=payload
    )
    if response.status_code == 200:
        results = response.json().get("results", [])

        for result in results:
            pid = result.get("project_serial_num", "")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                all_results.append(result)
    else:
        print(f"Error {response.status_code}: {response.text}")

    return all_results


def fetch_grant_data(yaml_filename: str):
    yaml = load_config(yaml_filename)
    awards_nsf = fetch_nsf(yaml["sources"])
    awards_nih = fetch_nih(yaml["sources"])

    all_awards = []
    for award in awards_nsf + awards_nih:
        n_award = normalize(award)
        if n_award is None:
            raise Exception("Error with normalizing")
        n_award["domain"] = yaml["name"]
        all_awards.append(n_award)

    return all_awards, yaml["name"]



