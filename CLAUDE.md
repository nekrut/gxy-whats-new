# CLAUDE.md - Galactic Weekly Context

## Repository Overview
Galactic Weekly: automated weekly summaries of galaxyproject GitHub activity
- 150+ repos monitored via GitHub API (REST + GraphQL)
- AI summaries via Anthropic Claude API
- Publishes to Galaxy Hub as news posts

## Architecture

```
scripts/
├── generate_summary.py  # main orchestrator (validates secrets, skips duplicate output)
├── fetcher.py           # GitHub API w/ retry + rate-limit + early token validation
├── aggregator.py        # metrics computation
├── summarizer.py        # AI summary generation (Claude)
├── renderer.py          # Jinja2 markdown rendering
└── news_post.py         # Galaxy Hub news conversion
```

## Workflow (.github/workflows/galactic-summary.yml)

Two jobs:
1. `generate-summary` - fetches data, generates summary, commits to this repo
2. `create-hub-pr` - syncs fork with upstream, creates news post branch on galaxy-hub fork

### Fork-Based PR Workflow
- Uses nekrut/galaxy-hub fork (can't PR directly to upstream w/ fine-grained PAT)
- Fork sync tolerates failures gracefully (warns instead of aborting)
- GitHub API for branch/file creation (hub repo too large to clone)
- File upload retries up to 3 times with backoff (handles transient GitHub API errors)
- Branch naming: `news/galactic-weekly-w08`, `news/galactic-weekly-w09`, etc.
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
6. **Markdown link escaping**: PR/issue titles with `[]` or backticks break `[text](url)` syntax; renderer.py has `md_escape` Jinja2 filter using HTML entities
7. **Galaxy Hub frontmatter**: Uses `authors_structured` (list of `{name, github, orcid}` maps), NOT `authors` (string). Schema defined in `content/schema-news.yaml`
8. **Fail fast on bad secrets**: `validate_github_token()` in fetcher.py calls `/user` before 150+ repo fetches; generate_summary.py checks `ANTHROPIC_API_KEY` at startup when AI is enabled
9. **Pin all deps**: `requirements.txt` pins every transitive dependency for reproducible CI; `anthropic==0.84.0` is the current SDK version
10. **Idempotent workflow**: Fork sync tolerates failures; file upload retries 3x; duplicate summary output is skipped

## Common Tasks

### Run locally
```bash
python scripts/generate_summary.py
```

### Regenerate a specific week
```bash
gh workflow run galactic-summary.yml -f period=weekly -f custom_start=2026-02-16 -f custom_end=2026-02-22
```

## Output Files
- `summaries/weekly/YYYY-WXX.md` - weekly summary markdown
- `news-post/YYYY-MM-DD-galactic-weekly/index.md` - Galaxy Hub news post
