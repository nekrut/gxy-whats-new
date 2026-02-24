# CLAUDE.md - Galactic Weekly Context

## Repository Overview
Galactic Weekly: automated weekly summaries of galaxyproject GitHub activity
- 150+ repos monitored via GitHub API (REST + GraphQL)
- AI summaries via Anthropic Claude API
- Publishes to Galaxy Hub as news posts

## Architecture

```
scripts/
├── generate_summary.py  # main orchestrator
├── fetcher.py           # GitHub API w/ retry + rate-limit handling
├── aggregator.py        # metrics computation
├── summarizer.py        # AI summary generation (Claude)
├── renderer.py          # Jinja2 markdown rendering
└── news_post.py         # Galaxy Hub news conversion
```

## Workflow (.github/workflows/weekly-summary.yml)

Two jobs:
1. `generate-summary` - fetches data, generates summary, commits to this repo
2. `create-hub-pr` - creates PR on galaxy-hub via fork

### Fork-Based PR Workflow
- Uses nekrut/galaxy-hub fork (can't PR directly to upstream w/ fine-grained PAT)
- GitHub API for branch/file creation (hub repo too large to clone)
- Email notification sent for manual PR creation on upstream

### Required Secrets
- `GITHUB_TOKEN` - default, for this repo
- `ANTHROPIC_API_KEY` - Claude API
- `GH_PAT` - classic PAT for fork operations
- `SMTP_USERNAME` / `SMTP_PASSWORD` - email notifications

## Git Push

- Always use HTTPS for pushing (remote is set to `https://github.com/nekrut/gxy-whats-new.git`)
- **Workflow files**: Pushing changes to `.github/workflows/` requires a PAT with `workflow` scope. If the push is rejected, the user must push from their local machine.

## Key Learnings

1. **Fine-grained PAT limitations**: Can't create PRs on repos you don't own; use classic PAT or fork workflow
2. **GitHub API vs clone**: For large repos, use API directly for file operations
3. **`GITHUB_OUTPUT`**: Replaces deprecated `set-output` command
4. **Rate limiting**: Essential handling for 150+ repo fetches; fetcher.py has exponential backoff
5. **Workflow push scope**: GitHub PATs need explicit `workflow` scope to modify `.github/workflows/` files

## Common Tasks

### Run locally
```bash
python scripts/generate_summary.py
```

### Test individual components
```bash
python -c "from scripts.fetcher import GitHubFetcher; ..."
```

## Output Files
- `summaries/YYYY-MM-DD.md` - weekly summary markdown
- `summaries/YYYY-MM-DD.json` - raw data cache
