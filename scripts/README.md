# scripts

Generates a two-part storytelling chart saved to `outputs/`.

## Usage

```bash
# Default: sugarcane global view, 1990–2024, top 10 countries
python3 scripts/storytelling.py

# Switch the global comparison to a different crop
python3 scripts/storytelling.py --crop "Maize (corn)"
python3 scripts/storytelling.py --crop "Wheat" --start 2000 --end 2023 --top 8
python3 scripts/storytelling.py --crop "Coffee, green" --top 5

# List all 301 available crop names
python3 scripts/storytelling.py --list-crops
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--crop` | `Sugar cane` | Crop for the global comparison (Part A) |
| `--start` | `1990` | Start year |
| `--end` | `2024` | End year |
| `--top` | `10` | Number of top countries to include |
| `--list-crops` | — | Print all available crop names and exit |

## Output

The chart is saved to `outputs/story_{crop}_{start}_{end}.png`.

## Chart structure

**Part A — Global crop comparison** *(switches with `--crop`)*

- Time-series lines for the top N countries
- Stacked area showing each country's share of world production
- Growth rate bar chart from start year to end year

**Part B — Brazil sugarcane storytelling** *(always fixed)*

- Production volume and harvested area since 1975, with key policy milestones annotated:
  - 1975: Pró-Álcool programme launched
  - 2003: Flex-fuel cars introduced
  - 2008: Global food price crisis
  - 2015: Paris Agreement
- Yield efficiency (t/ha) vs Brazil's world share % on a dual axis
- Pie charts comparing world production share in 1990 vs the latest available year
