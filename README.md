# Sugarcane Production — Crop Explorer

FAOSTAT crop production data (1961–2024, 301 crops, 144 countries) exposed as a REST API and a storytelling visualisation script.

No API keys required — all data is fetched from public sources:
- [FAOSTAT bulk download](https://www.fao.org/faostat) — production, area harvested, yield
- [World Bank Open Data](https://data.worldbank.org/) — GDP and population for enrichment

---

## Project structure

```
├── faostat/               # Core library
│   ├── client.py          # FAOSTATClient — download, cache, query
│   └── worldbank.py       # WorldBankClient — GDP & population
├── api/
│   └── main.py            # FastAPI REST API
├── scripts/
│   └── storytelling.py    # Visualisation script
├── data/                  # FAOSTAT cache + original CSVs
├── outputs/               # Generated plots
└── requirements.txt
```

---

## Setup

```bash
pip install -r requirements.txt
```

The FAOSTAT dataset (~34 MB) is downloaded automatically on first run and cached in `data/faostat_bulk.csv`. It is refreshed after 7 days.

---

## REST API

Start the server:

```bash
uvicorn api.main:app --reload
```

Interactive docs (Swagger UI): **http://localhost:8000/docs**

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/crops` | List all 301 available crops |
| `GET` | `/crops/{crop}/production` | Annual production (tonnes) |
| `GET` | `/crops/{crop}/production/top` | Top N producers for a single year |
| `GET` | `/crops/{crop}/area` | Annual area harvested (ha) |
| `GET` | `/crops/{crop}/yield` | Annual yield (kg / ha) |
| `GET` | `/crops/{crop}/country/{country}` | All three metrics for one country |
| `GET` | `/crops/{crop}/enrich` | Production + World Bank GDP & population |
| `GET` | `/brazil/sugarcane` | Brazil sugarcane time series + world share % |
| `GET` | `/health` | Health check |

### Query parameters (common)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `start` | 1990 | Start year |
| `end` | 2024 | End year |
| `top_n` | — | Limit to top N countries by total production |

### Example requests

```bash
# Top 5 sugarcane producers in 2022
curl "http://localhost:8000/crops/Sugar%20cane/production/top?year=2022&n=5"

# Wheat production 2000-2023, top 8 countries
curl "http://localhost:8000/crops/Wheat/production?start=2000&end=2023&top_n=8"

# Brazil's sugarcane metrics 1975-2024
curl "http://localhost:8000/brazil/sugarcane?start=1975"

# Maize production enriched with GDP + population
curl "http://localhost:8000/crops/Maize%20(corn)/enrich?top_n=10"

# All metrics for India + Coffee
curl "http://localhost:8000/crops/Coffee%2C%20green/country/India"
```

---

## Visualisation script

Generates a two-part storytelling chart saved to `outputs/`.

```bash
# Default: sugarcane, 1990–2024, top 10
python3 scripts/storytelling.py

# Different crop for the global comparison section
python3 scripts/storytelling.py --crop "Maize (corn)"
python3 scripts/storytelling.py --crop "Wheat" --start 2000 --end 2023 --top 8
python3 scripts/storytelling.py --crop "Coffee, green" --top 5

# List all available crop names
python3 scripts/storytelling.py --list-crops
```

The chart has two independent sections:

**Part A — Global crop comparison** (switches with `--crop`)
- Production time series for top N countries
- World production share (stacked area)
- Growth rate from start to end year

**Part B — Brazil sugarcane storytelling** (always fixed)
- Production + harvested area with policy milestones annotated
- Yield efficiency (t/ha) vs Brazil's world share
- Decade pie charts: world production share in 1990 vs latest year

---

## Using the library directly

```python
from faostat import FAOSTATClient, WorldBankClient

faostat = FAOSTATClient()

# List all crops
faostat.list_crops()

# Top producers
faostat.top_producers("Sugar cane", year=2022, n=10)

# Time series for one country
faostat.get_country("Sugar cane", "Brazil", start=1975, end=2024)

# Enrich with World Bank data
from faostat import WorldBankClient
wb = WorldBankClient()
wb.enrich(["Brazil", "India", "Thailand"], year=2022)
```
