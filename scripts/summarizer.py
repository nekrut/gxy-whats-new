"""AI-powered summaries using Anthropic API."""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_REPO_TOKENS = 200
DEFAULT_OVERALL_TOKENS = 300
DEFAULT_TIMEOUT = 60.0


def get_client(timeout: float = DEFAULT_TIMEOUT):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key, timeout=timeout)


def get_period_phrase(period: str) -> str:
    """Get appropriate time phrase for the period."""
    phrases = {
        "weekly": "this week's",
        "monthly": "this month's",
        "yearly": "this year's",
    }
    return phrases.get(period, "recent")


def summarize_repo_activity(
    repo_name: str,
    activity: dict,
    model: str = None,
    period: str = "weekly",
    config: dict = None
) -> str | None:
    """Generate human-readable summary for a repo's activity."""
    cfg = config or {}
    ai_cfg = cfg.get("ai", {})
    timeout = ai_cfg.get("request_timeout", DEFAULT_TIMEOUT)
    max_tokens = ai_cfg.get("repo_summary_tokens", DEFAULT_REPO_TOKENS)

    client = get_client(timeout)
    if not client:
        return None

    prs = activity.get("prs_merged", [])
    issues_new = activity.get("issues_new", [])
    issues_closed = activity.get("issues_closed", [])

    if not prs and not issues_new and not issues_closed:
        return None

    # Build context
    context_parts = []

    if prs:
        pr_list = "\n".join(f"- {pr['title']}" for pr in prs)
        context_parts.append(f"Merged PRs:\n{pr_list}")

    if issues_new:
        issue_list = "\n".join(f"- {i['title']}" for i in issues_new)
        context_parts.append(f"New issues:\n{issue_list}")

    if issues_closed:
        closed_list = "\n".join(f"- {i['title']}" for i in issues_closed)
        context_parts.append(f"Closed issues:\n{closed_list}")

    context = "\n\n".join(context_parts)
    period_phrase = get_period_phrase(period)

    prompt = f"""Summarize {period_phrase} activity for the Galaxy Project repository "{repo_name}" in 2-3 sentences.
Write for a general audience. Be factual and specific about what changed. Avoid superlatives, marketing language, and filler phrases like "significant improvements", "major enhancements", "exciting updates", etc. Just state what was done.

{context}

Summary:"""

    try:
        response = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except anthropic.APITimeoutError:
        log.error(f"Timeout summarizing {repo_name}")
        return None
    except Exception as e:
        log.error(f"Error summarizing {repo_name}: {e}")
        return None


def generate_repo_summaries(
    activity_data: list[dict],
    model: str = None,
    period: str = "weekly",
    config: dict = None
) -> dict[str, str]:
    """Generate summaries for all repos with activity."""
    cfg = config or {}
    ai_cfg = cfg.get("ai", {})
    api_cfg = cfg.get("api", {})
    max_workers = api_cfg.get("max_workers", 3)

    client = get_client()
    if not client:
        log.warning("No ANTHROPIC_API_KEY - skipping AI summaries")
        return {}

    # Filter to repos with activity
    active_repos = [
        a for a in activity_data
        if a["prs_merged"] or a["issues_new"] or a["issues_closed"]
    ]

    log.info(f"Generating AI summaries for {len(active_repos)} repos...")
    summaries = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                summarize_repo_activity, a["repo"], a, model, period, config
            ): a["repo"]
            for a in active_repos
        }

        for future in as_completed(futures):
            repo_name = futures[future]
            try:
                summary = future.result()
                if summary:
                    summaries[repo_name] = summary
                    log.info(f"Summarized: {repo_name}")
            except Exception as e:
                log.error(f"Error with {repo_name}: {e}")

    return summaries


def generate_overall_summary(
    metrics: dict,
    repo_summaries: dict[str, str],
    model: str = None,
    period: str = "weekly",
    config: dict = None
) -> str | None:
    """Generate an executive summary of all activity."""
    cfg = config or {}
    ai_cfg = cfg.get("ai", {})
    timeout = ai_cfg.get("request_timeout", DEFAULT_TIMEOUT)
    max_tokens = ai_cfg.get("overall_summary_tokens", DEFAULT_OVERALL_TOKENS)

    client = get_client(timeout)
    if not client:
        return None

    # Build context from top repos
    top_repos = metrics.get("top_repos", [])[:5]
    repo_context = []
    for repo in top_repos:
        name = repo["name"]
        summary = repo_summaries.get(name, f"{repo['prs_merged']} PRs merged, {repo['issues_closed']} issues closed")
        repo_context.append(f"**{name}**: {summary}")

    context = "\n".join(repo_context)
    period_phrase = get_period_phrase(period)

    prompt = f"""Write a 3-4 sentence summary of {period_phrase} Galaxy Project activity.
State the key themes and what was accomplished. Be factual and accessible to non-developers. Avoid superlatives, marketing language, and filler phrases like "significant", "major", "exciting", "enhanced", etc. Just state what happened.

Stats:
- {metrics['repos_active']} repositories had activity
- {metrics['prs_merged']} pull requests merged
- {metrics['issues_closed']} issues closed
- {metrics['contributors_unique']} contributors

Top repositories:
{context}

Summary:"""

    try:
        response = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except anthropic.APITimeoutError:
        log.error("Timeout generating overall summary")
        return None
    except Exception as e:
        log.error(f"Error generating overall summary: {e}")
        return None
