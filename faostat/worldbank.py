"""
WorldBankClient - thin wrapper around the World Bank open data API.

No API key is required. Fetches GDP and population per country/year
and joins them onto a FAOSTAT production DataFrame.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

_BASE_URL = "https://api.worldbank.org/v2/country/{iso3}/indicator/{indicator}"

# FAO country name → ISO-3 alpha code
NAME_TO_ISO3: dict[str, str] = {
    "Argentina": "ARG",
    "Australia": "AUS",
    "Bangladesh": "BGD",
    "Bolivia (Plurinational State of)": "BOL",
    "Brazil": "BRA",
    "Cambodia": "KHM",
    "Canada": "CAN",
    "China, mainland": "CHN",
    "Colombia": "COL",
    "Cuba": "CUB",
    "Ecuador": "ECU",
    "Egypt": "EGY",
    "Ethiopia": "ETH",
    "France": "FRA",
    "Germany": "DEU",
    "Guatemala": "GTM",
    "India": "IND",
    "Indonesia": "IDN",
    "Iran (Islamic Republic of)": "IRN",
    "Italy": "ITA",
    "Japan": "JPN",
    "Kazakhstan": "KAZ",
    "Kenya": "KEN",
    "Mexico": "MEX",
    "Mozambique": "MOZ",
    "Myanmar": "MMR",
    "Nigeria": "NGA",
    "Pakistan": "PAK",
    "Peru": "PER",
    "Philippines": "PHL",
    "Poland": "POL",
    "Romania": "ROU",
    "Russian Federation": "RUS",
    "South Africa": "ZAF",
    "Spain": "ESP",
    "Sri Lanka": "LKA",
    "Sudan": "SDN",
    "Tanzania, United Republic of": "TZA",
    "Thailand": "THA",
    "Turkey": "TUR",
    "Ukraine": "UKR",
    "United Kingdom": "GBR",
    "United States of America": "USA",
    "Viet Nam": "VNM",
}


class WorldBankClient:
    """
    Fetch GDP and population from the World Bank open API.

    Parameters
    ----------
    rate_limit_s : float
        Seconds to sleep between requests (default 0.15).
    timeout : int
        HTTP timeout in seconds (default 10).
    """

    def __init__(self, rate_limit_s: float = 0.15, timeout: int = 10) -> None:
        self._sleep = rate_limit_s
        self._timeout = timeout

    def get_gdp(self, iso3: str, year: int) -> float | None:
        """GDP at current USD for *iso3* in *year*."""
        return self._fetch(iso3, "NY.GDP.MKTP.CD", year)

    def get_population(self, iso3: str, year: int) -> float | None:
        """Total population for *iso3* in *year*."""
        return self._fetch(iso3, "SP.POP.TOTL", year)

    def enrich(
        self,
        countries: list[str],
        year: int,
    ) -> pd.DataFrame:
        """
        Return a DataFrame with GDP (billion USD) and population for each country.

        Parameters
        ----------
        countries : list[str]
            FAO country names (matched against NAME_TO_ISO3).
        year : int
            Reference year. If data for *year* is missing the most recent
            available value is used (World Bank mrv=1 behaviour).
        """
        rows = []
        for country in countries:
            iso3 = NAME_TO_ISO3.get(country)
            if iso3 is None:
                rows.append({"country": country, "gdp_bn_usd": None, "population": None})
                continue
            gdp = self._fetch(iso3, "NY.GDP.MKTP.CD", year)
            pop = self._fetch(iso3, "SP.POP.TOTL",    year)
            rows.append({
                "country":    country,
                "gdp_bn_usd": round(gdp / 1e9, 3) if gdp else None,
                "population": int(pop)             if pop else None,
            })
            time.sleep(self._sleep)
        return pd.DataFrame(rows)

    # internal

    def _fetch(self, iso3: str, indicator: str, year: int) -> float | None:
        url = _BASE_URL.format(iso3=iso3, indicator=indicator)
        try:
            resp = requests.get(
                url,
                params={"format": "json", "date": str(year), "mrv": "1"},
                timeout=self._timeout,
            )
            data = resp.json()
            val  = data[1][0].get("value") if data and len(data) > 1 and data[1] else None
            return float(val) if val is not None else None
        except Exception:
            return None
