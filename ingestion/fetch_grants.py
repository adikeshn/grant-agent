from .normalize import normalize
import requests
from datetime import datetime, date


def fetch_nsf(inj_domain: dict) -> list[dict]:
    url = "http://api.nsf.gov/services/v1/awards.json"
    seen_ids = set()
    awards = []
    max_results = inj_domain["max_results"]

    def nsf_quote(keyword: str) -> str:
        return f'"{keyword}"' if " " in keyword else keyword

    query_string = " OR ".join(nsf_quote(k) for k in inj_domain["keywords"][0:min(len(inj_domain["keywords"]), 3)])

    def to_nsf_date(date_str: str) -> str:
        if not date_str:
            return ""
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            return d.strftime("%m/%d/%Y")
        except ValueError:
            return date_str

    date_from = to_nsf_date(inj_domain["date_from"]) or "01/01/2000"
    offset = 0

    while len(awards) < max_results:
        rpp = min(25, max_results - len(awards))

        query_parameters = {
            "keyword": query_string,
            "startDateStart": date_from,
            "rpp": rpp,
            "offset": offset,
        }

        response = requests.get(url, params=query_parameters)
        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            break

        data = response.json()

        if "serviceNotification" in data.get("response", {}):
            print(f"NSF API error: {data['response']['serviceNotification']}")
            break

        award_list = data.get("response", {}).get("award", [])
        if not award_list:
            print("no more awards")
            break

        for award in award_list:
            proj_id = award.get("id", "")
            if proj_id and proj_id not in seen_ids:
                seen_ids.add(proj_id)
                awards.append(award)

        offset += rpp

    return awards


def fetch_nih(inj_domain: dict) -> list[dict]:
    date_from = inj_domain["date_from"]
    date_to = inj_domain["date_to"]
    all_results = []
    seen_ids = set()

    payload = {
        "criteria": {
            "advanced_text_search": {
                "operator": "and",
                "search_field": "projecttitle,terms,abstracttext",
                "search_text": " OR ".join(f'"{k}"' for k in inj_domain["keywords"]),
            },
            "award_notice_date": {
                "from_date": date_from,
                "to_date": date_to,
            },
        },
        "limit": inj_domain["max_results"],
        "offset": 0,
        "fields": [
            "ProjectNum", "ProjectTitle", "AbstractText",
            "PrincipalInvestigator", "Organization",
            "AwardAmount", "ProjectStartDate", "ProjectEndDate",
            "AgencyIcAdmin",
        ],
    }

    response = requests.post(
        "https://api.reporter.nih.gov/v2/projects/search",
        json=payload,
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


def fetch_grant_data(inj_domain: dict) -> tuple[list[dict], str]:
    date_to = inj_domain["date_to"] or date.today().strftime("%Y-%m-%d")
    inj_domain = {**inj_domain, "date_to": date_to}

    awards_nih, awards_nsf = [], []
    if inj_domain["fetch_nih"]:
        awards_nih = fetch_nih(inj_domain)
    if inj_domain["fetch_nsf"]:
        awards_nsf = fetch_nsf(inj_domain)

    print(f"fetched NIH {len(awards_nih)}")
    print(f"fetched NSF {len(awards_nsf)}")

    all_awards = []
    for award in awards_nsf + awards_nih:
        n_award = normalize(award)
        if n_award is None:
            raise Exception("Error with normalizing")
        n_award["domain"] = inj_domain["name"]
        all_awards.append(n_award)

    return all_awards, inj_domain["name"]