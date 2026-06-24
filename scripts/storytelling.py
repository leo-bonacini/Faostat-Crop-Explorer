"""
Crop Production Explorer + Brazil Sugarcane Storytelling
Uses the faostat package to fetch and enrich data.

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

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
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

# ── Part A data ───────────────────────────────────────────────────────────────
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

# ── Part A enrichment ─────────────────────────────────────────────────────────
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
print("Saved → data/crop_enriched.csv")

# ── Part B: Brazil sugarcane data ─────────────────────────────────────────────
SC_START = 1975
brazil   = faostat.get_country("Sugar cane", "Brazil", SC_START, args.end)
sc_world = faostat.get_production("Sugar cane", SC_START, args.end)
sc_world_total = sc_world.groupby("year")["production_tonnes"].sum() / 1e6

brazil_prod  = brazil["production_tonnes"].dropna() / 1e6
brazil_area  = brazil["area_ha"].dropna()           / 1e6
brazil_yield = brazil["yield_kg_ha"].dropna()       / 1000
brazil_share = (brazil_prod / sc_world_total * 100).dropna()

def world_top_share(year: int, n: int = 6):
    top   = faostat.top_producers("Sugar cane", year, n)
    total = sc_world[sc_world["year"] == year]["production_tonnes"].sum()
    others = total - top["production_tonnes"].sum()
    labels = list(top["country"].str.replace("China, mainland", "China", regex=False)) + ["Others"]
    values = list(top["production_tonnes"]) + [float(others)]
    return labels, values

# ── Styling ───────────────────────────────────────────────────────────────────
BRAND  = "#2E7D32"
ACCENT = "#FDD835"
RED    = "#C62828"
BG     = "#F9FBF9"
DARK   = "#1B1B1B"
GRAY   = "#888888"
BLUE   = "#1565C0"
ORANGE = "#E65100"

CMAP           = plt.colormaps.get_cmap("tab10")
COUNTRY_COLORS = {c: CMAP(i) for i, c in enumerate(top_countries)}
if "Brazil" in COUNTRY_COLORS:
    COUNTRY_COLORS["Brazil"] = ACCENT

MILESTONES = {
    1975: ("ProAlcool\nlaunched", BRAND),
    2003: ("Flex-fuel\ncars",     BLUE),
    2008: ("Food price\ncrisis",  RED),
    2015: ("Paris\nAgreement",   ORANGE),
}

# ── Figure layout ─────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(22, 32), facecolor=BG)
gs  = gridspec.GridSpec(
    5, 2, figure=fig,
    hspace=0.55, wspace=0.36,
    left=0.07, right=0.96,
    top=0.94, bottom=0.04,
    height_ratios=[1.1, 1, 1, 1, 1.2],
)
ax_ts    = fig.add_subplot(gs[0, :])
ax_share = fig.add_subplot(gs[1, 0])
ax_grow  = fig.add_subplot(gs[1, 1])
ax_bprod = fig.add_subplot(gs[2, :])
ax_byld  = fig.add_subplot(gs[3, :])
ax_pie1  = fig.add_subplot(gs[4, 0])
ax_pie2  = fig.add_subplot(gs[4, 1])

for ax in [ax_ts, ax_share, ax_grow, ax_bprod, ax_byld]:
    ax.set_facecolor(BG)
    ax.spines[["top", "right"]].set_visible(False)
    for sp in ax.spines.values():
        sp.set_color("#CCCCCC")

# ─── A1 time-series ───────────────────────────────────────────────────────────
for country in top_countries:
    s   = pivot[country].dropna()
    col = COUNTRY_COLORS[country]
    ax_ts.plot(s.index, s.values, color=col,
               linewidth=2.8 if country == "Brazil" else 1.4,
               zorder=3 if country == "Brazil" else 2)
    if len(s):
        label = (country.replace("China, mainland", "China")
                        .replace("United States of America", "USA")
                        .replace("Bolivia (Plurinational State of)", "Bolivia")
                        .replace("Tanzania, United Republic of", "Tanzania"))
        ax_ts.text(s.index[-1] + 0.5, s.values[-1], label,
                   fontsize=8.5, color=col, va="center")

ax_ts.set_xlim(args.start - 1, args.end + 10)
ax_ts.set_ylabel("Production (million tonnes)", fontsize=10, color=DARK)
ax_ts.set_title(
    f"Global: {args.crop} Production — Top {args.top} Countries ({args.start}–{args.end})",
    fontsize=13, fontweight="bold", color=DARK,
)
ax_ts.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f} Mt"))
ax_ts.grid(axis="y", color="#E0E0E0", linewidth=0.6, zorder=0)

# ─── A2 stacked area ──────────────────────────────────────────────────────────
common_y  = sorted(set(pivot.index) & set(world_total.index))
pivot_pct = pivot.loc[common_y].div(world_total.loc[common_y], axis=0) * 100
pivot_pct = pivot_pct.fillna(0)

ax_share.stackplot(
    common_y,
    [pivot_pct[c].values for c in top_countries],
    labels=[c.replace("China, mainland", "China")
              .replace("United States of America", "USA")
             for c in top_countries],
    colors=[COUNTRY_COLORS[c] for c in top_countries],
    alpha=0.85,
)
ax_share.set_ylabel("% of world production", fontsize=10, color=DARK)
ax_share.set_title(f"World Share — {args.crop}", fontsize=11, fontweight="bold", color=DARK)
ax_share.set_ylim(0, 100)
ax_share.legend(loc="lower left", fontsize=7, ncol=2, framealpha=0.7)
ax_share.grid(axis="y", color="#E0E0E0", linewidth=0.5)

# ─── A3 growth bar ────────────────────────────────────────────────────────────
bar_col3 = [ACCENT if c == "Brazil" else (RED if growth_pct[c] < 0 else BRAND)
            for c in growth_pct.index]
ax_grow.barh(growth_pct.index, growth_pct.values,
             color=bar_col3, edgecolor="white", linewidth=0.4, height=0.7)
ax_grow.axvline(0, color=DARK, linewidth=0.8)
ax_grow.set_xlabel(f"% change {args.start}→{args.end}", fontsize=10, color=DARK)
ax_grow.set_title(f"Growth Rate — {args.crop}", fontsize=11, fontweight="bold", color=DARK)
ax_grow.legend(handles=[
    Line2D([0],[0], color=ACCENT, lw=6, label="Brazil"),
    Line2D([0],[0], color=BRAND,  lw=6, label="Growth"),
    Line2D([0],[0], color=RED,    lw=6, label="Decline"),
], fontsize=8, framealpha=0.6)

# ─── B1 Brazil production + area ─────────────────────────────────────────────
ax_bprod.fill_between(brazil_prod.index, brazil_prod.values, alpha=0.18, color=ACCENT)
l1, = ax_bprod.plot(brazil_prod.index, brazil_prod.values,
                    color=ACCENT, linewidth=2.5, label="Production (Mt)")
ax_b2 = ax_bprod.twinx()
ax_b2.fill_between(brazil_area.index, brazil_area.values, alpha=0.12, color=BRAND)
l2, = ax_b2.plot(brazil_area.index, brazil_area.values,
                 color=BRAND, linewidth=2, linestyle="--", label="Area harvested (Mha)")

for yr, (lbl, col) in MILESTONES.items():
    if brazil_prod.index.min() <= yr <= brazil_prod.index.max():
        ax_bprod.axvline(yr, color=col, linewidth=1.2, linestyle=":", alpha=0.8)
        ax_bprod.text(yr + 0.3, brazil_prod.max() * 0.97, lbl,
                      fontsize=7.5, color=col, va="top")

ax_bprod.set_ylabel("Production (million tonnes)", fontsize=10, color=ACCENT)
ax_b2.set_ylabel("Area harvested (million ha)", fontsize=10, color=BRAND)
ax_bprod.set_title("Brazil · Sugarcane Production & Harvested Area",
                   fontsize=13, fontweight="bold", color=DARK)
ax_bprod.legend(handles=[l1, l2], loc="upper left", fontsize=9, framealpha=0.7)
ax_bprod.grid(axis="y", color="#E0E0E0", linewidth=0.5)
ax_bprod.set_facecolor(BG)
ax_b2.set_facecolor(BG)
ax_b2.spines[["top"]].set_visible(False)
ax_b2.spines["right"].set_color("#CCCCCC")

# ─── B2 Brazil yield + world share ───────────────────────────────────────────
ax_byld.fill_between(brazil_yield.index, brazil_yield.values, alpha=0.2, color=BLUE)
l3, = ax_byld.plot(brazil_yield.index, brazil_yield.values,
                   color=BLUE, linewidth=2.5, label="Yield (t/ha)")
ax_b3 = ax_byld.twinx()
l4, = ax_b3.plot(brazil_share.index, brazil_share.values,
                 color=RED, linewidth=2, linestyle="--", label="Brazil's world share (%)")
ax_b3.fill_between(brazil_share.index, brazil_share.values, alpha=0.08, color=RED)

for yr, (_, col) in MILESTONES.items():
    if brazil_yield.index.min() <= yr <= brazil_yield.index.max():
        ax_byld.axvline(yr, color=col, linewidth=1.2, linestyle=":", alpha=0.8)

ax_byld.set_ylabel("Yield (tonnes per hectare)", fontsize=10, color=BLUE)
ax_b3.set_ylabel("Brazil's share of world production (%)", fontsize=10, color=RED)
ax_byld.set_title("Brazil · Sugarcane Yield Efficiency & World Dominance",
                  fontsize=13, fontweight="bold", color=DARK)
ax_byld.legend(handles=[l3, l4], loc="upper left", fontsize=9, framealpha=0.7)
ax_byld.grid(axis="y", color="#E0E0E0", linewidth=0.5)
ax_byld.set_facecolor(BG)
ax_b3.set_facecolor(BG)
ax_b3.spines[["top"]].set_visible(False)
ax_b3.spines["right"].set_color("#CCCCCC")

# ─── B3 decade pies ──────────────────────────────────────────────────────────
PIE_COLORS = [ACCENT, "#43A047", "#1565C0", "#E65100", "#6A1B9A", "#C62828", "#BDBDBD"]

for ax_pie, year in [(ax_pie1, 1990), (ax_pie2, min(2023, args.end))]:
    labels, values = world_top_share(year)
    short  = [l.replace("China, mainland", "China")
                .replace("United States of America", "USA") for l in labels]
    colors = PIE_COLORS[:len(labels)]
    colors[-1] = "#BDBDBD"
    wedges, texts, autotexts = ax_pie.pie(
        values, labels=short, colors=colors,
        autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
        startangle=140, pctdistance=0.78,
        wedgeprops={"edgecolor": "white", "linewidth": 1.2},
    )
    for t in texts:      t.set_fontsize(8.5)
    for at in autotexts: at.set_fontsize(8)
    total_mt = sum(values) / 1e6
    ax_pie.set_title(f"World Sugarcane Share — {year}\n({total_mt:,.0f} Mt total)",
                     fontsize=11, fontweight="bold", color=DARK, pad=10)

# ─── Master title + section labels ───────────────────────────────────────────
fig.text(0.50, 0.953,
         f"Crop Explorer: {args.crop}  +  Brazil Sugarcane Deep-Dive",
         ha="center", fontsize=19, fontweight="bold", color=DARK)
fig.text(0.50, 0.935,
         "Data: FAOSTAT bulk download  ·  Economic context: World Bank Open API",
         ha="center", fontsize=9.5, color=GRAY, style="italic")

for y_pos, label in [(0.756, "PART A  ·  Global Crop Comparison"),
                     (0.536, "PART B  ·  Brazil Sugarcane Storytelling")]:
    fig.text(0.04, y_pos, label, fontsize=10, fontweight="bold",
             color="white",
             bbox=dict(boxstyle="round,pad=0.35", fc=DARK, ec="none"))

fig.legend(
    handles=[Line2D([0],[0], color=col, lw=1.5, linestyle=":",
                    label=f"{yr}: {lbl.replace(chr(10), ' ')}")
             for yr, (lbl, col) in MILESTONES.items()],
    loc="lower center", ncol=4, fontsize=8, framealpha=0.8,
    bbox_to_anchor=(0.5, 0.01),
    title="Key milestones (Brazil sugarcane)",
)

# ── Save ──────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).parent.parent / "outputs"
out_dir.mkdir(exist_ok=True)
slug = (args.crop.lower()
        .replace(" ", "_").replace("(", "").replace(")", "")
        .replace(";", "").replace(",", ""))
out  = out_dir / f"story_{slug}_{args.start}_{args.end}.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
print(f"Saved → {out}")
plt.show()
