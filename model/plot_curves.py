"""Training curves for MODEL.md from model/results/<run>/log.csv (same data as W&B).

    python -m model.plot_curves --run arranger-v1

Four small multiples, one y-axis each: training loss per head (EMA-smoothed), validation
accuracy per head, predicted vs true non-plain realisation share, and per-class realisation
recall. Validation = the fixed phase-one windows (val_r0). Dashed line = start of phase two.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # categorical slots 1-4 (reference palette)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def ema(v, a=0.05):
    out, m = [], None
    for x in v:
        m = x if m is None else (1 - a) * m + a * x
        out.append(m)
    return out


def panel(ax, title, series, phase2, ylim=None, fmt=None):
    for (name, xs, ys), c in zip(series, S):
        ax.plot(xs, ys, color=c, lw=2, solid_capstyle="round")
    if ylim:
        ax.set_ylim(*ylim)
    # end labels, spread apart so they never collide (min gap 6% of the axis height)
    lo, hi = ax.get_ylim()
    ends = sorted(((ys[-1], name, xs[-1]) for name, xs, ys in series), key=lambda e: e[0])
    gap, placed = 0.06 * (hi - lo), []
    for y, name, x in ends:
        y2 = max(y, placed[-1] + gap) if placed else y
        placed.append(y2)
        ax.annotate("  " + name, (x, y), xytext=(x, y2), textcoords="data", va="center", fontsize=9, color=INK2,
                    annotation_clip=False)
    ax.set_xlim(right=max(xs[-1] for _, xs, _ in series) * 1.0)
    ax.axvline(phase2, color=MUTED, lw=1, ls=(0, (4, 3)))
    ax.text(phase2, 0.02, " phase two", transform=ax.get_xaxis_transform(), fontsize=8, color=MUTED, va="bottom")
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_xlabel("step", fontsize=8, color=MUTED)
    if fmt:
        ax.yaxis.set_major_formatter(fmt)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="arranger-v1")
    a = ap.parse_args(argv)
    rd = ROOT / "model" / "results" / a.run
    rows = list(csv.DictReader(open(rd / "log.csv")))
    import json
    cfg = json.loads((rd / "config.json").read_text())
    st = [int(r["step"]) for r in rows]
    val = [r for r in rows if _f(r.get("val_r0/loss")) is not None and int(r["step"]) > 0]   # step 0 = random init
    vs = [int(r["step"]) for r in val]
    pct = matplotlib.ticker.PercentFormatter(1.0, decimals=0)
    fig, axs = plt.subplots(2, 2, figsize=(11, 7), facecolor=SURFACE)
    panel(axs[0, 0], "Training loss per head (smoothed)",
          [(n, st, ema([_f(r[f"train/loss_{k}"]) for r in rows])) for n, k in
           (("part", "part"), ("octave", "octave"), ("realisation", "real"))], cfg["phase1_steps"])
    panel(axs[0, 1], "Validation accuracy per head",
          [(n, vs, [_f(r[f"val_r0/acc_{k}"]) for r in val]) for n, k in
           (("part", "part"), ("octave", "octave"), ("realisation", "real"))], cfg["phase1_steps"],
          ylim=(0.5, 1.0), fmt=pct)
    panel(axs[1, 0], "Non-plain realisation share (validation)",
          [("predicted", vs, [_f(r["val_r0/frac_pred_nonplain"]) for r in val]),
           ("true", vs, [_f(r["val_r0/frac_true_nonplain"]) for r in val])], cfg["phase1_steps"],
          fmt=matplotlib.ticker.PercentFormatter(1.0, decimals=1))
    panel(axs[1, 1], "Realisation recall by class (validation)",
          [(n, vs, [_f(r[f"val_r0/recall_{n}"]) or 0.0 for r in val])
           for n in ("arpeggiate", "repeat", "tremolo", "double")], cfg["phase1_steps"], ylim=(0, 1), fmt=pct)
    fig.suptitle(f"{a.run}: {cfg['n_params'] / 1e6:.1f}M parameters, {cfg['steps']:,} steps", x=0.01, ha="left",
                 fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0, 0.96, 0.96))
    out = rd / "curves.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    print(out)


if __name__ == "__main__":
    main()
