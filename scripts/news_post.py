#!/usr/bin/env python3
"""Convert weekly summary to Galaxy Hub news post format."""

import os
import re
from datetime import datetime
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).parent.parent
SUMMARIES_DIR = REPO_ROOT / "summaries" / "weekly"
OUTPUT_DIR = REPO_ROOT / "news-post"

# Image URL for Galaxy Hub (absolute path to raw GitHub content)
HEADER_IMAGE_URL = "https://raw.githubusercontent.com/nekrut/gxy-whats-new/main/assets/header.jpg"


def find_latest_summary() -> Path:
    """Find most recent weekly summary file."""
    summaries = sorted(SUMMARIES_DIR.glob("*.md"), reverse=True)
    if not summaries:
        raise FileNotFoundError("No weekly summaries found")
    return summaries[0]


def parse_summary_info(filepath: Path) -> tuple[int, int, str, str]:
    """Parse week number, year, and dates from summary file.

    Returns: (week_num, year, start_date, end_date)
    """
    # Filename format: YYYY-WXX.md
    match = re.match(r"(\d{4})-W(\d{2})\.md", filepath.name)
    if not match:
        raise ValueError(f"Invalid summary filename: {filepath.name}")

    year = int(match.group(1))
    week_num = int(match.group(2))

    # Parse dates from content (second line: *YYYY-MM-DD to YYYY-MM-DD*)
    content = filepath.read_text()
    date_match = re.search(r"\*(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})\*", content)
    if not date_match:
        raise ValueError("Could not parse dates from summary")

    start_date = date_match.group(1)
    end_date = date_match.group(2)

    return week_num, year, start_date, end_date


def read_and_strip_header(filepath: Path) -> str:
    """Read summary content, strip title and date lines."""
    lines = filepath.read_text().splitlines()

    # Skip first 2 lines (title and date) and any blank lines after
    content_start = 2
    while content_start < len(lines) and not lines[content_start].strip():
        content_start += 1

    return "\n".join(lines[content_start:])


def fix_image_url(content: str) -> str:
    """Replace relative image paths with absolute GitHub URL."""
    # Pattern: ../../assets/header.jpg or similar
    content = re.sub(
        r"\.\./\.\.?/assets/header\.jpg",
        HEADER_IMAGE_URL,
        content
    )
    return content


def generate_frontmatter(week_num: int, year: int, end_date: str) -> dict:
    """Generate Galaxy Hub frontmatter."""
    return {
        "title": f"Galactic Weekly: Week {week_num}, {year}",
        "date": end_date,
        "tease": "Weekly summary of activity across 150+ galaxyproject repositories",
        "authors": "Galactic Bot",
        "tags": ["community", "development"],
        "subsites": ["all"],
    }


def main():
    # Find latest summary
    summary_file = find_latest_summary()
    print(f"Processing: {summary_file}")

    # Parse info
    week_num, year, start_date, end_date = parse_summary_info(summary_file)
    print(f"Week {week_num}, {year}: {start_date} to {end_date}")

    # Read content
    content = read_and_strip_header(summary_file)
    content = fix_image_url(content)

    # Generate frontmatter
    frontmatter = generate_frontmatter(week_num, year, end_date)

    # Create output directory: YYYY-MM-DD-galactic-weekly
    output_dir = OUTPUT_DIR / f"{end_date}-galactic-weekly"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write index.md
    output_file = output_dir / "index.md"
    with open(output_file, "w") as f:
        f.write("---\n")
        yaml.dump(frontmatter, f, default_flow_style=False, sort_keys=False)
        f.write("---\n\n")
        f.write(content)

    print(f"Created: {output_file}")

    # Output info for workflow
    print(f"::set-output name=week_num::{week_num}")
    print(f"::set-output name=year::{year}")
    print(f"::set-output name=end_date::{end_date}")


if __name__ == "__main__":
    main()
