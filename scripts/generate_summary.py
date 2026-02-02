#!/usr/bin/env python3
"""Main entry point for generating Galaxy project activity summaries."""

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from fetcher import fetch_org_repos, fetch_all_repos_activity
from aggregator import aggregate_metrics
from renderer import render_markdown
from summarizer import generate_repo_summaries, generate_overall_summary

# Resolve paths relative to repo root
REPO_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config.yml"
DEFAULT_TEMPLATE = REPO_ROOT / "templates" / "summary.md.j2"

log = logging.getLogger(__name__)

REQUIRED_CONFIG_KEYS = ["organization", "periods", "output_dir"]


def setup_logging(verbose: bool = False):
    """Configure logging for all modules."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def load_config(config_path: Path) -> dict:
    """Load and validate config file."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Validate required keys
    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in config]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")

    # Set defaults for optional sections
    config.setdefault("api", {})
    config.setdefault("ai", {})
    config.setdefault("excluded_repos", [])
    config.setdefault("highlight_repos", [])

    return config


def get_date_range(period: str, config: dict, custom_start: str = None, custom_end: str = None):
    """Calculate start and end dates for the period."""
    if custom_start and custom_end:
        return date.fromisoformat(custom_start), date.fromisoformat(custom_end)

    today = date.today()
    days = config["periods"].get(period, {}).get("days", 7)

    if period == "weekly":
        # Last Monday to Sunday
        # weekday(): Mon=0, Tue=1, ..., Sun=6
        # On Monday (0): want last Mon-Sun, so go back 7 days to last Monday
        # On Sunday (6): want last Mon-Sun, so go back 6 days to last Monday
        days_since_monday = today.weekday()
        if days_since_monday == 0:
            # Monday: last week was 7 days ago
            start = today - timedelta(days=7)
        else:
            # Tue-Sun: last Monday was days_since_monday days ago
            start = today - timedelta(days=days_since_monday)
        end = start + timedelta(days=6)  # Sunday of that week
    elif period == "monthly":
        # Previous month
        first_of_month = today.replace(day=1)
        end = first_of_month - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "yearly":
        # Previous year
        end = date(today.year - 1, 12, 31)
        start = date(today.year - 1, 1, 1)
    else:
        # Custom period: last N days
        end = today - timedelta(days=1)
        start = end - timedelta(days=days - 1)

    return start, end


def get_output_path(period: str, start: date, end: date, config: dict) -> Path:
    """Generate output file path."""
    output_dir = REPO_ROOT / config["output_dir"] / period

    if period == "weekly":
        # ISO week number
        filename = f"{start.year}-W{start.isocalendar()[1]:02d}.md"
    elif period == "monthly":
        filename = f"{start.year}-{start.month:02d}.md"
    elif period == "yearly":
        filename = f"{start.year}.md"
    else:
        filename = f"{start.isoformat()}_to_{end.isoformat()}.md"

    return output_dir / filename


def get_period_label(period: str, start: date, end: date) -> str:
    """Generate human-readable period label."""
    if period == "weekly":
        return f"Week {start.isocalendar()[1]}, {start.year}"
    elif period == "monthly":
        return start.strftime("%B %Y")
    elif period == "yearly":
        return str(start.year)
    else:
        return f"{start.isoformat()} to {end.isoformat()}"


def main():
    parser = argparse.ArgumentParser(description="Generate Galaxy project activity summary")
    parser.add_argument(
        "--period",
        choices=["weekly", "monthly", "yearly"],
        default="weekly",
        help="Summary period (default: weekly)",
    )
    parser.add_argument("--start", help="Custom start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="Custom end date (YYYY-MM-DD)")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Config file path",
    )
    parser.add_argument(
        "--template",
        default=str(DEFAULT_TEMPLATE),
        help="Template file path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output to stdout instead of file",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip AI-generated summaries",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Load config
    config_path = Path(args.config)
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as e:
        log.error(f"Config error: {e}")
        sys.exit(1)

    # Calculate date range
    start, end = get_date_range(args.period, config, args.start, args.end)
    log.info(f"Period: {args.period}")
    log.info(f"Date range: {start} to {end}")

    # Fetch repos
    org = config["organization"]
    log.info(f"Fetching repos for {org}...")
    repos = fetch_org_repos(org, config)
    log.info(f"Found {len(repos)} active repos")

    # Filter excluded repos
    excluded = set(config.get("excluded_repos", []))
    repos = [r for r in repos if r["name"] not in excluded]
    log.info(f"After exclusions: {len(repos)} repos")

    # Fetch activity
    log.info("Fetching activity...")
    activity_data = fetch_all_repos_activity(org, repos, start, end, config)

    # Aggregate metrics
    log.info("Aggregating metrics...")
    metrics = aggregate_metrics(activity_data)

    log.info(f"Summary: {metrics['repos_active']} active repos, "
             f"{metrics['prs_merged']} PRs merged, "
             f"{metrics['issues_closed']} issues closed, "
             f"{metrics['contributors_unique']} contributors")

    # Generate AI summaries
    repo_summaries = {}
    overall_summary = None
    if not args.no_ai:
        model = config.get("anthropic_model")
        repo_summaries = generate_repo_summaries(
            activity_data, model=model, period=args.period, config=config
        )
        if repo_summaries:
            overall_summary = generate_overall_summary(
                metrics, repo_summaries, model=model, period=args.period, config=config
            )

    metrics["repo_summaries"] = repo_summaries
    metrics["overall_summary"] = overall_summary

    # Render markdown
    template_path = Path(args.template)
    period_label = get_period_label(args.period, start, end)
    markdown = render_markdown(
        metrics,
        template_path,
        period_label,
        start.isoformat(),
        end.isoformat(),
    )

    if args.dry_run:
        print("\n" + "=" * 60)
        print(markdown)
    else:
        output_path = get_output_path(args.period, start, end, config)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown)
        log.info(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
