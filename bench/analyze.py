"""Turn a benchmark JSON (scale mode) into a chart + markdown analysis.

    python3 bench/analyze.py out/benchmark_scale.json --out out/scaling

Writes <out>.png (wall-time + placement-rate vs n_sections) and <out>.md
(a table + headline numbers). matplotlib/pandas are local-only deps, so this
runs on the workstation, not inside the lean Cloud Run Job image.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("json", help="benchmark JSON from --scale")
    ap.add_argument("--out", default="out/scaling", help="output stem (.png/.md)")
    args = ap.parse_args()

    data = json.loads(Path(args.json).read_text())
    env = data["env"]
    rows = sorted((s for s in data["summary"] if s["label"].startswith("n")),
                  key=lambda s: s["n_sections"])
    if not rows:
        raise SystemExit("no scale cells (labels like 'n400') in this JSON")

    ns = [s["n_sections"] for s in rows]
    walls = [s["wall_s_median"] for s in rows]
    rates = [(s["placement_rate_median"] or 0) * 100 for s in rows]
    conflicts = [s["genuine_conflicts_max"] for s in rows]

    # --- chart ---
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    ax1.plot(ns, walls, "o-", color="#2b3a8c")
    ax1.set_xlabel("number of sections")
    ax1.set_ylabel("median wall time (s)")
    ax1.set_title("Solve time vs. problem size")
    ax1.grid(True, alpha=.3)
    ax2.plot(ns, rates, "s-", color="#1b7f4b")
    ax2.set_xlabel("number of sections")
    ax2.set_ylabel("placement rate (%)")
    ax2.set_ylim(min(90, min(rates) - 2), 100.5)
    ax2.set_title("Placement rate vs. problem size")
    ax2.grid(True, alpha=.3)
    fig.suptitle(f"KAIROS scaling — budget {env['time_limit_s']:.0f}s, "
                 f"cpu={env['cpu_count']}, runs={rows[0]['runs']}")
    fig.tight_layout()
    png = Path(args.out).with_suffix(".png")
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=130)

    # --- markdown ---
    lines = [
        f"# KAIROS scaling analysis (by section count)",
        "",
        f"- Environment: `{env['platform']}`, cpu={env['cpu_count']}, "
        f"python {env['python']}",
        f"- Repair budget: {env['time_limit_s']:.0f}s · repeats per size: "
        f"{rows[0]['runs']} · solver: `{rows[0]['solver']}`",
        "",
        "| n_sections | rooms | sec/room | blocks | wall median (s) | "
        "wall min–max | placement % | genuine conflicts |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in rows:
        nr = s.get("n_rooms")
        ratio = f"{s['n_sections'] / nr:.1f}" if nr else "—"
        lines.append(
            f"| {s['n_sections']} | {nr or '—'} | {ratio} | {s['n_blocks']} | "
            f"{s['wall_s_median']} | {s['wall_s_min']}–{s['wall_s_max']} | "
            f"{(s['placement_rate_median'] or 0) * 100:.1f} | "
            f"{s['genuine_conflicts_max']} |")
    # headline scaling factor (wall growth from smallest to largest)
    if walls[0] > 0:
        grow = walls[-1] / walls[0]
        lines += ["",
                  f"**Wall time grows ~{grow:.1f}× from {ns[0]} to {ns[-1]} "
                  f"sections** ({walls[0]:.1f}s → {walls[-1]:.1f}s). "
                  f"Placement stays ≥{min(rates):.1f}% with "
                  f"{max(conflicts)} genuine hard conflicts at worst."]
    md = Path(args.out).with_suffix(".md")
    md.write_text("\n".join(lines) + "\n")

    print(f"[done] wrote {png} and {md}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
