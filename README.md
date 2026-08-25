# IPL Player Comparison (Python)

Compares two IPL players' **runs** and **wickets**, broken down **season by
season (year by year)**, using the Kaggle dataset:
[IPL Complete Dataset (2008-2024)](https://www.kaggle.com/datasets/patrickb1912/ipl-complete-dataset-20082020)

Two **independent** implementations are included — they don't call each
other, they each read the dataset and compute the same answer their own way.

```
ipl-stats-project/
├── data/
│   ├── matches.csv         <- put the Kaggle file here (see below)
│   └── deliveries.csv      <- put the Kaggle file here (see below)
├── python/
│   ├── app.py               <- Flask REST API + CLI mode
│   └── requirements.txt


## 1. Get the dataset

1. Download the dataset from Kaggle (free account required):
   https://www.kaggle.com/datasets/patrickb1912/ipl-complete-dataset-20082020
2. Unzip it and place **both** `matches.csv` and `deliveries.csv` in the
   `data/` folder of this project.

`matches.csv` provides the season/year for each match (`id`, `season`, ...).
`deliveries.csv` has the ball-by-ball data (`batter`/`batsman`, `bowler`,
`batsman_runs`, `is_wicket`, `dismissal_kind`, `match_id`). Both programs join
these two files on `match_id` to group stats by season. Wickets are only
credited to the bowler (run outs, retired hurt, and obstruction are excluded,
matching real cricket scoring rules).

## 2. Python — REST API

### A. Most Runs by Year API (`most_runs_by_year.py`)

Reports the top run scorer, team, total runs, and series winner for any season, protected with **Bearer Token authentication**.

#### 1. Start the server
```bash
cd python
python most_runs_by_year.py
```
*(Runs on `http://127.0.0.1:5005`)*

> **Authentication**:
> - Default Token: `ipl-secret-token-2026`
> - Custom Token: set the environment variable `API_BEARER_TOKEN`

---

#### 2. Querying the API

**Option 1: In PowerShell (Windows)**
```powershell
$headers = @{ "Authorization" = "Bearer ipl-secret-token-2026" }
Invoke-RestMethod -Uri "http://127.0.0.1:5005/stats?year=2016" -Headers $headers
```

**Option 2: Using `curl.exe`**
```powershell
curl.exe -H "Authorization: Bearer ipl-secret-token-2026" "http://127.0.0.1:5005/stats?year=2016"
```

**Option 3: Using Query Parameter (Browser or Web Client)**
```
http://127.0.0.1:5005/stats?year=2016&token=ipl-secret-token-2026
```

#### 3. Available Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/stats?year=2016` | `GET` | Get top batsman & series winner for year |
| `/most-runs/2016` | `GET` | Path parameter format |
| `/stats/all` | `GET` | Get statistics for all seasons |
| `/seasons` | `GET` | List all available seasons in dataset |
| `/` | `GET` | API status and endpoint directory |

---

#### 4. Run directly in CLI (No Server)
```bash
python most_runs_by_year.py 2016
```

**Output**:
```text
Year: 2016
Player with most runs: V Kohli
Team: Royal Challengers Bangalore
Total runs: 973
Series winner: Sunrisers Hyderabad
```

---

### B. Visualization Dashboard App (`visualization_app.py`)

A modern web dashboard running on port **`8080`** that connects to the REST API on port **`5005`** with **Bearer Token authentication**:
- **Top Batsman Runs by Season** (Interactive Bar Chart)
- **Series Winners Championship Distribution** (Doughnut Chart)
- **Top Scoring Titles per Player** (Horizontal Bar Chart)
- **Summary Metrics & Full Season Breakdown Table**
- **Bearer Token Auth Control**: UI token input bar + API protection

#### How to run:
1. First, start the backend REST API in one terminal:
   ```bash
   cd python
   python most_runs_by_year.py
   ```
2. In a second terminal, start the visualizer:
   ```bash
   cd python
   python visualization_app.py
   ```
3. Open your browser to **[http://127.0.0.1:8080](http://127.0.0.1:8080)**.
   - The dashboard opens in a **Locked State** (no data is shown).
   - Enter your Bearer Token (`ipl-secret-token-2026`) into the input box and click **Unlock Dashboard** to view all charts and tables.
   - You can also bypass the prompt by visiting with a token in the URL: `http://127.0.0.1:8080/?token=ipl-secret-token-2026`.

---

### C. Player Comparison CLI (`ipl_season_stats.py`)

```bash
# Run one-off CLI comparison:
python ipl_season_stats.py
```

## 3. Java — standalone program

```bash
cd java
javac MostRunsByYear.java
java MostRunsByYear
```

## Sample output

```
Year: 2016
Player with most runs: V Kohli
Team: Royal Challengers Bangalore
Total runs: 973
Series winner: Sunrisers Hyderabad
```

## Notes

- Player names and stats are aggregated directly from `deliveries.csv` and `matches.csv`.
- Supported seasons include `2007/08`, `2009`, `2009/10`, `2011` through `2024`.

