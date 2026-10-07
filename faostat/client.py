"""
FAOSTATClient - downloads and caches the FAOSTAT bulk crop/livestock dataset.

The 34 MB zip is saved to data/faostat_bulk.csv and refreshed automatically
after CACHE_MAX_DAYS days so callers always work from a local file.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

_BULK_URL = (
    "https://fenixservices.fao.org/faostat/static/bulkdownloads/"
    "Production_Crops_Livestock_E_All_Data_(Normalized).zip"
)
_CACHE_FILE = Path(__file__).parent.parent / "data" / "faostat_bulk.csv"
_ITEMS_FILE = Path(__file__).parent.parent / "data" / "faostat_items.csv"

ELEMENT_PRODUCTION = 5510
ELEMENT_AREA       = 5312
ELEMENT_YIELD      = 5412


class FAOSTATClient:
    """
    Thin wrapper around the FAOSTAT bulk crop production dataset.

    Parameters
    ----------
    cache_max_days : int
        Re-download the source data after this many days (default 7).
    """

    def __init__(self, cache_max_days: int = 7) -> None:
        self._cache_max_days = cache_max_days
        self._df: pd.DataFrame | None = None
        self._items: pd.DataFrame | None = None

    # public

    def list_crops(self) -> list[str]:
        """Return all crop names present in the dataset."""
        df = self._load()
        return sorted(df["Item"].dropna().unique().tolist())

    def get_production(
        self,
        crop: str,
        start: int = 1990,
        end: int = 2024,
        top_n: int | None = None,
    ) -> pd.DataFrame:
        """
        Annual production (tonnes) for *crop* between *start* and *end*.

        Returns a DataFrame with columns [country, year, production_tonnes].
        If *top_n* is given, only the top N countries by total production
        over the period are included.
        """
        return self._fetch(crop, ELEMENT_PRODUCTION, "production_tonnes", start, end, top_n)

    def get_area(
        self,
        crop: str,
        start: int = 1990,
        end: int = 2024,
        top_n: int | None = None,
    ) -> pd.DataFrame:
        """Annual area harvested (ha) for *crop*."""
        return self._fetch(crop, ELEMENT_AREA, "area_ha", start, end, top_n)

    def get_yield(
        self,
        crop: str,
        start: int = 1990,
        end: int = 2024,
        top_n: int | None = None,
    ) -> pd.DataFrame:
        """Annual yield (kg / ha) for *crop*."""
        return self._fetch(crop, ELEMENT_YIELD, "yield_kg_ha", start, end, top_n)

    def get_country(
        self,
        crop: str,
        country: str,
        start: int = 1961,
        end: int = 2024,
    ) -> pd.DataFrame:
        """
        All three metrics (production, area, yield) for one country.

        Returns a DataFrame indexed by year with columns
        [production_tonnes, area_ha, yield_kg_ha].
        """
        prod  = self._fetch(crop, ELEMENT_PRODUCTION, "production_tonnes", start, end)
        area  = self._fetch(crop, ELEMENT_AREA,       "area_ha",           start, end)
        yld   = self._fetch(crop, ELEMENT_YIELD,      "yield_kg_ha",       start, end)

        def _filter(df: pd.DataFrame, val_col: str) -> pd.Series:
            sub = df[df["country"] == country].set_index("year")[val_col]
            return sub

        result = pd.DataFrame({
            "production_tonnes": _filter(prod, "production_tonnes"),
            "area_ha":           _filter(area, "area_ha"),
            "yield_kg_ha":       _filter(yld,  "yield_kg_ha"),
        })
        result.index.name = "year"
        return result.dropna(how="all")

    def top_producers(
        self,
        crop: str,
        year: int,
        n: int = 10,
    ) -> pd.DataFrame:
        """
        Top *n* producers for *crop* in a single *year*.

        Returns a DataFrame with columns [rank, country, production_tonnes].
        """
        prod = self._fetch(crop, ELEMENT_PRODUCTION, "production_tonnes", year, year)
        return (
            prod[prod["year"] == year]
            .sort_values("production_tonnes", ascending=False)
            .head(n)
            .reset_index(drop=True)
            .assign(rank=lambda d: d.index + 1)
            [["rank", "country", "production_tonnes"]]
        )

    # internal

    def _fetch(
        self,
        crop: str,
        element_code: int,
        value_col: str,
        start: int,
        end: int,
        top_n: int | None = None,
    ) -> pd.DataFrame:
        df = self._load()

        item_code = self._resolve_crop(crop)

        mask = (
            (df["Item Code"] == item_code) &
            (df["Element Code"] == element_code) &
            (df["_is_country"]) &
            (df["Year"] >= start) &
            (df["Year"] <= end)
        )
        result = (
            df[mask][["Area", "Year", "Value"]]
            .rename(columns={"Area": "country", "Year": "year", "Value": value_col})
            .dropna(subset=[value_col])
            .copy()
        )

        if top_n is not None:
            totals = result.groupby("country")[value_col].sum()
            keep   = totals.nlargest(top_n).index
            result = result[result["country"].isin(keep)]

        return result.reset_index(drop=True)

    def _resolve_crop(self, crop: str) -> int:
        df = self._load()
        items = df[["Item Code", "Item"]].drop_duplicates()
        # exact match first
        exact = items[items["Item"].str.lower() == crop.lower()]
        if not exact.empty:
            return int(exact.iloc[0]["Item Code"])
        # fuzzy
        fuzzy = items[items["Item"].str.contains(crop, case=False, na=False)]
        if not fuzzy.empty:
            return int(fuzzy.iloc[0]["Item Code"])
        available = sorted(items["Item"].dropna().unique().tolist())
        raise ValueError(
            f"Crop '{crop}' not found. "
            f"Use list_crops() to see options. "
            f"Partial matches: {[c for c in available if crop.lower() in c.lower()][:5]}"
        )

    def _load(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        if self._needs_refresh():
            self._download()
        self._df = pd.read_csv(_CACHE_FILE, low_memory=False)
        # pre-compute country flag (Area Code < 1000 = real country)
        self._df["_is_country"] = self._df["Area Code"] < 1000
        return self._df

    def _needs_refresh(self) -> bool:
        if not _CACHE_FILE.exists():
            return True
        age = datetime.now() - datetime.fromtimestamp(_CACHE_FILE.stat().st_mtime)
        return age > timedelta(days=self._cache_max_days)

    def _download(self) -> None:
        print("Downloading FAOSTAT bulk data (~34 MB)…")
        resp = requests.get(_BULK_URL, timeout=180)
        resp.raise_for_status()
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            csv_name = "Production_Crops_Livestock_E_All_Data_(Normalized).csv"
            with z.open(csv_name) as f:
                df = pd.read_csv(f, encoding="latin-1", low_memory=False)
        df.to_csv(_CACHE_FILE, index=False)
        print(f"Cached → {_CACHE_FILE}")
