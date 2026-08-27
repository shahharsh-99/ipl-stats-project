# IPL Player Comparison (Python)

Compares IPL players' **runs**, broken down **season by season (year by
year)**, using the Kaggle dataset:
[IPL Complete Dataset (2008-2024)](https://www.kaggle.com/datasets/patrickb1912/ipl-complete-dataset-20082020)

The project has two parts that work together:

- **`most_runs_by_year.py`** — a Flask REST API (and CLI tool) that reads
  the dataset and reports the top run scorer, team, total runs, and series
  winner for a given season.
- **`visualization_app.py`** — a Flask web dashboard that calls the REST
  API above and renders the results as interactive charts and tables.

```
ipl-stats-project/
├── data/
│   ├── matches.csv              <- put the Kaggle file here (see below)
│   └── deliveries.csv           <- put the Kaggle file here (see below)
├── python/
│   ├── most_runs_by_year.py     <- Flask REST API + CLI mode
│   ├── visualization_app.py     <- Web dashboard (calls the REST API)
│   └── requirements.txt
```

## 1. Get the dataset

1. Download the dataset from Kaggle (free account required):
   https://www.kaggle.com/datasets/patrickb1912/ipl-complete-dataset-20082020
2. Unzip it and place **both** `matches.csv` and `deliveries.csv` in the
   `data/` folder of this project.

`matches.csv` provides the season/year and winner for each match (`id`,
`season`, `winner`, `date`, ...). `deliveries.csv` has the ball-by-ball data
(`batter`, `batsman_runs`, `batting_team`, `match_id`). Both scripts join
these two files on `match_id` to aggregate runs per player per season, and
determine each season's series winner from the last match played that
season.

## 2. Install dependencies

```bash
cd python
pip install flask
```

## 2a. Run with Docker Compose

Docker Compose runs the REST API and dashboard as separate services. The
dataset in `data/` is copied into both containers at build time.

### Windows PowerShell

After downloading or cloning this project, open PowerShell and change into the
project folder. The folder must contain `docker-compose.yml`.

```powershell
cd C:\path\to\project
$env:API_BEARER_TOKEN = "replace-with-a-secret-token"
docker compose up --build
```

### macOS/Linux

```bash
cd /path/to/project
export API_BEARER_TOKEN="replace-with-a-secret-token"
docker compose up --build
```

Open the dashboard at **http://localhost:8080** and enter the same token.
The API is also available at **http://localhost:5005**. Stop the services with:

```powershell
docker compose down
```

Keep `API_BEARER_TOKEN` out of version control. To use a different host port,
change the left-hand side of the `ports` entries in `docker-compose.yml`.

### Run the published GitHub images

The images can also be pulled from GitHub Container Registry. Log in with a
GitHub token that has `read:packages` permission:

```powershell
docker login ghcr.io -u shahharsh-99
docker pull ghcr.io/shahharsh-99/ipl-stats-project-api:latest
docker pull ghcr.io/shahharsh-99/ipl-stats-project-dashboard:latest
```

To run the published images together, create a Docker network and provide the
same token to both containers. Replace the example token with your own value:

```powershell
docker network create ipl-network
$env:API_BEARER_TOKEN = "replace-with-a-secret-token"

docker run -d --name ipl-api --network ipl-network `
  -e API_BEARER_TOKEN `
  -p 5005:5005 `
  ghcr.io/shahharsh-99/ipl-stats-project-api:latest

docker run -d --name ipl-dashboard --network ipl-network `
  -e API_BEARER_TOKEN `
  -e API_BASE_URL=http://ipl-api:5005 `
  -p 8080:8080 `
  ghcr.io/shahharsh-99/ipl-stats-project-dashboard:latest
```

Open **http://localhost:8080** and enter the same token. Stop and remove the
containers when finished:

```powershell
docker rm -f ipl-dashboard ipl-api
docker network rm ipl-network
```

## 3. Most Runs by Year API (`most_runs_by_year.py`)

Reports the top run scorer, their team, total runs, and the series winner
for any season. All data endpoints are protected with **Bearer Token
authentication**.

### Start the server

```bash
cd python
python most_runs_by_year.py
```
*(Runs on `http://127.0.0.1:5005`)*

> **Authentication**
> The server reads its token from the `API_BEARER_TOKEN` environment
> variable — there is no built-in default, so you must set it before
> starting the server, e.g.:
> ```bash
> # macOS/Linux
> export API_BEARER_TOKEN="ipl-secret-token-2026"
> # Windows PowerShell
> $env:API_BEARER_TOKEN = "ipl-secret-token-2026"
> ```
> Requests without a matching token receive a `401 Unauthorized` response.

### Querying the API

**Option 1: PowerShell (Windows)**
```powershell
$headers = @{ "Authorization" = "Bearer ipl-secret-token-2026" }
Invoke-RestMethod -Uri "http://127.0.0.1:5005/stats?year=2016" -Headers $headers
```

**Option 2: `curl.exe`**
```powershell
curl.exe -H "Authorization: Bearer ipl-secret-token-2026" "http://127.0.0.1:5005/stats?year=2016"
```

**Option 3: Query parameter (browser or web client)**
```
http://127.0.0.1:5005/stats?year=2016&token=ipl-secret-token-2026
```

### Available endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/stats?year=2016` | `GET` | Top batsman, team, total runs & series winner for a season |
| `/most-runs?year=2016` / `/api/most-runs?year=2016` | `GET` | Aliases for `/stats` |
| `/stats/2016` / `/most-runs/2016` | `GET` | Same as above, with year as a path parameter |
| `/stats/all` / `/all-stats` | `GET` | Stats for every available season |
| `/seasons` / `/years` | `GET` | List all available seasons in the dataset |
| `/` | `GET` | API status and endpoint directory; also accepts `?year=` for a quick lookup |

All endpoints except `/` (without `?year=`) require a Bearer token, either
as an `Authorization: Bearer <TOKEN>` header or a `?token=` / `?api_key=`
query parameter.

### Run directly in CLI (no server, no auth needed)

```bash
python most_runs_by_year.py 2016
```

**Output:**
```text
Year: 2016
Player with most runs: V Kohli
Team: Royal Challengers Bangalore
Total runs: 973
Series winner: Sunrisers Hyderabad
```

You can also run it with no arguments for an interactive prompt
(`cli_interactive`), which asks you to type in a year.

## 4. Visualization Dashboard (`visualization_app.py`)

A web dashboard on port **`8080`** that calls the REST API on port
**`5005`** and renders:

- **Top Batsman Runs by Season** (bar chart)
- **Series Winners Distribution** (doughnut chart)
- **Most Season-Leading Run Scorer Titles** (horizontal bar chart)
- **Summary metric cards** and a **full season-by-season table**
- A **Bearer Token auth gate** — the dashboard stays locked until a valid
  token is entered

### How to run

1. Start the backend REST API in one terminal (see section 3 above — make
   sure `API_BEARER_TOKEN` is set first):
   ```bash
   cd python
   python most_runs_by_year.py
   ```
2. In a second terminal, start the visualizer. Point it at the same token
   and, if needed, a different API URL:
   ```bash
   cd python
   # optional overrides — visualization_app.py defaults to
   # API_BASE_URL=http://127.0.0.1:5005 and
   # API_BEARER_TOKEN=ipl-secret-token-2026 if these aren't set
   export API_BEARER_TOKEN="ipl-secret-token-2026"
   export API_BASE_URL="http://127.0.0.1:5005"
   export VIS_PORT=8080
   python visualization_app.py
   ```
3. Open your browser to **http://127.0.0.1:8080**.
   - The dashboard opens in a **locked state** — no data is shown.
   - Enter your Bearer token into the input box and click **Unlock
     Dashboard** to view all charts and tables.
   - You can also skip the prompt by including the token in the URL:
     `http://127.0.0.1:8080/?token=ipl-secret-token-2026`.

> **Note:** Unlike `most_runs_by_year.py`, `visualization_app.py` *does*
> fall back to a default token (`ipl-secret-token-2026`) if
> `API_BEARER_TOKEN` isn't set. For the dashboard to actually fetch data,
> this token must match whatever `API_BEARER_TOKEN` you started
> `most_runs_by_year.py` with.

### Dashboard proxy endpoints

| Endpoint | Description |
| :--- | :--- |
| `/api/health` | Checks connectivity to the backend REST API |
| `/api/all-stats` | Fetches and aggregates stats for every season for the dashboard |
| `/` | Serves the dashboard HTML page |

## Notes

- Player names and stats are aggregated directly from `deliveries.csv` and
  `matches.csv` — nothing is hardcoded.
- Supported seasons include `2007/08`, `2009`, `2009/10`, `2011` through
  `2024` (whatever seasons exist in your copy of `matches.csv`). You can
  query using either the full season string (e.g. `2007/08`) or a
  four-digit year (e.g. `2008`) — the API will match it to the closest
  season label.
- Keep your Bearer token out of version control; treat it like a secret
  and set it via environment variables rather than hardcoding it.