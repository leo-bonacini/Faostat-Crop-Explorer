# API

FastAPI REST API over the FAOSTAT crop production dataset.

## Start

```bash
uvicorn api.main:app --reload
```

Interactive docs (Swagger UI): **http://localhost:8000/docs**  
Alternative docs (ReDoc): **http://localhost:8000/redoc**

---

## Endpoints

### Meta

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/crops` | List all 301 available crop names |

### Crop data

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/crops/{crop}/production` | Annual production in tonnes |
| `GET` | `/crops/{crop}/production/top` | Top N producers for a single year |
| `GET` | `/crops/{crop}/area` | Annual area harvested in hectares |
| `GET` | `/crops/{crop}/yield` | Annual yield in kg / ha |
| `GET` | `/crops/{crop}/country/{country}` | All three metrics for one country |

### Enriched data

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/crops/{crop}/enrich` | Production + World Bank GDP & population |

### Brazil

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/brazil/sugarcane` | Full Brazil sugarcane time series + world share % |

---

## Query parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start` | int | 1990 | Start year |
| `end` | int | 2024 | End year |
| `top_n` | int | — | Limit to top N countries by total production |
| `year` | int | 2022 | Reference year (for `/production/top`) |
| `n` | int | 10 | Number of results (for `/production/top`) |

---

## Example requests

```bash
# Top 5 sugarcane producers in 2023
curl "http://localhost:8000/crops/Sugar%20cane/production/top?year=2023&n=5"

# Wheat production 2000–2023, top 8 countries
curl "http://localhost:8000/crops/Wheat/production?start=2000&end=2023&top_n=8"

# All metrics for Brazil + sugarcane since 1975
curl "http://localhost:8000/brazil/sugarcane?start=1975"

# Maize top producers enriched with GDP and population
curl "http://localhost:8000/crops/Maize%20(corn)/enrich?top_n=10"

# Coffee production for Vietnam over time
curl "http://localhost:8000/crops/Coffee%2C%20green/country/Viet%20Nam"
```

---

## Response shapes

**`/crops/{crop}/production`**
```json
[
  { "country": "Brazil", "year": 2023, "production_tonnes": 782058236.0 },
  { "country": "India",  "year": 2023, "production_tonnes": 490533351.0 }
]
```

**`/crops/{crop}/enrich`**
```json
[
  {
    "country": "Brazil",
    "production_tonnes": 782058236.0,
    "gdp_bn_usd": 2173.664,
    "population": 216422446,
    "production_per_capita_kg": 3614.8,
    "production_per_gdp_kt_per_bn": 359.8
  }
]
```

**`/brazil/sugarcane`**
```json
[
  {
    "year": 2023,
    "production_tonnes": 782058236.0,
    "area_ha": 10048731.0,
    "yield_kg_ha": 77829.0,
    "world_share_pct": 36.8
  }
]
```
