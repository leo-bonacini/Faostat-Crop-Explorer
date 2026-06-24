"""
Crop Production Explorer + Brazil Sugarcane Storytelling
Produces one PNG per chart, saved to outputs/.

Usage:
  python scripts/storytelling.py                         # defaults
  python scripts/storytelling.py --crop "Maize (corn)"  # different crop
  python scripts/storytelling.py --start 2000 --end 2023 --top 8
  python scripts/storytelling.py --list-crops
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).parent.parent))
from faostat import FAOSTATClient, WorldBankClient

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--crop",       default="Sugar cane")
parser.add_argument("--start",      type=int, default=1990)
parser.add_argument("--end",        type=int, default=2024)
parser.add_argument("--top",        type=int, default=10)
parser.add_argument("--list-crops", action="store_true")
args = parser.parse_args()

faostat   = FAOSTATClient()
worldbank = WorldBankClient()

if args.list_crops:
    for c in faostat.list_crops():
        print(f"  {c}")
    sys.exit(0)

print(f"Crop: {args.crop}  |  {args.start}–{args.end}  |  top {args.top}")

# ── Data preparation ──────────────────────────────────────────────────────────
prod_top = faostat.get_production(args.crop, args.start, args.end, top_n=args.top)
top_countries = (
    prod_top.groupby("country")["production_tonnes"].sum()
    .nlargest(args.top).index.tolist()
)
pivot = (
    prod_top.assign(production_mt=lambda d: d["production_tonnes"] / 1e6)
    .pivot_table(index="year", columns="country", values="production_mt", aggfunc="sum")
    .reindex(columns=top_countries)
)
prod_all    = faostat.get_production(args.crop, args.start, args.end)
world_total = prod_all.groupby("year")["production_tonnes"].sum() / 1e6

start_vals = pivot.loc[pivot.index[pivot.index >= args.start].min()]
end_vals   = pivot.loc[pivot.index[pivot.index <= args.end].max()]
growth_pct = ((end_vals - start_vals) / start_vals.replace(0, np.nan) * 100).dropna()
growth_pct = growth_pct.sort_values()

print("Fetching World Bank data…")
snap_year = min(args.end, 2023)
wb_df     = worldbank.enrich(top_countries, snap_year)
snap_prod = (
    prod_top[prod_top["year"] == prod_top["year"].max()]
    .groupby("country", as_index=False)["production_tonnes"].sum()
    .assign(production_mt=lambda d: d["production_tonnes"] / 1e6)
    .merge(wb_df, on="country", how="left")
)
out_data = Path(__file__).parent.parent / "data"
snap_prod.to_csv(out_data / "crop_enriched.csv", index=False)

SC_START = 1975
brazil        = faostat.get_country("Sugar cane", "Brazil", SC_START, args.end)
sc_world      = faostat.get_production("Sugar cane", SC_START, args.end)
sc_world_total = sc_world.groupby("year")["production_tonnes"].sum() / 1e6

brazil_prod  = brazil["production_tonnes"].dropna() / 1e6
brazil_area  = brazil["area_ha"].dropna()           / 1e6
brazil_yield = brazil["yield_kg_ha"].dropna()       / 1000
brazil_share = (brazil_prod / sc_world_total * 100).dropna()

def world_top_share(year: int, n: int = 6):
    top    = faostat.top_producers("Sugar cane", year, n)
    total  = sc_world[sc_world["year"] == year]["production_tonnes"].sum()
    others = total - top["production_tonnes"].sum()
    labels = list(top["country"].str.replace("China, mainland", "China", regex=False)) + ["Others"]
    values = list(top["production_tonnes"]) + [float(others)]
    return labels, values

# ── Styling constants ─────────────────────────────────────────────────────────
BRAND  = "#2E7D32"
ACCENT = "#FDD835"
RED    = "#C62828"
BG     = "#F9FBF9"
DARK   = "#1B1B1B"
GRAY   = "#888888"
BLUE   = "#1565C0"
ORANGE = "#E65100"
SOURCE = "Data: FAOSTAT bulk download  ·  World Bank Open API"

CMAP           = plt.colormaps.get_cmap("tab10")
COUNTRY_COLORS = {c: CMAP(i) for i, c in enumerate(top_countries)}
if "Brazil" in COUNTRY_COLORS:
    COUNTRY_COLORS["Brazil"] = ACCENT

MILESTONES = {
    1975: ("Pró-Álcool launched",    BRAND),
    2003: ("Flex-fuel cars",         BLUE),
    2008: ("Food price crisis",      RED),
    2015: ("Paris Agreement",        ORANGE),
}
PIE_COLORS = [ACCENT, "#43A047", "#1565C0", "#E65100", "#6A1B9A", "#C62828", "#BDBDBD"]

OUT_DIR = Path(__file__).parent.parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

def _style(ax):
    ax.set_facecolor(BG)
    ax.spines[["top", "right"]].set_visible(False)
    for sp in ax.spines.values():
        sp.set_color("#CCCCCC")

def _source(fig):
    fig.text(0.99, 0.01, SOURCE, ha="right", fontsize=7.5,
             color=GRAY, style="italic", transform=fig.transFigure)

def _save(fig, name: str) -> Path:
    path = OUT_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved → outputs/{name}")
    return path

def _shorten(name: str) -> str:
    return (name.replace("China, mainland", "China")
                .replace("United States of America", "USA")
                .replace("Bolivia (Plurinational State of)", "Bolivia")
                .replace("Tanzania, United Republic of", "Tanzania"))

# ── Plot 1 · Global production time series ───────────────────────────────────
def plot_timeseries():
    fig, ax = plt.subplots(figsize=(14, 6), facecolor=BG)
    _style(ax)
    for country in top_countries:
        s   = pivot[country].dropna()
        col = COUNTRY_COLORS[country]
        ax.plot(s.index, s.values, color=col,
                linewidth=2.8 if country == "Brazil" else 1.4,
                zorder=3 if country == "Brazil" else 2)
        if len(s):
            ax.text(s.index[-1] + 0.5, s.values[-1], _shorten(country),
                    fontsize=8.5, color=col, va="center")
    ax.set_xlim(args.start - 1, args.end + 10)
    ax.set_ylabel("Production (million tonnes)", fontsize=11, color=DARK)
    ax.set_title(
        f"{args.crop} Production — Top {args.top} Countries  ({args.start}–{args.end})",
        fontsize=13, fontweight="bold", color=DARK, pad=12,
    )
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f} Mt"))
    ax.grid(axis="y", color="#E0E0E0", linewidth=0.6, zorder=0)
    fig.tight_layout()
    _source(fig)
    _save(fig, "01_global_production_timeseries.png")

# ── Plot 2 · World production share (stacked area) ───────────────────────────
def plot_world_share():
    common_y  = sorted(set(pivot.index) & set(world_total.index))
    pivot_pct = pivot.loc[common_y].div(world_total.loc[common_y], axis=0) * 100
    pivot_pct = pivot_pct.fillna(0)

    fig, ax = plt.subplots(figsize=(12, 6), facecolor=BG)
    _style(ax)
    ax.stackplot(
        common_y,
        [pivot_pct[c].values for c in top_countries],
        labels=[_shorten(c) for c in top_countries],
        colors=[COUNTRY_COLORS[c] for c in top_countries],
        alpha=0.85,
    )
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of world production", fontsize=11, color=DARK)
    ax.set_title(
        f"{args.crop} — Share of World Production  ({args.start}–{args.end})",
        fontsize=13, fontweight="bold", color=DARK, pad=12,
    )
    ax.legend(loc="lower left", fontsize=8, ncol=2, framealpha=0.7)
    ax.grid(axis="y", color="#E0E0E0", linewidth=0.5)
    fig.tight_layout()
    _source(fig)
    _save(fig, "02_global_world_share.png")

# ── Plot 3 · Growth rate ─────────────────────────────────────────────────────
def plot_growth_rate():
    bar_colors = [ACCENT if c == "Brazil" else (RED if growth_pct[c] < 0 else BRAND)
                  for c in growth_pct.index]
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG)
    _style(ax)
    ax.barh([_shorten(c) for c in growth_pct.index], growth_pct.values,
            color=bar_colors, edgecolor="white", linewidth=0.4, height=0.7)
    ax.axvline(0, color=DARK, linewidth=0.8)
    ax.set_xlabel(f"% change from {args.start} to {args.end}", fontsize=11, color=DARK)
    ax.set_title(
        f"{args.crop} — Production Growth Rate  ({args.start}→{args.end})",
        fontsize=13, fontweight="bold", color=DARK, pad=12,
    )
    ax.legend(handles=[
        Line2D([0],[0], color=ACCENT, lw=6, label="Brazil"),
        Line2D([0],[0], color=BRAND,  lw=6, label="Growth"),
        Line2D([0],[0], color=RED,    lw=6, label="Decline"),
    ], fontsize=9, framealpha=0.7)
    fig.tight_layout()
    _source(fig)
    _save(fig, "03_global_growth_rate.png")

# ── Plot 4 · Brazil: production & harvested area ─────────────────────────────
def plot_brazil_production():
    fig, ax1 = plt.subplots(figsize=(14, 6), facecolor=BG)
    _style(ax1)
    ax1.fill_between(brazil_prod.index, brazil_prod.values, alpha=0.18, color=ACCENT)
    l1, = ax1.plot(brazil_prod.index, brazil_prod.values,
                   color=ACCENT, linewidth=2.5, label="Production (Mt)")

    ax2 = ax1.twinx()
    ax2.set_facecolor(BG)
    ax2.spines[["top"]].set_visible(False)
    ax2.spines["right"].set_color("#CCCCCC")
    ax2.fill_between(brazil_area.index, brazil_area.values, alpha=0.12, color=BRAND)
    l2, = ax2.plot(brazil_area.index, brazil_area.values,
                   color=BRAND, linewidth=2, linestyle="--", label="Area harvested (Mha)")

    for yr, (lbl, col) in MILESTONES.items():
        if brazil_prod.index.min() <= yr <= brazil_prod.index.max():
            ax1.axvline(yr, color=col, linewidth=1.2, linestyle=":", alpha=0.85)
            ax1.text(yr + 0.4, brazil_prod.max() * 0.97, lbl,
                     fontsize=8, color=col, va="top")

    ax1.set_ylabel("Production (million tonnes)", fontsize=11, color=ACCENT)
    ax2.set_ylabel("Area harvested (million ha)",  fontsize=11, color=BRAND)
    ax1.set_title("Brazil · Sugarcane Production & Harvested Area  (1975–2024)",
                  fontsize=13, fontweight="bold", color=DARK, pad=12)
    ax1.legend(handles=[l1, l2], loc="upper left", fontsize=9, framealpha=0.7)
    ax1.grid(axis="y", color="#E0E0E0", linewidth=0.5)
    fig.tight_layout()
    _source(fig)
    _save(fig, "04_brazil_production_area.png")

# ── Plot 5 · Brazil: yield efficiency & world dominance ──────────────────────
def plot_brazil_yield():
    fig, ax1 = plt.subplots(figsize=(14, 6), facecolor=BG)
    _style(ax1)
    ax1.fill_between(brazil_yield.index, brazil_yield.values, alpha=0.2, color=BLUE)
    l3, = ax1.plot(brazil_yield.index, brazil_yield.values,
                   color=BLUE, linewidth=2.5, label="Yield (t/ha)")

    ax2 = ax1.twinx()
    ax2.set_facecolor(BG)
    ax2.spines[["top"]].set_visible(False)
    ax2.spines["right"].set_color("#CCCCCC")
    ax2.fill_between(brazil_share.index, brazil_share.values, alpha=0.08, color=RED)
    l4, = ax2.plot(brazil_share.index, brazil_share.values,
                   color=RED, linewidth=2, linestyle="--", label="Brazil's world share (%)")

    for yr, (lbl, col) in MILESTONES.items():
        if brazil_yield.index.min() <= yr <= brazil_yield.index.max():
            ax1.axvline(yr, color=col, linewidth=1.2, linestyle=":", alpha=0.85)
            ax1.text(yr + 0.4, brazil_yield.max() * 0.97, lbl,
                     fontsize=8, color=col, va="top")

    ax1.set_ylabel("Yield (tonnes per hectare)",              fontsize=11, color=BLUE)
    ax2.set_ylabel("Brazil's share of world production (%)", fontsize=11, color=RED)
    ax1.set_title("Brazil · Sugarcane Yield Efficiency & World Dominance  (1975–2024)",
                  fontsize=13, fontweight="bold", color=DARK, pad=12)
    ax1.legend(handles=[l3, l4], loc="upper left", fontsize=9, framealpha=0.7)
    ax1.grid(axis="y", color="#E0E0E0", linewidth=0.5)

    # Milestone legend below chart
    fig.legend(
        handles=[Line2D([0],[0], color=col, lw=1.5, linestyle=":", label=f"{yr}: {lbl}")
                 for yr, (lbl, col) in MILESTONES.items()],
        loc="lower center", ncol=4, fontsize=8, framealpha=0.8,
        bbox_to_anchor=(0.5, -0.06),
    )
    fig.tight_layout()
    _source(fig)
    _save(fig, "05_brazil_yield_dominance.png")

# ── Plot 6 · World share comparison pies (1990 vs latest) ────────────────────
def plot_world_pies():
    pie_year_2 = min(2023, args.end)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7), facecolor=BG)

    for ax, year in [(ax1, 1990), (ax2, pie_year_2)]:
        ax.set_facecolor(BG)
        labels, values = world_top_share(year)
        short  = [_shorten(l) for l in labels]
        colors = PIE_COLORS[:len(labels)]
        colors[-1] = "#BDBDBD"
        wedges, texts, autotexts = ax.pie(
            values, labels=short, colors=colors,
            autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
            startangle=140, pctdistance=0.78,
            wedgeprops={"edgecolor": "white", "linewidth": 1.4},
        )
        for t  in texts:     t.set_fontsize(9.5)
        for at in autotexts: at.set_fontsize(8.5)
        total_mt = sum(values) / 1e6
        ax.set_title(f"World Sugarcane Share — {year}\n({total_mt:,.0f} Mt total)",
                     fontsize=12, fontweight="bold", color=DARK, pad=14)

    fig.suptitle("Who Grew the World's Sugarcane?  1990 vs 2023",
                 fontsize=14, fontweight="bold", color=DARK, y=1.02)
    _source(fig)
    _save(fig, "06_world_share_comparison.png")

# ── Run all plots ─────────────────────────────────────────────────────────────
print("\nGenerating plots…")
plot_timeseries()
plot_world_share()
plot_growth_rate()
plot_brazil_production()
plot_brazil_yield()
plot_world_pies()
print(f"\nAll plots saved to outputs/")
