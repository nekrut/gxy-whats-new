# Galactic Weekly

<img width="1024" height="495" alt="image" src="https://github.com/user-attachments/assets/23c1fc24-56f2-4bc0-85f1-7135a1b256fd" />

Automated weekly summaries of GitHub activity across all 150+ repositories in the `galaxyproject` organization. Generates AI-powered human-readable summaries and automatically creates news posts for Galaxy Hub.

## Features

- Fetches issues, PRs, and contributor data from all galaxyproject repos
- Generates AI summaries using Claude (Anthropic API)
- Produces markdown reports with metrics and highlights
- Auto-creates Galaxy Hub news post branches
- Email notifications when posts are ready for PR
- Configurable rate limiting and retry logic
- Structured logging with verbose mode

## Repository Structure

```
gxy-whats-new/
├── scripts/
│   ├── generate_summary.py   # Main entry point
│   ├── fetcher.py            # GitHub API interactions
│   ├── aggregator.py         # Metrics computation
│   ├── summarizer.py         # AI summary generation
│   ├── renderer.py           # Jinja2 markdown rendering
│   └── news_post.py          # Galaxy Hub post converter
├── templates/
│   └── summary.md.j2         # Summary template
├── summaries/
│   └── weekly/               # Generated summaries
├── tests/
│   ├── test_aggregator.py    # Aggregator unit tests
│   ├── test_fetcher.py       # Fetcher unit tests
│   └── test_dates.py         # Date calculation tests
├── config.yml                # Configuration
└── requirements.txt          # Python dependencies
```

## Scripts

### `generate_summary.py`
Main orchestrator. Coordinates fetching, aggregation, summarization, and rendering.

**Functions:**
- `setup_logging()` - Configures logging for all modules
- `load_config()` - Loads and validates `config.yml`
- `get_date_range()` - Calculates period start/end dates
- `get_output_path()` - Determines output filename
- `get_period_label()` - Human-readable period name

### `fetcher.py`
GitHub API interactions using both REST and GraphQL with retry logic.

**Functions:**
- `get_headers()` - Returns auth headers from `GITHUB_TOKEN`
- `handle_rate_limit()` - Checks rate limit headers and waits if needed
- `request_with_retry()` - HTTP requests with exponential backoff (1s, 2s, 4s)
- `fetch_org_repos()` - Lists all non-archived repos via GraphQL
- `fetch_repo_issues()` - Gets issues created/closed in date range
- `fetch_repo_prs()` - Gets PRs opened/merged in date range
- `fetch_repo_activity()` - Combines issues and PRs for one repo
- `fetch_all_repos_activity()` - Parallel fetching with configurable workers

### `aggregator.py`
Processes raw data into summary metrics.

**Functions:**
- `aggregate_metrics()` - Computes totals, ranks repos by activity score, groups items by repo

**Activity score:** `merged_prs * 3 + opened_prs * 2 + closed_issues + new_issues`

### `summarizer.py`
AI-powered summaries using Anthropic Claude with timeout handling.

**Functions:**
- `get_client()` - Creates Anthropic client with configurable timeout
- `get_period_phrase()` - Returns "this week's", "this month's", etc.
- `summarize_repo_activity()` - 2-3 sentence summary per repo
- `generate_repo_summaries()` - Parallel summarization for all active repos
- `generate_overall_summary()` - Executive summary of period's activity

### `renderer.py`
Jinja2 template rendering.

**Functions:**
- `render_markdown()` - Renders metrics to markdown using `templates/summary.md.j2`

### `news_post.py`
Converts weekly summary to Galaxy Hub news post format.

**Functions:**
- `find_latest_summary()` - Finds most recent weekly summary
- `parse_summary_info()` - Extracts week number, year, dates from filename/content
- `read_and_strip_header()` - Removes title/date lines (already in frontmatter)
- `fix_image_url()` - Converts relative image paths to absolute GitHub URLs
- `generate_frontmatter()` - Creates Galaxy Hub YAML frontmatter

## Configuration

`config.yml`:

```yaml
organization: galaxyproject
anthropic_model: claude-sonnet-4-20250514
excluded_repos: []              # Repos to skip
highlight_repos:                # Priority repos for summaries
  - galaxy
  - training-material
  - tools-iuc
periods:
  weekly:
    days: 7
  monthly:
    days: 30
  yearly:
    days: 365
output_dir: summaries

# API settings
api:
  max_workers: 3              # Parallel fetch threads
  rate_limit_delay: 0.1       # Delay between API calls (seconds)
  request_timeout: 30         # HTTP timeout (seconds)
  max_retries: 3              # Retry attempts on failure

# AI summary settings
ai:
  repo_summary_tokens: 200    # Max tokens per repo summary
  overall_summary_tokens: 300 # Max tokens for overall summary
```

## Local Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GITHUB_TOKEN=your_token_here
export ANTHROPIC_API_KEY=your_key_here  # Optional

# Generate weekly summary
python scripts/generate_summary.py --period weekly

# Other options
python scripts/generate_summary.py --period monthly
python scripts/generate_summary.py --start 2026-01-01 --end 2026-01-31
python scripts/generate_summary.py --dry-run      # Print to stdout
python scripts/generate_summary.py --no-ai        # Skip AI summaries
python scripts/generate_summary.py --verbose      # Debug logging

# Run tests
pytest tests/
```

## GitHub Actions Workflow

### `galactic-summary.yml`

**Triggers:**
- **Scheduled:** Every Sunday at 9 AM UTC
- **Manual:** Via workflow_dispatch with custom parameters

### Jobs

#### 1. `generate-summary`

Generates the weekly summary markdown file.

**Steps:**
1. Checkout repository
2. Setup Python 3.11
3. Install dependencies from `requirements.txt`
4. Run `generate_summary.py` with period and optional date parameters
5. Commit and push to `summaries/` directory

**Environment:**
- `GITHUB_TOKEN` - For GitHub API access
- `ANTHROPIC_API_KEY` - For AI summaries

#### 2. `create-hub-pr`

Creates a news post branch on the Galaxy Hub fork (runs only for weekly summaries).

**Steps:**
1. Checkout and pull latest changes
2. Run `news_post.py` to convert summary to Galaxy Hub format
3. Create branch on fork (`nekrut/galaxy-hub`) from upstream SHA
4. Upload news post file via GitHub API
5. Send email notification with PR creation link

**API Operations:**
- Gets upstream (`galaxyproject/galaxy-hub`) default branch SHA
- Creates new branch on fork
- Uploads `content/news/YYYY-MM-DD-galactic-weekly/index.md`
- Handles existing files by providing blob SHA for updates

### Workflow Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `period` | choice | `weekly` | Summary period (weekly/monthly/yearly) |
| `custom_start` | string | - | Custom start date (YYYY-MM-DD) |
| `custom_end` | string | - | Custom end date (YYYY-MM-DD) |

## Required Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI summaries |
| `GH_PAT` | Yes | GitHub PAT with repo access |
| `SMTP_USERNAME` | Yes | Email address for notifications |
| `SMTP_PASSWORD` | Yes | Gmail app password |

### GH_PAT Permissions

Fine-grained PAT for `nekrut/galaxy-hub`:
- **Contents:** Read and write
- **Pull requests:** Read and write

## Output

### Summary Files

Stored in `summaries/{period}/`:
- `2026-W05.md` (weekly)
- `2026-01.md` (monthly)
- `2026.md` (yearly)

### Galaxy Hub News Post

Created at `content/news/YYYY-MM-DD-galactic-weekly/index.md` with frontmatter:

```yaml
title: "Galactic Weekly: Week X, YYYY"
date: "YYYY-MM-DD"
tease: "Weekly summary of activity across 150+ galaxyproject repositories"
authors: "Galactic Bot"
tags: [community, development]
subsites: [all]
```

## Email Notification

After successful run, an email is sent containing:
- Branch URL on the fork
- Direct link to create PR against `galaxyproject/galaxy-hub`

## Dependencies

```
requests>=2.31.0
pyyaml>=6.0
jinja2>=3.1.2
anthropic==0.40.0
pytest>=7.0.0
```
