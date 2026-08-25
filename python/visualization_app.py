import os
import json
import urllib.request
import urllib.parse
import urllib.error
from functools import wraps
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# Configuration
PORT = int(os.environ.get("VIS_PORT", 8080))
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5005")
API_BEARER_TOKEN = os.environ.get("API_BEARER_TOKEN", "ipl-secret-token-2026")


def require_auth(f):
    """
    Decorator to enforce Bearer Token authentication on visualization proxy endpoints.
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


def fetch_from_api(endpoint, token=None):
    """Helper to fetch data from the REST API on port 5005 with Bearer token."""
    url = f"{API_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    auth_token = token or API_BEARER_TOKEN
    headers = {"Authorization": f"Bearer {auth_token}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"error": f"HTTP {e.code}: {e.reason}"}
        return None, err_body
    except urllib.error.URLError as e:
        return None, {"error": f"Could not connect to API at {API_BASE_URL}. Ensure most_runs_by_year.py is running on port 5005. ({e.reason})"}
    except Exception as e:
        return None, {"error": str(e)}


@app.route("/api/health")
@require_auth
def api_health():
    """Check backend API connectivity (Protected by Bearer Token)."""
    # Extract the client's token to forward to the backend
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1].strip() if auth_header.startswith("Bearer ") else (request.args.get("token") or request.args.get("api_key"))
    
    data, err = fetch_from_api("/seasons", token=token)
    if err:
        return jsonify({"status": "offline", "api_url": API_BASE_URL, "error": err}), 503
    return jsonify({"status": "online", "api_url": API_BASE_URL, "season_count": data.get("count", 0)})


@app.route("/api/all-stats")
@require_auth
def api_all_stats():
    """Fetch and aggregate stats across all available seasons (Protected by Bearer Token)."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1].strip() if auth_header.startswith("Bearer ") else (request.args.get("token") or request.args.get("api_key"))

    # 1. Try batch /stats/all endpoint
    batch_data, err = fetch_from_api("/stats/all", token=token)
    if not err and batch_data and "seasons" in batch_data:
        return jsonify(batch_data)

    # 2. Fallback to querying seasons list and individual stats
    seasons_data, err = fetch_from_api("/seasons", token=token)
    if err:
        return jsonify(err), 503

    seasons = seasons_data.get("seasons", [])
    results = []
    for season in seasons:
        stat, s_err = fetch_from_api(f"/stats?year={urllib.parse.quote(season)}", token=token)
        if stat:
            results.append(stat)

    return jsonify({"seasons": results, "count": len(results)})


HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPL Statistics Visualizer</title>
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        :root {
            --bg-dark: #090d16;
            --card-bg: rgba(19, 28, 46, 0.85);
            --card-border: #1e293b;
            --accent-cyan: #38bdf8;
            --accent-indigo: #818cf8;
            --accent-amber: #fbbf24;
            --accent-emerald: #34d399;
            --accent-rose: #f43f5e;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: radial-gradient(circle at 50% 0%, #172554 0%, #090d16 60%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 30px 20px;
        }
        .wrapper {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            margin-bottom: 24px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--card-border);
        }
        h1 {
            font-size: 1.9rem;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
        }
        p.subtitle { color: var(--text-muted); font-size: 0.95rem; margin-top: 4px; }
        
        .header-controls {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }
        .auth-status-bar {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid var(--card-border);
            padding: 6px 12px;
            border-radius: 10px;
            font-size: 0.85rem;
        }
        .auth-status-bar button {
            background: #334155;
            color: #f8fafc;
            border: 1px solid var(--card-border);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
        }
        .auth-status-bar button:hover { background: #475569; }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid var(--card-border);
        }
        .status-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: #ef4444;
            box-shadow: 0 0 8px #ef4444;
        }
        .status-dot.online {
            background: #22c55e;
            box-shadow: 0 0 8px #22c55e;
        }
        
        /* Auth Gate Screen */
        .auth-gate {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 48px 32px;
            max-width: 520px;
            margin: 60px auto;
            text-align: center;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
            backdrop-filter: blur(12px);
        }
        .lock-icon {
            font-size: 3rem;
            margin-bottom: 16px;
        }
        .auth-gate h2 {
            font-size: 1.6rem;
            margin-bottom: 8px;
            color: var(--text-main);
        }
        .auth-gate p {
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-bottom: 24px;
            line-height: 1.5;
        }
        .gate-form {
            display: flex;
            flex-direction: column;
            gap: 14px;
        }
        .gate-form input {
            width: 100%;
            padding: 14px 18px;
            background: #090d16;
            border: 1px solid var(--card-border);
            border-radius: 10px;
            color: var(--accent-cyan);
            font-size: 1rem;
            font-family: monospace;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        .gate-form input:focus {
            border-color: var(--accent-cyan);
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.25);
        }
        .gate-form button {
            padding: 14px;
            background: linear-gradient(135deg, #0284c7, #3b82f6);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: opacity 0.15s, transform 0.15s;
        }
        .gate-form button:hover {
            opacity: 0.9;
            transform: translateY(-1px);
        }
        .gate-error {
            background: rgba(248, 113, 113, 0.15);
            border: 1px solid #f87171;
            color: #fca5a5;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 0.88rem;
            margin-top: 14px;
            display: none;
        }

        /* Dashboard content (hidden until authenticated) */
        #dashboardContent {
            display: none;
        }

        .alert-banner {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.4);
            color: #fca5a5;
            padding: 16px 20px;
            border-radius: 12px;
            margin-bottom: 24px;
            display: none;
            line-height: 1.5;
        }
        .alert-banner strong { color: #f87171; }
        .alert-banner code {
            background: rgba(0,0,0,0.3);
            padding: 2px 6px;
            border-radius: 4px;
            color: #ffffff;
            font-family: monospace;
        }
        .alert-banner button {
            margin-top: 10px;
            padding: 6px 14px;
            background: #ef4444;
            color: white;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
        }

        /* Metrics row */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 18px;
            margin-bottom: 28px;
        }
        .metric-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }
        .metric-title { font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
        .metric-value { font-size: 1.8rem; font-weight: 700; color: var(--accent-cyan); }
        .metric-sub { font-size: 0.85rem; color: var(--text-muted); margin-top: 4px; }

        /* Charts grid */
        .charts-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 22px;
            margin-bottom: 28px;
        }
        @media (max-width: 900px) {
            .charts-grid { grid-template-columns: 1fr; }
        }
        .chart-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(10px);
            box-shadow: 0 12px 30px rgba(0,0,0,0.35);
        }
        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
        }
        .chart-title { font-size: 1.15rem; font-weight: 700; color: var(--text-main); }
        .chart-container { position: relative; width: 100%; height: 320px; }

        /* Table Card */
        .table-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(10px);
            margin-bottom: 28px;
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            text-align: left;
        }
        th {
            padding: 12px 16px;
            color: var(--text-muted);
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--card-border);
        }
        td {
            padding: 12px 16px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 0.95rem;
        }
        tr:hover td { background: rgba(56, 189, 248, 0.05); }
        .player-name { font-weight: 600; color: var(--accent-cyan); }
        .runs-val { font-weight: 700; color: var(--accent-emerald); }
        .winner-badge {
            background: rgba(251, 191, 36, 0.15);
            color: var(--accent-amber);
            border: 1px solid rgba(251, 191, 36, 0.3);
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .loader {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 240px;
            color: var(--text-muted);
            font-size: 1.1rem;
            gap: 12px;
        }
        .spinner {
            width: 24px;
            height: 24px;
            border: 3px solid var(--card-border);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="wrapper">
        <header>
            <div>
                <h1>IPL Season Stats Visualizer</h1>
                <p class="subtitle">Connected to REST API (<code>{{ api_url }}</code>)</p>
            </div>
            <div class="header-controls">
                <div class="auth-status-bar" id="authStatusBar" style="display:none;">
                    <span style="color: var(--accent-emerald);">Authenticated</span>
                    <button onclick="lockDashboard()">Lock</button>
                </div>
                <div class="badge" id="apiStatusBadge">
                    <div class="status-dot" id="statusDot"></div>
                    <span id="statusText">Authentication Required</span>
                </div>
            </div>
        </header>

        <!-- AUTH GATE SCREEN (Shown before token is entered) -->
        <div id="authGateCard" class="auth-gate">
            <div class="lock-icon">🔒</div>
            <h2>Authentication Required</h2>
            <p>Please enter your <strong>Bearer Token</strong> to unlock and view the IPL statistics and interactive visualizations.</p>
            <form class="gate-form" onsubmit="handleGateAuth(event)">
                <input type="password" id="gateTokenInput" placeholder="Enter Bearer Token" required autocomplete="off" />
                <button type="submit">Unlock Dashboard</button>
            </form>
            <div id="gateError" class="gate-error"></div>
        </div>

        <!-- DASHBOARD CONTENT (Locked and hidden until token is submitted and validated) -->
        <div id="dashboardContent">
            <!-- Offline notice banner -->
            <div id="offlineBanner" class="alert-banner">
                <span id="bannerText"><strong>API Server Disconnected:</strong> Could not connect to backend at <code>{{ api_url }}</code>.</span><br>
                Please make sure you have started the REST API server in a separate terminal:
                <br><code>python python/most_runs_by_year.py</code><br>
                <button onclick="fetchAndRenderDashboard()">Retry Connection</button>
            </div>

            <!-- Metric Summary Cards -->
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-title">All-Time Highest Runs</div>
                    <div class="metric-value" id="topRunsMetric">--</div>
                    <div class="metric-sub" id="topPlayerMetric">Loading...</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Total Seasons Analyzed</div>
                    <div class="metric-value" id="seasonsCountMetric">--</div>
                    <div class="metric-sub">2008 &ndash; 2024</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Most Trophies (Winner)</div>
                    <div class="metric-value" id="topTeamMetric">--</div>
                    <div class="metric-sub" id="topTeamCountMetric">Loading...</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Average Top Scorer Runs</div>
                    <div class="metric-value" id="avgRunsMetric">--</div>
                    <div class="metric-sub">Runs / Season Leader</div>
                </div>
            </div>

            <!-- Charts Section -->
            <div class="charts-grid">
                <div class="chart-card">
                    <div class="chart-header">
                        <div class="chart-title">Top Batsman Runs by Season</div>
                    </div>
                    <div class="chart-container">
                        <canvas id="runsBySeasonChart"></canvas>
                    </div>
                </div>

                <div class="chart-card">
                    <div class="chart-header">
                        <div class="chart-title">Series Winners Distribution</div>
                    </div>
                    <div class="chart-container">
                        <canvas id="winnersChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Orange Cap Multi-Winners Chart -->
            <div class="chart-card" style="margin-bottom: 28px;">
                <div class="chart-header">
                    <div class="chart-title">Most Season-Leading Run Scorer Titles</div>
                </div>
                <div class="chart-container" style="height: 260px;">
                    <canvas id="topScorersCountChart"></canvas>
                </div>
            </div>

            <!-- Detailed Table -->
            <div class="table-card">
                <div class="chart-title" style="margin-bottom: 16px;">Season-by-Season Breakdown</div>
                <div id="tableContainer">
                    <div class="loader">
                        <div class="spinner"></div>
                        <span>Fetching statistics from REST API...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentToken = null;
        let runsChartInstance = null;
        let winnersChartInstance = null;
        let scorersChartInstance = null;

        function handleGateAuth(e) {
            e.preventDefault();
            const token = document.getElementById('gateTokenInput').value.trim();
            const gateError = document.getElementById('gateError');
            gateError.style.display = 'none';

            if (!token) {
                gateError.textContent = 'Please enter a valid Bearer token.';
                gateError.style.display = 'block';
                return;
            }

            currentToken = token;
            sessionStorage.setItem('vis_bearer_token', token);
            validateAndLoadDashboard();
        }

        function lockDashboard() {
            currentToken = null;
            sessionStorage.removeItem('vis_bearer_token');
            document.getElementById('dashboardContent').style.display = 'none';
            document.getElementById('authStatusBar').style.display = 'none';
            document.getElementById('authGateCard').style.display = 'block';
            document.getElementById('gateTokenInput').value = '';
            document.getElementById('statusDot').className = 'status-dot';
            document.getElementById('statusText').textContent = 'Authentication Required';
        }

        async function validateAndLoadDashboard() {
            const gateError = document.getElementById('gateError');
            const authGateCard = document.getElementById('authGateCard');
            const dashboardContent = document.getElementById('dashboardContent');
            const authStatusBar = document.getElementById('authStatusBar');
            const statusDot = document.getElementById('statusDot');
            const statusText = document.getElementById('statusText');

            statusText.textContent = 'Verifying Token...';

            try {
                // 1. Verify token with health endpoint
                const healthRes = await fetch(`/api/health?token=${encodeURIComponent(currentToken)}`, {
                    headers: { 'Authorization': `Bearer ${currentToken}` }
                });
                const health = await healthRes.json();

                if (healthRes.status === 401) {
                    gateError.textContent = 'Invalid Bearer Token. Access Denied.';
                    gateError.style.display = 'block';
                    statusText.textContent = 'Unauthorized';
                    statusDot.className = 'status-dot';
                    return;
                }

                // If token is valid, unlock the dashboard!
                authGateCard.style.display = 'none';
                dashboardContent.style.display = 'block';
                authStatusBar.style.display = 'flex';

                if (healthRes.ok && health.status === 'online') {
                    statusDot.classList.add('online');
                    statusText.textContent = `API Online (${health.season_count} Seasons)`;
                } else {
                    statusText.textContent = 'API Offline';
                }

                fetchAndRenderDashboard();
            } catch (err) {
                gateError.textContent = 'Connection Error: ' + err.message;
                gateError.style.display = 'block';
                statusText.textContent = 'Connection Error';
            }
        }

        async function fetchAndRenderDashboard() {
            const offlineBanner = document.getElementById('offlineBanner');
            const tableContainer = document.getElementById('tableContainer');
            offlineBanner.style.display = 'none';

            try {
                const statsRes = await fetch(`/api/all-stats?token=${encodeURIComponent(currentToken)}`, {
                    headers: { 'Authorization': `Bearer ${currentToken}` }
                });
                const data = await statsRes.json();

                if (!statsRes.ok || !data.seasons || data.seasons.length === 0) {
                    offlineBanner.style.display = 'block';
                    tableContainer.innerHTML = '<p style="color: #f87171; padding: 20px;">Could not load data from API. Please ensure <code>python python/most_runs_by_year.py</code> is running on port 5005.</p>';
                    return;
                }

                renderDashboard(data.seasons);
            } catch (err) {
                offlineBanner.style.display = 'block';
                tableContainer.innerHTML = `<p style="color: #f87171; padding: 20px;">Error: ${err.message}</p>`;
            }
        }

        function renderDashboard(seasons) {
            let maxRuns = 0;
            let recordHolder = '';
            let totalRuns = 0;
            const winnersCount = {};
            const playerCounts = {};

            seasons.forEach(s => {
                const runs = s.total_runs;
                totalRuns += runs;
                if (runs > maxRuns) {
                    maxRuns = runs;
                    recordHolder = `${s.player_with_most_runs} (${s.year})`;
                }
                const winner = s.series_winner || 'Unknown';
                winnersCount[winner] = (winnersCount[winner] || 0) + 1;
                const player = s.player_with_most_runs;
                playerCounts[player] = (playerCounts[player] || 0) + 1;
            });

            let topTeam = '';
            let topTeamCount = 0;
            for (const [team, count] of Object.entries(winnersCount)) {
                if (count > topTeamCount) {
                    topTeamCount = count;
                    topTeam = team;
                }
            }

            document.getElementById('topRunsMetric').textContent = maxRuns;
            document.getElementById('topPlayerMetric').textContent = recordHolder;
            document.getElementById('seasonsCountMetric').textContent = seasons.length;
            document.getElementById('topTeamMetric').textContent = topTeam;
            document.getElementById('topTeamCountMetric').textContent = `${topTeamCount} Championship Titles`;
            document.getElementById('avgRunsMetric').textContent = Math.round(totalRuns / seasons.length);

            if (runsChartInstance) runsChartInstance.destroy();
            if (winnersChartInstance) winnersChartInstance.destroy();
            if (scorersChartInstance) scorersChartInstance.destroy();

            // 1. Runs Chart
            const labels = seasons.map(s => s.year);
            const runsData = seasons.map(s => s.total_runs);
            const playerLabels = seasons.map(s => `${s.player_with_most_runs} (${s.team})`);

            runsChartInstance = new Chart(document.getElementById('runsBySeasonChart'), {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Total Runs',
                        data: runsData,
                        backgroundColor: seasons.map(s => s.total_runs === maxRuns ? '#38bdf8' : '#3b82f6'),
                        borderColor: '#0284c7',
                        borderRadius: 6,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                afterLabel: function(context) {
                                    return 'Top Batsman: ' + playerLabels[context.dataIndex];
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false,
                            min: 500,
                            grid: { color: 'rgba(255,255,255,0.06)' },
                            ticks: { color: '#94a3b8' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#94a3b8' }
                        }
                    }
                }
            });

            // 2. Winners Chart
            winnersChartInstance = new Chart(document.getElementById('winnersChart'), {
                type: 'doughnut',
                data: {
                    labels: Object.keys(winnersCount),
                    datasets: [{
                        data: Object.values(winnersCount),
                        backgroundColor: [
                            '#38bdf8', '#818cf8', '#fbbf24', '#34d399', '#f43f5e', '#a855f7', '#fb923c'
                        ],
                        borderWidth: 2,
                        borderColor: '#0f172a'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { color: '#94a3b8', boxWidth: 12, font: { size: 11 } }
                        }
                    }
                }
            });

            // 3. Orange Cap Titles Chart
            const sortedPlayers = Object.entries(playerCounts)
                .sort((a,b) => b[1] - a[1])
                .slice(0, 8);

            scorersChartInstance = new Chart(document.getElementById('topScorersCountChart'), {
                type: 'bar',
                data: {
                    labels: sortedPlayers.map(p => p[0]),
                    datasets: [{
                        label: 'Orange Caps (Top Runs Seasons)',
                        data: sortedPlayers.map(p => p[1]),
                        backgroundColor: '#818cf8',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            ticks: { stepSize: 1, color: '#94a3b8' },
                            grid: { color: 'rgba(255,255,255,0.06)' }
                        },
                        y: {
                            ticks: { color: '#f8fafc', font: { weight: '600' } },
                            grid: { display: false }
                        }
                    }
                }
            });

            // 4. Data Table
            let tableHtml = `
                <table>
                    <thead>
                        <tr>
                            <th>Season</th>
                            <th>Top Scorer</th>
                            <th>Team</th>
                            <th>Total Runs</th>
                            <th>Series Winner</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            seasons.forEach(s => {
                tableHtml += `
                    <tr>
                        <td><strong>${s.year}</strong></td>
                        <td class="player-name">${s.player_with_most_runs}</td>
                        <td>${s.team}</td>
                        <td class="runs-val">${s.total_runs}</td>
                        <td><span class="winner-badge">🏆 ${s.series_winner}</span></td>
                    </tr>
                `;
            });
            tableHtml += `</tbody></table>`;
            document.getElementById('tableContainer').innerHTML = tableHtml;
        }

        // On page load: check if query parameter ?token= exists, otherwise stay locked
        document.addEventListener('DOMContentLoaded', () => {
            const urlParams = new URLSearchParams(window.location.search);
            const queryToken = urlParams.get('token') || urlParams.get('api_key');
            if (queryToken) {
                currentToken = queryToken;
                sessionStorage.setItem('vis_bearer_token', queryToken);
                validateAndLoadDashboard();
            }
        });
    </script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML_PAGE, api_url=API_BASE_URL)


if __name__ == "__main__":
    print("==========================================================")
    print("IPL Stats Visualization Dashboard")
    print("==========================================================")
    print(f"Server Port:       {PORT}")
    print(f"Backend API URL:   {API_BASE_URL}")
    print(f"Bearer Token:      {API_BEARER_TOKEN}")
    print("----------------------------------------------------------")
    print(f"Open Dashboard:    http://127.0.0.1:{PORT}")
    print("==========================================================\n")
    app.run(host="127.0.0.1", port=PORT, debug=False)
