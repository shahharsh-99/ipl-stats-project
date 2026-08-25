import csv
import os
import sys
from functools import wraps
from pathlib import Path
from flask import Flask, request, jsonify

# Determine data paths relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

MATCHES_PATH = DATA_DIR / "matches.csv"
DELIVERIES_PATH = DATA_DIR / "deliveries.csv"

# Configurable Bearer Token (can be customized via environment variable API_BEARER_TOKEN)
API_BEARER_TOKEN = os.environ.get("API_BEARER_TOKEN")

# Global data caches
match_year = {}       # match_id -> season
match_winner = {}     # match_id -> winner
match_date = {}       # match_id -> date
available_seasons = [] # sorted list of distinct seasons
season_player_stats = {} # season -> { 'runs': {player: runs}, 'teams': {player: team} }
season_winners = {}   # season -> series_winner


def load_dataset():
    """Load and index matches.csv and deliveries.csv into memory for fast querying."""
    global match_year, match_winner, match_date, available_seasons, season_player_stats, season_winners

    if not MATCHES_PATH.exists():
        raise FileNotFoundError(f"Matches CSV file not found at: {MATCHES_PATH}")
    if not DELIVERIES_PATH.exists():
        raise FileNotFoundError(f"Deliveries CSV file not found at: {DELIVERIES_PATH}")

    # 1. Load matches
    with open(MATCHES_PATH, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            match_id = row["id"]
            match_year[match_id] = row["season"]
            match_winner[match_id] = row["winner"]
            match_date[match_id] = row["date"]

    seasons_set = set(match_year.values())
    available_seasons = sorted(list(seasons_set))

    # 2. Compute series winner per season (winner of the latest match by date in that season)
    for season in available_seasons:
        season_match_ids = [mid for mid in match_year if match_year[mid] == season]
        latest_match_id = None
        latest_date = None
        for mid in season_match_ids:
            this_date = match_date[mid]
            if latest_date is None or this_date > latest_date:
                latest_date = this_date
                latest_match_id = mid
        season_winners[season] = match_winner.get(latest_match_id, "Unknown")

    # 3. Load deliveries and pre-aggregate per season
    for season in available_seasons:
        season_player_stats[season] = {"runs": {}, "teams": {}}

    with open(DELIVERIES_PATH, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            match_id = row["match_id"]
            season = match_year.get(match_id)
            if not season:
                continue

            player = row["batter"]
            team = row["batting_team"]
            try:
                runs = int(row["batsman_runs"])
            except (ValueError, TypeError):
                continue

            stats = season_player_stats[season]
            stats["runs"][player] = stats["runs"].get(player, 0) + runs
            if player not in stats["teams"]:
                stats["teams"][player] = team


def resolve_season(year_input):
    """
    Resolve user input to the matched season name in the dataset.
    Supports exact match (e.g. '2016') as well as partial year matches (e.g. '2008' -> '2007/08', '2020' -> '2020/21').
    """
    if not year_input:
        return None

    year_str = str(year_input).strip()
    if year_str in available_seasons:
        return year_str

    for season in available_seasons:
        if season.endswith(year_str) or season.startswith(year_str) or year_str in season:
            return season

    return None


def get_most_runs_by_year(year_wanted, print_output=True):
    """
    Given a year/season, returns a dict with top run scorer, team, total runs, and series winner.
    Prints the result in the required format.
    """
    matched_season = resolve_season(year_wanted)
    if not matched_season or matched_season not in season_player_stats:
        return None

    stats = season_player_stats[matched_season]
    player_runs = stats["runs"]
    player_team = stats["teams"]

    if not player_runs:
        return None

    # ---- Find the top run scorer ----
    top_player = None
    top_runs = 0
    for player, runs in player_runs.items():
        if runs > top_runs:
            top_runs = runs
            top_player = player

    top_team = player_team.get(top_player, "Unknown")
    series_winner = season_winners.get(matched_season, "Unknown")

    if print_output:
        # ---- Print results ----
        print("\nYear:", year_wanted)
        print("Player with most runs:", top_player)
        print("Team:", top_team)
        print("Total runs:", top_runs)
        print("Series winner:", series_winner)

    return {
        "year": str(year_wanted),
        "season_matched": matched_season,
        "player_with_most_runs": top_player,
        "team": top_team,
        "total_runs": top_runs,
        "series_winner": series_winner
    }


# Initialize dataset on import/startup
load_dataset()

# Flask REST API
app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def require_auth(f):
    """
    Decorator to enforce Bearer Token authentication.
    Checks:
      1. 'Authorization: Bearer <TOKEN>' header
      2. '?token=<TOKEN>' or '?api_key=<TOKEN>' query parameter (fallback)
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 1. Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

        # 2. Check query parameter fallback
        if not token:
            token = request.args.get("token") or request.args.get("api_key")

        if not token or token != API_BEARER_TOKEN:
            return jsonify({
                "error": "Unauthorized. Missing or invalid Bearer token.",
                "hint": "Include 'Authorization: Bearer <TOKEN>' header in your request or pass '?token=<TOKEN>' in the query."
            }), 401

        return f(*args, **kwargs)
    return decorated


@app.route("/", methods=["GET"])
def home():
    """Root endpoint for the IPL Stats REST API."""
    year = request.args.get("year") or request.args.get("season")
    if year:
        # If accessed directly with ?year=, enforce auth
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        if not token:
            token = request.args.get("token") or request.args.get("api_key")

        if not token or token != API_BEARER_TOKEN:
            return jsonify({
                "error": "Unauthorized. Missing or invalid Bearer token.",
                "hint": "Include 'Authorization: Bearer <TOKEN>' header in your request or pass '?token=<TOKEN>' in the query."
            }), 401

        result = get_most_runs_by_year(year)
        if result is None:
            return jsonify({"error": f"No data found for year/season: {year}", "available_seasons": available_seasons}), 404
        return jsonify(result)

    return jsonify({
        "status": "online",
        "service": "IPL Stats REST API",
        "endpoints": {
            "/stats?year=<year>": "Get top batsman and series winner for a season (Requires Bearer token)",
            "/stats/all": "Get statistics for all seasons (Requires Bearer token)",
            "/seasons": "List all available seasons (Requires Bearer token)"
        }
    })


@app.route("/stats", methods=["GET"])
@app.route("/most-runs", methods=["GET"])
@app.route("/api/most-runs", methods=["GET"])
@require_auth
def api_stats():
    """
    Protected REST API endpoint for season stats.
    Requires Bearer Token authentication.
    Example: /stats?year=2016 with Header: Authorization: Bearer <TOKEN>
    """
    year = request.args.get("year") or request.args.get("season")
    if not year:
        return jsonify({"error": "Missing required query parameter 'year'. Example: /stats?year=2016"}), 400

    result = get_most_runs_by_year(year)
    if result is None:
        return jsonify({
            "error": f"No data found for year/season: '{year}'",
            "available_seasons": available_seasons
        }), 404

    return jsonify(result)


@app.route("/stats/all", methods=["GET"])
@app.route("/all-stats", methods=["GET"])
@require_auth
def api_all_stats():
    """Returns top batsman and series winner for all available seasons."""
    results = [get_most_runs_by_year(s, print_output=False) for s in available_seasons]
    valid_results = [r for r in results if r is not None]
    return jsonify({
        "seasons": valid_results,
        "count": len(valid_results)
    })


@app.route("/stats/<path:year>", methods=["GET"])
@app.route("/most-runs/<path:year>", methods=["GET"])
@require_auth
def api_stats_by_path(year):
    """
    Protected REST API endpoint accepting year as URL path parameter.
    Requires Bearer Token authentication.
    Example: /stats/2016 with Header: Authorization: Bearer <TOKEN>
    """
    result = get_most_runs_by_year(year)
    if result is None:
        return jsonify({
            "error": f"No data found for year/season: '{year}'",
            "available_seasons": available_seasons
        }), 404

    return jsonify(result)


@app.route("/seasons", methods=["GET"])
@app.route("/years", methods=["GET"])
@require_auth
def api_seasons():
    """Returns list of all available seasons in the dataset (Protected)."""
    return jsonify({
        "seasons": available_seasons,
        "count": len(available_seasons)
    })


def cli_interactive():
    """Interactive CLI mode."""
    year_wanted = input("Enter the year you want to check: ").strip()
    result = get_most_runs_by_year(year_wanted, print_output=True)
    if result is None:
        print("No data found for that year.")


if __name__ == "__main__":
    # Check if a year was passed via command line argument (CLI mode)
    # Usage: python most_runs_by_year.py 2016
    if len(sys.argv) > 1 and sys.argv[1] not in ["--server", "-s", "serve"]:
        cli_year = sys.argv[1]
        result = get_most_runs_by_year(cli_year, print_output=True)
        if result is None:
            print(f"No data found for year '{cli_year}'. Available seasons: {available_seasons}")
    else:
        PORT = 5005
        print(f"IPL Stats REST API Server running on http://127.0.0.1:{PORT} (Bearer token: {API_BEARER_TOKEN})")
        app.run(host="127.0.0.1", port=PORT, debug=False)