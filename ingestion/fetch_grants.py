from api.api import DomainRequest

from .normalize import normalize

import xml.etree.ElementTree as ET
import requests
import yaml
from pathlib import Path
from datetime import date

def load_config(yaml_file_path: str):
    path = Path(f"config/{yaml_file_path}.yaml")
    with open(path) as f:
        return yaml.safe_load(f)
    
def fetch_nsf(inj_domain: DomainRequest) -> list[dict]:

    url = "http://api.nsf.gov/services/v1/awards.json"
    seen_ids = set()
    query_string = [f'"{keyword}"' for keyword in inj_domain.keywords]
    offset = 1
    awards = []
    max_results = inj_domain.max_results
    while len(awards) < max_results:
        curr_results = min(25, max_results - offset + 1)
        query_parameters = {
            "keyword": query_string,
            "startDateStart": inj_domain.date_from,
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

def fetch_nih(inj_domain: DomainRequest) -> list[dict]:
    date_from = inj_domain.date_from
    date_to = inj_domain.date_to or date.today().strftime("%Y-%m-%d")
    all_results = []
    seen_ids = set()
    payload = {
        "criteria": {
            'advanced_text_search': { 
                'operator': "and", 
                'search_field': "projecttitle,terms,abstracttext", 
                "search_text": ' OR '.join(f"\"{keyword}\"" for keyword in inj_domain.keywords)},
            "award_notice_date": {
                "from_date": date_from,
                "to_date": date_to
            },
        },
        "limit": inj_domain.max_results,
        "offset": 0,
        "fields": [
            "ProjectNum", "ProjectTitle", "AbstractText",
            "PrincipalInvestigator", "Organization",
            "AwardAmount", "ProjectStartDate", "ProjectEndDate",
            "AgencyIcAdmin"
        ]
    }

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


def fetch_grant_data(new_domain: DomainRequest):
    awards_nih, awards_nsf = []
    if new_domain.fetch_nih:
        awards_nih = fetch_nih(new_domain)
    if new_domain.fetch_nsf:
        awards_nsf = fetch_nsf(new_domain)

    all_awards = []
    for award in awards_nsf + awards_nih:
        n_award = normalize(award)
        if n_award is None:
            raise Exception("Error with normalizing")
        n_award["domain"] = new_domain.name
        all_awards.append(n_award)

    return all_awards, new_domain.name



