"""
QSH Fleet Simulation Results Report.

Reads fleet.db (from batch.py) and produces summary statistics
showing energy savings, COP improvements, and comfort metrics
across all archetypes and climate zones.

Usage:
    python -m qsh.twin.fleet_report --db /mnt/d/qsh-data/results/fleet.db
    python -m qsh.twin.fleet_report --db fleet.db --output /mnt/d/qsh-data/results/
    python -m qsh.twin.fleet_report --db fleet.db --format csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Data loading ─────────────────────────────────────────────────────


def _connect_readonly(db_path: str) -> sqlite3.Connection:
    """Open fleet.db in read-only mode."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _load_completed_runs(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Load all completed runs (where total_kwh IS NOT NULL)."""
    cursor = conn.execute("""
        SELECT
            run_id, archetype, weather_location, strategy,
            hours_simulated, total_kwh, total_cost_gbp,
            mean_cop, mean_room_temp, min_room_temp,
            hours_below_setpoint, mean_flow_temp, max_flow_temp,
            savings_kwh, savings_pct, mean_cop_improvement,
            skynet_cost_kwh
        FROM runs
        WHERE total_kwh IS NOT NULL
        ORDER BY archetype, weather_location, strategy
    """)
    return [dict(row) for row in cursor.fetchall()]


# ── Analysis ─────────────────────────────────────────────────────────


def _group_runs(runs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]:
    """Group runs by archetype -> weather_location -> strategy.

    Returns:
        Nested dict: {archetype: {zone: {strategy: run_dict}}}
    """
    grouped: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
    for run in runs:
        arch = run["archetype"]
        zone = run["weather_location"]
        strat = run["strategy"]
        grouped.setdefault(arch, {}).setdefault(zone, {})[strat] = run
    return grouped


def build_report(db_path: str) -> Dict[str, Any]:
    """Build the full fleet report from fleet.db.

    Args:
        db_path: Path to fleet.db SQLite database.

    Returns:
        Report dict with per-archetype, per-zone, and fleet-wide stats.
    """
    conn = _connect_readonly(db_path)
    runs = _load_completed_runs(conn)
    conn.close()

    if not runs:
        return {
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "run_count": 0,
            "message": "No completed runs found in database.",
        }

    grouped = _group_runs(runs)

    # Per-archetype × zone comparison rows
    comparison_rows: List[Dict[str, Any]] = []
    all_savings: List[float] = []
    all_cop_improvements: List[float] = []
    all_skynet_costs: List[float] = []
    worst_min_temp = 100.0
    worst_case_arch = ""
    worst_case_zone = ""

    per_archetype: Dict[str, Dict[str, Any]] = {}
    per_zone: Dict[str, Dict[str, Any]] = {}

    for arch, zones in sorted(grouped.items()):
        arch_savings: List[float] = []
        arch_cop_improvements: List[float] = []

        for zone, strategies in sorted(zones.items()):
            stock_run = strategies.get("stock")
            capped_run = strategies.get("qsh_capped")

            if not stock_run:
                continue

            stock_kwh = stock_run["total_kwh"]
            stock_cop = stock_run.get("mean_cop", 0) or 0

            # Track worst-case comfort across all strategies
            for strat_run in strategies.values():
                min_temp = strat_run.get("min_room_temp")
                if min_temp is not None and min_temp < worst_min_temp:
                    worst_min_temp = min_temp
                    worst_case_arch = arch
                    worst_case_zone = zone

            if capped_run:
                capped_kwh = capped_run["total_kwh"] or 0
                savings_pct = capped_run.get("savings_pct")
                if savings_pct is None and stock_kwh and stock_kwh > 0:
                    savings_pct = ((stock_kwh - capped_kwh) / stock_kwh) * 100.0

                cop_delta = capped_run.get("mean_cop_improvement")
                if cop_delta is None:
                    capped_cop = capped_run.get("mean_cop", 0) or 0
                    cop_delta = capped_cop - stock_cop

                min_room = capped_run.get("min_room_temp", 0) or 0
                skynet_cost = capped_run.get("skynet_cost_kwh")

                row = {
                    "archetype": arch,
                    "zone": zone,
                    "stock_kwh": round(stock_kwh, 1) if stock_kwh else 0,
                    "qsh_kwh": round(capped_kwh, 1),
                    "savings_pct": round(savings_pct, 1) if savings_pct is not None else None,
                    "cop_delta": round(cop_delta, 2) if cop_delta is not None else None,
                    "min_room_temp": round(min_room, 1),
                    "skynet_cost_kwh": round(skynet_cost, 1) if skynet_cost is not None else None,
                }
                comparison_rows.append(row)

                if savings_pct is not None:
                    all_savings.append(savings_pct)
                    arch_savings.append(savings_pct)
                if cop_delta is not None:
                    all_cop_improvements.append(cop_delta)
                    arch_cop_improvements.append(cop_delta)
                if skynet_cost is not None:
                    all_skynet_costs.append(skynet_cost)

            # Per-zone aggregation
            per_zone.setdefault(zone, {"savings": [], "cop_improvements": []})
            if capped_run and savings_pct is not None:
                per_zone[zone]["savings"].append(savings_pct)
            if capped_run and cop_delta is not None:
                per_zone[zone]["cop_improvements"].append(cop_delta)

        # Per-archetype summary
        per_archetype[arch] = {
            "mean_savings_pct": round(_safe_mean(arch_savings), 1),
            "mean_cop_improvement": round(_safe_mean(arch_cop_improvements), 2),
            "zones_tested": len(zones),
        }

    # Finalise per-zone summaries
    per_zone_summary: Dict[str, Dict[str, Any]] = {}
    for zone, data in sorted(per_zone.items()):
        per_zone_summary[zone] = {
            "mean_savings_pct": round(_safe_mean(data["savings"]), 1),
            "mean_cop_improvement": round(_safe_mean(data["cop_improvements"]), 2),
            "archetypes_tested": len(data["savings"]),
        }

    report: Dict[str, Any] = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_count": len(runs),
        "mean_savings_pct": round(_safe_mean(all_savings), 1),
        "mean_cop_improvement": round(_safe_mean(all_cop_improvements), 2),
        "worst_min_room_temp_c": round(worst_min_temp, 1) if worst_min_temp < 100.0 else None,
        "worst_case_archetype": worst_case_arch or None,
        "worst_case_zone": worst_case_zone or None,
        "mean_skynet_cost_kwh": round(_safe_mean(all_skynet_costs), 1) if all_skynet_costs else None,
        "comparison_rows": comparison_rows,
        "per_archetype": per_archetype,
        "per_zone": per_zone_summary,
    }

    return report


def _safe_mean(values: List[float]) -> float:
    """Mean that returns 0.0 for empty lists."""
    return sum(values) / len(values) if values else 0.0


# ── Output formatters ────────────────────────────────────────────────


def format_table(report: Dict[str, Any]) -> str:
    """Format report as a human-readable table."""
    lines: List[str] = []

    lines.append("QSH Fleet Simulation Report")
    lines.append("=" * 28)
    lines.append(f"{report['run_count']} runs analysed")
    lines.append("")

    rows = report.get("comparison_rows", [])
    if not rows:
        lines.append("No comparison data available (need stock + qsh_capped runs).")
        return "\n".join(lines)

    lines.append("Savings vs Stock Baseline")
    lines.append("-" * 25)
    lines.append(
        f"{'Archetype':<30s} | {'Zone':<16s} | {'Stock kWh':>9s} | {'QSH kWh':>8s} | "
        f"{'Savings %':>9s} | {'COP D':>6s} | {'Min Room C':>10s}"
    )
    lines.append(
        f"{'-' * 30}-+-{'-' * 16}-+-{'-' * 9}-+-{'-' * 8}-+-"
        f"{'-' * 9}-+-{'-' * 6}-+-{'-' * 10}"
    )

    # Look up archetype labels
    try:
        from twin.archetypes.archetypes import UK_ARCHETYPES
        label_map = {k: v["label"] for k, v in UK_ARCHETYPES.items()}
    except ImportError:
        label_map = {}

    for row in rows:
        arch_label = label_map.get(row["archetype"], row["archetype"])
        savings_str = f"{row['savings_pct']:.1f}%" if row["savings_pct"] is not None else "N/A"
        cop_str = f"+{row['cop_delta']:.2f}" if row["cop_delta"] is not None else "N/A"
        lines.append(
            f"{arch_label:<30s} | {row['zone']:<16s} | {row['stock_kwh']:>9.1f} | {row['qsh_kwh']:>8.1f} | "
            f"{savings_str:>9s} | {cop_str:>6s} | {row['min_room_temp']:>10.1f}"
        )

    lines.append("")
    lines.append("Fleet Summary")
    lines.append("-" * 14)
    lines.append(f"Mean savings (qsh_capped): {report.get('mean_savings_pct', 0):.1f}%")
    lines.append(f"Mean COP improvement: +{report.get('mean_cop_improvement', 0):.2f}")

    worst = report.get("worst_min_room_temp_c")
    if worst is not None:
        lines.append(
            f"Worst-case min room temp: {worst:.1f}C "
            f"({report.get('worst_case_archetype', '?')} x {report.get('worst_case_zone', '?')})"
        )

    skynet = report.get("mean_skynet_cost_kwh")
    if skynet is not None:
        lines.append(f"Skynet Rule cost: {skynet:.1f} kWh mean (safety margin preserving comfort)")

    return "\n".join(lines)


def format_csv(report: Dict[str, Any]) -> str:
    """Format comparison rows as CSV."""
    rows = report.get("comparison_rows", [])
    if not rows:
        return "No comparison data available.\n"

    output = io.StringIO()
    fieldnames = ["archetype", "zone", "stock_kwh", "qsh_kwh", "savings_pct", "cop_delta", "min_room_temp",
                   "skynet_cost_kwh"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def write_json(report: Dict[str, Any], output_path: str) -> str:
    """Write fleet_summary.json to output directory.

    Returns:
        Path to the written file.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return output_path


# ── CLI ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="QSH Fleet Simulation Results Report")
    parser.add_argument("--db", required=True, help="Path to fleet.db")
    parser.add_argument("--output", default=None, help="Output directory for fleet_summary.json (default: same as db)")
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format (default: table)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    report = build_report(args.db)

    if args.format == "table":
        print(format_table(report))
    elif args.format == "csv":
        print(format_csv(report))
    elif args.format == "json":
        print(json.dumps(report, indent=2, default=str))

    # Always write JSON summary
    output_dir = args.output or os.path.dirname(args.db) or "."
    json_path = os.path.join(output_dir, "fleet_summary.json")
    write_json(report, json_path)
    logger.info("Wrote %s", json_path)


if __name__ == "__main__":
    main()
