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
CORS(app)  # Allow requests from any origin (your SpotterBoard HTML file)

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

    # ── SECTION 3a: PARSE THE TABLE ───────────────────────────────────
    # OurLads roster table columns (0-indexed):
    # 0=Num, 1=Name, 2=Pos, 3=Ht, 4=Wt, 5=Age, 6=Exp, 7=College, 8=DraftYr, 9=Rd
    draft_data = {}

    table = soup.find("table", {"id": "roster-table"}) or soup.find("table")
    if not table:
        return jsonify({"error": "Could not find roster table", "url": url}), 502

    rows = table.find_all("tr")
    for row in rows[1:]:  # skip header row
        cells = row.find_all("td")
        if len(cells) < 10:
            continue

        name  = cells[1].get_text(strip=True)
        year  = cells[8].get_text(strip=True)
        round_ = cells[9].get_text(strip=True)

        if not name:
            continue

        # Clean up — OurLads uses "FA" for undrafted free agents
        if year in ("", "FA", "0", "—") or round_ in ("", "FA", "0", "—"):
            draft_data[name] = {"year": "UDFA", "round": ""}
        else:
            draft_data[name] = {"year": year, "round": round_}

    return jsonify({
        "team":  abbr,
        "count": len(draft_data),
        "draft": draft_data,
    })


# ── SECTION 4: RUN ────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
