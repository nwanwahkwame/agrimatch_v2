"""
Data quality report for AgriMatch M1.

Queries the live database and prints five sections:
  1. Coverage summary  — row counts by source and by crop
  2. Market coverage   — per-market row count and date range
  3. Quarantine        — top-10 rejection reasons
  4. Data gaps         — market+crop pairs with >3 consecutive months missing
  5. Recent runs       — last 10 ingestion_log entries

Output is printed to the terminal and saved to reports/latest_quality_report.txt.
"""

import sys
import textwrap
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text

from db.connection import get_session
from db.models import CleanPrice, IngestionLog, PriceQuarantine

# ── Paths ─────────────────────────────────────────────────────────────────────

REPORTS_DIR = Path(__file__).parent
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = REPORTS_DIR / "latest_quality_report.txt"


# ── Formatting helpers ────────────────────────────────────────────────────────

def _hr(char: str = "=", width: int = 72) -> str:
    return char * width


def _section(title: str) -> str:
    bar = _hr()
    return f"\n{bar}\n  {title}\n{bar}"


def _table(headers: list[str], rows: list[list], col_align: list[str] | None = None) -> str:
    """Render a plain-text table.

    col_align: list of 'l' (left) or 'r' (right) per column; defaults to all left.
    """
    if not rows:
        return "  (no data)\n"

    col_align = col_align or ["l"] * len(headers)
    all_rows = [headers] + [[str(v) for v in r] for r in rows]
    widths = [max(len(str(row[i])) for row in all_rows) for i in range(len(headers))]

    sep = "  +" + "+".join("-" * (w + 2) for w in widths) + "+"

    def _fmt_row(values):
        cells = []
        for i, v in enumerate(values):
            w = widths[i]
            cells.append(f" {v:>{w}} " if col_align[i] == "r" else f" {v:<{w}} ")
        return "  |" + "|".join(cells) + "|"

    lines = [sep, _fmt_row(headers), sep]
    for row in rows:
        lines.append(_fmt_row([str(v) for v in row]))
    lines.append(sep)
    return "\n".join(lines) + "\n"


def _no_data(label: str = "") -> str:
    suffix = f" ({label})" if label else ""
    return f"  No data found{suffix}.\n"


# ── Section builders ──────────────────────────────────────────────────────────

def _coverage_summary(session) -> str:
    lines = [_section("1. COVERAGE SUMMARY")]

    total = session.execute(select(func.count()).select_from(CleanPrice)).scalar() or 0
    lines.append(f"\n  Total rows in clean_prices: {total:,}\n")

    if total == 0:
        lines.append(_no_data("run a pipeline first"))
        return "\n".join(lines)

    # By source
    by_source = session.execute(
        select(CleanPrice.source, func.count().label("n"))
        .group_by(CleanPrice.source)
        .order_by(func.count().desc())
    ).all()
    lines.append("  By source:")
    lines.append(
        _table(
            ["Source", "Rows"],
            [[r.source or "-", f"{r.n:,}"] for r in by_source],
            col_align=["l", "r"],
        )
    )

    # By crop
    by_crop = session.execute(
        select(CleanPrice.crop, func.count().label("n"))
        .group_by(CleanPrice.crop)
        .order_by(func.count().desc())
    ).all()
    lines.append("  By crop:")
    lines.append(
        _table(
            ["Crop", "Rows"],
            [[r.crop or "-", f"{r.n:,}"] for r in by_crop],
            col_align=["l", "r"],
        )
    )

    return "\n".join(lines)


def _market_coverage(session) -> str:
    lines = [_section("2. MARKET COVERAGE")]

    rows = session.execute(
        select(
            CleanPrice.market,
            CleanPrice.source,
            func.count().label("n"),
            func.min(CleanPrice.price_date).label("first"),
            func.max(CleanPrice.price_date).label("last"),
        )
        .group_by(CleanPrice.market, CleanPrice.source)
        .order_by(func.count().desc())
    ).all()

    if not rows:
        lines.append(_no_data())
        return "\n".join(lines)

    table_rows = [
        [r.market or "-", r.source or "-", f"{r.n:,}", str(r.first), str(r.last)]
        for r in rows
    ]
    lines.append(
        _table(
            ["Market", "Source", "Rows", "Earliest", "Latest"],
            table_rows,
            col_align=["l", "l", "r", "l", "l"],
        )
    )
    return "\n".join(lines)


def _quarantine_summary(session) -> str:
    lines = [_section("3. QUARANTINE SUMMARY")]

    total = session.execute(
        select(func.count()).select_from(PriceQuarantine)
    ).scalar() or 0
    lines.append(f"\n  Total quarantined rows: {total:,}\n")

    if total == 0:
        lines.append("  No quarantined rows - all ingested data passed validation.\n")
        return "\n".join(lines)

    top10 = session.execute(
        select(
            PriceQuarantine.rejection_reason,
            func.count().label("n"),
        )
        .group_by(PriceQuarantine.rejection_reason)
        .order_by(func.count().desc())
        .limit(10)
    ).all()

    lines.append("  Top 10 rejection reasons:")
    lines.append(
        _table(
            ["Reason", "Count"],
            [[r.rejection_reason or "-", f"{r.n:,}"] for r in top10],
            col_align=["l", "r"],
        )
    )
    return "\n".join(lines)


def _data_gaps(session) -> str:
    lines = [_section("4. DATA GAPS  (>3 consecutive months missing)")]

    # Fetch all (market, crop, price_date) in one query; the dataset is small
    # enough that pulling it into Python is cheaper than writing a complex
    # generate_series gap-detection query.
    all_rows = session.execute(
        select(CleanPrice.market, CleanPrice.crop, CleanPrice.price_date)
        .where(CleanPrice.price_date.isnot(None))
    ).all()

    if not all_rows:
        lines.append(_no_data())
        return "\n".join(lines)

    # Group year-month tuples by (market, crop)
    seen: dict[tuple, set] = defaultdict(set)
    for r in all_rows:
        seen[(r.market, r.crop)].add((r.price_date.year, r.price_date.month))

    gaps = []
    for (market, crop), months in seen.items():
        sorted_months = sorted(months)
        for i in range(len(sorted_months) - 1):
            y1, m1 = sorted_months[i]
            y2, m2 = sorted_months[i + 1]
            gap_months = (y2 - y1) * 12 + (m2 - m1) - 1  # missing months between
            if gap_months > 3:
                gap_from = f"{sorted_months[i][0]}-{sorted_months[i][1]:02d}"
                gap_to   = f"{sorted_months[i + 1][0]}-{sorted_months[i + 1][1]:02d}"
                gaps.append([market, crop, gap_from, gap_to, str(gap_months)])

    if not gaps:
        lines.append("\n  No gaps greater than 3 consecutive months found.\n")
        return "\n".join(lines)

    gaps.sort(key=lambda x: (x[0], x[1]))   # sort by market then crop
    lines.append(
        _table(
            ["Market", "Crop", "Gap from", "Gap to", "Missing months"],
            gaps,
            col_align=["l", "l", "l", "l", "r"],
        )
    )
    return "\n".join(lines)


def _recent_runs(session) -> str:
    lines = [_section("5. RECENT RUNS  (last 10 ingestion_log entries)")]

    runs = session.execute(
        select(
            IngestionLog.id,
            IngestionLog.source,
            IngestionLog.run_at,
            IngestionLog.rows_fetched,
            IngestionLog.rows_clean,
            IngestionLog.rows_quarantined,
            IngestionLog.status,
            IngestionLog.error_detail,
        )
        .order_by(IngestionLog.run_at.desc())
        .limit(10)
    ).all()

    if not runs:
        lines.append(_no_data("no pipeline runs recorded yet"))
        return "\n".join(lines)

    table_rows = []
    for r in runs:
        run_at_str = r.run_at.strftime("%Y-%m-%d %H:%M") if r.run_at else "-"
        error = (r.error_detail or "")[:40]   # truncate long errors
        if r.error_detail and len(r.error_detail) > 40:
            error += "..."
        table_rows.append([
            str(r.id),
            r.source or "-",
            run_at_str,
            f"{r.rows_fetched or 0:,}",
            f"{r.rows_clean or 0:,}",
            f"{r.rows_quarantined or 0:,}",
            r.status or "-",
            error,
        ])

    lines.append(
        _table(
            ["ID", "Source", "Run at", "Fetched", "Clean", "Quarantined", "Status", "Error"],
            table_rows,
            col_align=["r", "l", "l", "r", "r", "r", "l", "l"],
        )
    )
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_report() -> str:
    """Build the full report string by querying the live database."""
    with get_session() as session:
        parts = [
            _coverage_summary(session),
            _market_coverage(session),
            _quarantine_summary(session),
            _data_gaps(session),
            _recent_runs(session),
        ]

    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = textwrap.dedent(f"""\
        {_hr()}
        AgriMatch - Data Quality Report
        Generated: {generated_at}
        {_hr()}""")

    footer = f"\n{_hr()}\n  End of report\n{_hr()}\n"

    return header + "\n".join(parts) + footer


def main() -> None:
    try:
        report = generate_report()
    except Exception as exc:
        print(f"ERROR: could not generate report — {exc}", file=sys.stderr)
        raise

    # Print to terminal
    print(report)

    # Save to file
    OUTPUT_FILE.write_text(report, encoding="utf-8")
    print(f"Report saved to: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
