# ============================================================
#  SpotterBoard Backend — Flask
#  Proxies OurLads roster pages and returns draft data as JSON.
#  Deploy to Railway. Requires Python 3.9+
# ============================================================

from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=False)

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

# ── SECTION 1: TEAM ABBREVIATION MAP ──────────────────────────────────
# Maps your app's abbreviations to OurLads URL slugs
OURLADS_MAP = {
    "ARI": "ARZ", "ATL": "ATL", "BAL": "BAL", "BUF": "BUF",
    "CAR": "CAR", "CHI": "CHI", "CIN": "CIN", "CLE": "CLE",
    "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GB":  "GB",
    "HOU": "HOU", "IND": "IND", "JAX": "JAX", "KC":  "KC",
    "LAC": "LAC", "LAR": "LAR", "LV":  "LV",  "MIA": "MIA",
    "MIN": "MIN", "NE":  "NE",  "NO":  "NO",  "NYG": "NYG",
    "NYJ": "NYJ", "PHI": "PHI", "PIT": "PIT", "SEA": "SEA",
    "SF":  "SF",  "TB":  "TB",  "TEN": "TEN", "WAS": "WAS",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── SECTION 2: HEALTH CHECK ───────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "SpotterBoard Backend"})


# ── SECTION 3: DRAFT DATA ENDPOINT ───────────────────────────────────
# Returns a dict of { "Player Name": { "year": "2021", "round": "1" }, ... }
# Called by the frontend as: /api/draft/KC
@app.route("/api/draft/<abbr>")
def draft(abbr):
    abbr = abbr.upper()
    slug = OURLADS_MAP.get(abbr)
    if not slug:
        return jsonify({"error": f"Unknown team: {abbr}"}), 404

    url = f"https://www.ourlads.com/nfldepthcharts/roster/{slug}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    soup = BeautifulSoup(resp.text, "html.parser")

    # Confirmed OurLads columns (0-indexed):
    # 0=#, 1=Player, 2=Pos, 3=DOB, 4=Age, 5=HT, 6=WT, 7=School, 8=Orig.Team, 9=Draft Status, 10=NFL Exp
    # Draft Status examples: "23 01 031" = 2023 Rd1 Pk31 | "25 CFA" = undrafted | "SFA" = street FA
    draft_data = {}

    table = soup.find("table", {"id": "roster-table"}) or soup.find("table")
    if not table:
        return jsonify({"error": "Could not find roster table", "url": url}), 502

    rows = table.find_all("tr")
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 10:
            continue

        name = cells[1].get_text(strip=True)
        raw  = cells[9].get_text(strip=True)  # e.g. "23 01 031" or "25 CFA" or "SFA"

        if not name or name == "Active Players":
            continue

        parts = raw.split()
        # Drafted: first two parts are both numbers e.g. "23 01 031"
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            yy = int(parts[0])
            yr = str(2000 + yy) if yy < 50 else str(1900 + yy)
            rd = str(int(parts[1]))  # "01" -> "1"
            draft_data[name] = {"year": yr, "round": rd}
        else:
            # CFA, SFA, or anything else = undrafted
            draft_data[name] = {"year": "UDFA", "round": ""}

    return jsonify({
        "team":  abbr,
        "count": len(draft_data),
        "draft": draft_data,
    })


# ── SECTION 3b: DEBUG ENDPOINT ───────────────────────────────────────
# Visit /api/debug/KC to see raw column values — remove after testing
@app.route("/api/debug/<abbr>")
def debug(abbr):
    abbr = abbr.upper()
    slug = OURLADS_MAP.get(abbr)
    if not slug:
        return jsonify({"error": f"Unknown team: {abbr}"}), 404
    url = f"https://www.ourlads.com/nfldepthcharts/roster/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "roster-table"}) or soup.find("table")
    if not table:
        return jsonify({"error": "no table found"}), 502
    rows = table.find_all("tr")
    # Return first 5 rows with all cell values
    sample = []
    for row in rows[:6]:
        cells = row.find_all(["td","th"])
        sample.append([c.get_text(strip=True) for c in cells])
    return jsonify({"headers": sample[0], "rows": sample[1:], "total_rows": len(rows)})



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
