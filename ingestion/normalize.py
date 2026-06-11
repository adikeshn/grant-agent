from datetime import datetime

# --- Utility functions ---

def normalize_date(date_str: str) -> str:
    if not date_str:
        return ""
    formats = [
        "%m/%d/%Y",           
        "%Y-%m-%dT%H:%M:%S",  
        "%Y-%m-%d",           
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    print(f"Warning: could not parse date '{date_str}'")
    return ""


def normalize_amount(value) -> int:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError):
        return 0


def normalize_name(name: str) -> str:
    if not name:
        return ""
    return name.strip().title()


def normalize_institution(name: str) -> str:
    if not name:
        return ""
    return name.strip().title()


def compute_duration(date_from: str, date_to: str) -> int:
    if not date_from or not date_to:
        return 0
    try:
        d1 = datetime.strptime(date_from, "%Y-%m-%d")
        d2 = datetime.strptime(date_to, "%Y-%m-%d")
        return max(0, (d2.year - d1.year) * 12 + (d2.month - d1.month))
    except ValueError:
        return 0


def extract_year(date_str: str) -> int:
    if not date_str:
        return 0
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").year
    except ValueError:
        return 0



def normalize(raw: dict) -> dict | None:
    if "id" in raw:
        return normalize_nsf(raw)
    elif "project_num" in raw:
        return normalize_nih(raw)
    else:
        print(f"Unknown record format, skipping: {list(raw.keys())}")
        return None


def normalize_nsf(raw: dict) -> dict:
    program = raw.get("program", "")

    pi_raw = raw.get("pi", [])
    pi_name = ""
    if pi_raw:
        parts = pi_raw[0].rsplit(" ", 1)
        pi_name = parts[0] if parts else ""

    date_awarded = normalize_date(raw.get("date", ""))
    date_expires = normalize_date(raw.get("expDate", ""))

    return {
        "award_id":              raw.get("id", ""),
        "agency":                "nsf",
        "title":                 raw.get("title", "").strip(),
        "abstract":              raw.get("abstractText", "").strip(),
        "date_awarded":          date_awarded,
        "date_expires":          date_expires,
        "amount":                normalize_amount(raw.get("estimatedTotalAmt", 0)),
        "program_directorate":   raw.get("dirAbbr", ""),
        "program_division":      raw.get("divAbbr", ""),
        "program_name":          raw.get("fundProgramName", ""),
        "pi_name":               normalize_name(raw.get("pdPIName", "") or pi_name),
        "pi_email":              raw.get("piEmail", "").strip().lower(),
        "co_pi_names":           [],
        "institution":           normalize_institution(raw.get("awardeeName", "")),
        "institution_state":     raw.get("awardeeStateCode", ""),
        "award_duration_months": compute_duration(date_awarded, date_expires),
        "award_year":            extract_year(date_awarded),
        "is_early_career":       "CAREER" in program.upper(),
        "is_collaborative":      False,
        "source_url":            f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={raw.get('id', '')}",
        "ingested_at":           datetime.utcnow().isoformat(),
    }


def normalize_nih(raw: dict) -> dict:
    pis = raw.get("principal_investigators", [])
    contact_pi = next((p for p in pis if p.get("is_contact_pi")), pis[0] if pis else {})
    co_pis = [p.get("full_name", "") for p in pis if not p.get("is_contact_pi")]

    agency_ic = raw.get("agency_ic_admin", {})
    org = raw.get("organization", {})

    date_awarded = normalize_date(raw.get("award_notice_date", ""))
    date_expires = normalize_date(raw.get("project_end_date", ""))

    return {
        "award_id":              raw.get("project_num", ""),
        "agency":                "nih",
        "title":                 raw.get("project_title", "").strip(),
        "abstract":              raw.get("abstract_text", "").strip(),
        "date_awarded":          date_awarded,
        "date_expires":          date_expires,
        "amount":                normalize_amount(raw.get("award_amount", 0)),
        "program_directorate":   agency_ic.get("abbreviation", ""),
        "program_division":      raw.get("activity_code", ""),
        "program_name":          raw.get("opportunity_number", ""),
        "pi_name":               normalize_name(contact_pi.get("full_name", "")),
        "pi_email":              "",
        "co_pi_names":           [normalize_name(n) for n in co_pis],
        "institution":           normalize_institution(org.get("org_name", "")),
        "institution_state":     org.get("org_state", ""),
        "award_duration_months": compute_duration(date_awarded, date_expires),
        "award_year":            extract_year(date_awarded),
        "is_early_career":       raw.get("activity_code", "").startswith("K"),
        "is_collaborative":      len(co_pis) > 0,
        "source_url":            raw.get("project_detail_url", ""),
        "ingested_at":           datetime.utcnow().isoformat(),
    }