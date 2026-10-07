"""
FAOSTAT Crop Production API
Run: uvicorn api.main:app --reload
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Make sure the project root is on the path when running from any directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from faostat import FAOSTATClient, WorldBankClient

# Startup: load data once

_faostat = FAOSTATClient(cache_max_days=7)
_worldbank = WorldBankClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the cache before accepting requests
    _faostat.list_crops()
    yield


app = FastAPI(
    title="FAOSTAT Crop Production API",
    description=(
        "Query FAO crop production, area harvested, and yield data for any country "
        "and year range. Optionally enrich with World Bank GDP and population.\n\n"
        "Data source: [FAOSTAT](https://www.fao.org/faostat) bulk download (no key required)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Response models

class ProductionRecord(BaseModel):
    country: str
    year: int
    production_tonnes: float

class AreaRecord(BaseModel):
    country: str
    year: int
    area_ha: float

class YieldRecord(BaseModel):
    country: str
    year: int
    yield_kg_ha: float

class TopProducerRecord(BaseModel):
    rank: int
    country: str
    production_tonnes: float

class EnrichedRecord(BaseModel):
    country: str
    production_tonnes: Optional[float]
    gdp_bn_usd: Optional[float]
    population: Optional[int]
    production_per_capita_kg: Optional[float]
    production_per_gdp_kt_per_bn: Optional[float]

class BrazilMetrics(BaseModel):
    year: int
    production_tonnes: Optional[float]
    area_ha: Optional[float]
    yield_kg_ha: Optional[float]
    world_share_pct: Optional[float]

# Routes

@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/crops", response_model=list[str], tags=["crops"])
def list_crops():
    """Return all crop names available in the FAOSTAT dataset."""
    return _faostat.list_crops()


@app.get("/crops/{crop}/production", response_model=list[ProductionRecord], tags=["crops"])
def get_production(
    crop: str,
    start: int = Query(1990, description="Start year"),
    end:   int = Query(2024, description="End year"),
    top_n: Optional[int] = Query(None, description="Limit to top N countries by total production"),
):
    """
    Annual production (tonnes) for a crop.

    Use `top_n` to return only the biggest producers.
    """
    try:
        df = _faostat.get_production(crop, start, end, top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return df.rename(columns={"year": "year"}).to_dict(orient="records")


@app.get("/crops/{crop}/production/top", response_model=list[TopProducerRecord], tags=["crops"])
def top_producers(
    crop: str,
    year: int = Query(2022, description="Reference year"),
    n:    int = Query(10,   description="Number of top producers to return"),
):
    """Top N producers for a crop in a single year."""
    try:
        df = _faostat.top_producers(crop, year, n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return df.to_dict(orient="records")


@app.get("/crops/{crop}/area", response_model=list[AreaRecord], tags=["crops"])
def get_area(
    crop:  str,
    start: int = Query(1990, description="Start year"),
    end:   int = Query(2024, description="End year"),
    top_n: Optional[int] = Query(None, description="Limit to top N countries by total area"),
):
    """Annual area harvested (ha) for a crop."""
    try:
        df = _faostat.get_area(crop, start, end, top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return df.to_dict(orient="records")


@app.get("/crops/{crop}/yield", response_model=list[YieldRecord], tags=["crops"])
def get_yield(
    crop:  str,
    start: int = Query(1990, description="Start year"),
    end:   int = Query(2024, description="End year"),
    top_n: Optional[int] = Query(None, description="Limit to top N countries"),
):
    """Annual yield (kg / ha) for a crop."""
    try:
        df = _faostat.get_yield(crop, start, end, top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return df.to_dict(orient="records")


@app.get("/crops/{crop}/country/{country}", tags=["crops"])
def get_country(
    crop:    str,
    country: str,
    start:   int = Query(1961, description="Start year"),
    end:     int = Query(2024, description="End year"),
):
    """
    All three metrics (production, area, yield) for one country over time.

    Returns a list of annual records.
    """
    try:
        df = _faostat.get_country(crop, country, start, end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    records = df.reset_index().rename(columns={"index": "year"}).to_dict(orient="records")
    return records


@app.get("/crops/{crop}/enrich", response_model=list[EnrichedRecord], tags=["enriched"])
def enrich(
    crop:  str,
    start: int = Query(1990, description="Start year"),
    end:   int = Query(2024, description="End year"),
    top_n: int = Query(10,   description="Top N countries to enrich"),
):
    """
    Production data enriched with World Bank GDP and population.

    Adds:
    - `gdp_bn_usd` - GDP at current USD (billions)
    - `population` - total population
    - `production_per_capita_kg` - kg of crop per person
    - `production_per_gdp_kt_per_bn` - kilotonnes per billion USD of GDP
    """
    try:
        prod = _faostat.get_production(crop, start, end, top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    snap_year  = min(end, 2023)
    countries  = prod["country"].unique().tolist()
    wb         = _worldbank.enrich(countries, snap_year)
    snap_prod  = (
        prod[prod["year"] == prod["year"].max()]
        .groupby("country", as_index=False)["production_tonnes"].sum()
    )
    merged = snap_prod.merge(wb, on="country", how="left")

    def _safe_div(a, b):
        try:
            return round(a / b, 4) if b and b > 0 else None
        except Exception:
            return None

    records = []
    for _, row in merged.iterrows():
        records.append(EnrichedRecord(
            country=row["country"],
            production_tonnes=row.get("production_tonnes"),
            gdp_bn_usd=row.get("gdp_bn_usd"),
            population=row.get("population"),
            production_per_capita_kg=_safe_div(
                row.get("production_tonnes"), row.get("population")
            ),
            production_per_gdp_kt_per_bn=_safe_div(
                (row.get("production_tonnes") or 0) / 1000,
                row.get("gdp_bn_usd"),
            ),
        ))
    return records


@app.get("/brazil/sugarcane", response_model=list[BrazilMetrics], tags=["brazil"])
def brazil_sugarcane(
    start: int = Query(1961, description="Start year"),
    end:   int = Query(2024, description="End year"),
):
    """
    Full Brazil sugarcane time series: production, area, yield, and world share %.
    """
    try:
        brazil = _faostat.get_country("Sugar cane", "Brazil", start, end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    world_prod = (
        _faostat.get_production("Sugar cane", start, end)
        .groupby("year")["production_tonnes"].sum()
    )

    records = []
    for year, row in brazil.iterrows():
        world = world_prod.get(year)
        share = round(row["production_tonnes"] / world * 100, 2) if world else None
        records.append(BrazilMetrics(
            year=int(year),
            production_tonnes=row.get("production_tonnes"),
            area_ha=row.get("area_ha"),
            yield_kg_ha=row.get("yield_kg_ha"),
            world_share_pct=share,
        ))
    return records
