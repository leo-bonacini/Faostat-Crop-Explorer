# faostat

Python library for querying the FAOSTAT crop production dataset.

The 34 MB bulk zip is downloaded automatically on first use and cached in
`data/faostat_bulk.csv`. It is refreshed after 7 days.

---

## Classes

### `FAOSTATClient`

```python
from faostat import FAOSTATClient

client = FAOSTATClient()               # default: refresh cache after 7 days
client = FAOSTATClient(cache_max_days=30)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `list_crops()` | `list[str]` | All 301 crop names in the dataset |
| `get_production(crop, start, end, top_n)` | `DataFrame` | Annual production (tonnes) |
| `get_area(crop, start, end, top_n)` | `DataFrame` | Annual area harvested (ha) |
| `get_yield(crop, start, end, top_n)` | `DataFrame` | Annual yield (kg / ha) |
| `get_country(crop, country, start, end)` | `DataFrame` | All three metrics for one country, indexed by year |
| `top_producers(crop, year, n)` | `DataFrame` | Top N producers for a single year |

### `WorldBankClient`

```python
from faostat import WorldBankClient

wb = WorldBankClient()
```

| Method | Returns | Description |
|--------|---------|-------------|
| `get_gdp(iso3, year)` | `float \| None` | GDP at current USD |
| `get_population(iso3, year)` | `float \| None` | Total population |
| `enrich(countries, year)` | `DataFrame` | GDP (bn USD) and population for a list of FAO country names |

---

## Usage examples

```python
from faostat import FAOSTATClient, WorldBankClient

client = FAOSTATClient()

# Browse available crops
client.list_crops()
# ['Abaca, manila hemp, raw', 'Almonds, in shell', ..., 'Wheat', ...]

# Top 5 sugarcane producers in 2023
client.top_producers("Sugar cane", year=2023, n=5)
#  rank          country  production_tonnes
#     1           Brazil       782058236.0
#     2            India       490533351.0
#     3            China       105075026.0
#     4         Thailand        93981770.0
#     5         Pakistan        89100000.0

# Brazil sugarcane: production, area, yield - all years
brazil = client.get_country("Sugar cane", "Brazil", start=1975, end=2024)
#       production_tonnes    area_ha  yield_kg_ha
# year
# 1975       91530649.0   1969800.0      46465.0
# ...
# 2023      782058236.0  10048731.0      77829.0

# Wheat production 2000–2023, top 8 countries
wheat = client.get_production("Wheat", start=2000, end=2023, top_n=8)

# Enrich with World Bank data
wb = WorldBankClient()
wb.enrich(["Brazil", "India", "China, mainland"], year=2023)
#              country  gdp_bn_usd  population
#               Brazil    2173.664   216422446
#                India    3549.919  1428627663
#      China, mainland   17794.782  1409670000
```

---

## Crop name reference (common crops)

| Crop | Name to pass |
|------|-------------|
| Sugarcane | `Sugar cane` |
| Maize | `Maize (corn)` |
| Wheat | `Wheat` |
| Rice | `Rice` |
| Soybeans | `Soya beans` |
| Coffee | `Coffee, green` |
| Cocoa | `Cocoa beans` |
| Bananas | `Bananas` |
| Potatoes | `Potatoes` |
| Cotton | `Seed cotton, unginned` |

Run `client.list_crops()` for the full list of 301 options.
