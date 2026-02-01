# Galactic Weekly

Automated summaries of GitHub activity across all repositories in the `galaxyproject` organization. Includes AI-generated human-readable summaries for each active repository.

## Usage

### Local

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=your_token_here
export ANTHROPIC_API_KEY=your_key_here  # Optional, for AI summaries
python scripts/generate_summary.py --period weekly
```

### Options

- `--period`: `weekly`, `monthly`, or `yearly`
- `--start`: Custom start date (YYYY-MM-DD)
- `--end`: Custom end date (YYYY-MM-DD)
- `--dry-run`: Print to stdout instead of file
- `--no-ai`: Skip AI-generated summaries

### GitHub Actions

Runs automatically every Monday at 9 AM UTC. Can also be triggered manually with custom parameters.

## Configuration

Edit `config.yml` to:
- Exclude specific repositories
- Mark highlight repositories
- Adjust period definitions

## Output

Summaries are stored in `summaries/{period}/` with filenames like:
- `2026-W05.md` (weekly)
- `2026-01.md` (monthly)
- `2026.md` (yearly)

## Secrets

Add these secrets to your GitHub repository:

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | For AI-generated summaries |
| `GH_PAT` | No | Personal access token if default token lacks permissions |

The default `GITHUB_TOKEN` should work for reading public repos. Create a PAT with `read:org` scope if issues arise.
