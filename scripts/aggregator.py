"""Data processing and metrics computation."""

from collections import defaultdict


def aggregate_metrics(activity_data: list[dict]) -> dict:
    """Aggregate activity data into summary metrics."""
    repos_active = 0
    total_issues_new = 0
    total_issues_closed = 0
    total_prs_opened = 0
    total_prs_merged = 0
    contributors = set()

    # Per-repo stats for ranking
    repo_stats = []

    # Group items by repo
    merged_prs_by_repo = defaultdict(list)
    new_issues_by_repo = defaultdict(list)
    closed_issues_by_repo = defaultdict(list)

    for repo_data in activity_data:
        repo_name = repo_data["repo"]

        issues_new = repo_data["issues_new"]
        issues_closed = repo_data["issues_closed"]
        prs_opened = repo_data["prs_opened"]
        prs_merged = repo_data["prs_merged"]

        # Count totals
        n_new = len(issues_new)
        n_closed = len(issues_closed)
        n_opened = len(prs_opened)
        n_merged = len(prs_merged)

        total_issues_new += n_new
        total_issues_closed += n_closed
        total_prs_opened += n_opened
        total_prs_merged += n_merged

        # Track activity
        if n_new or n_closed or n_opened or n_merged:
            repos_active += 1

        # Collect contributors
        for pr in prs_opened + prs_merged:
            contributors.add(pr["author"])
        for issue in issues_new:
            contributors.add(issue["author"])

        # Store per-repo stats
        repo_stats.append({
            "name": repo_name,
            "prs_merged": n_merged,
            "prs_opened": n_opened,
            "issues_new": n_new,
            "issues_closed": n_closed,
            "activity_score": n_merged * 3 + n_opened * 2 + n_closed + n_new,
        })

        # Group items
        if prs_merged:
            merged_prs_by_repo[repo_name] = prs_merged
        if issues_new:
            new_issues_by_repo[repo_name] = issues_new
        if issues_closed:
            closed_issues_by_repo[repo_name] = issues_closed

    # Sort repos by activity
    repo_stats.sort(key=lambda x: x["activity_score"], reverse=True)
    top_repos = [r for r in repo_stats[:10] if r["activity_score"] > 0]

    # Sort grouped items by repo name
    merged_prs_by_repo = dict(sorted(merged_prs_by_repo.items()))
    new_issues_by_repo = dict(sorted(new_issues_by_repo.items()))
    closed_issues_by_repo = dict(sorted(closed_issues_by_repo.items()))

    return {
        "repos_active": repos_active,
        "issues_new": total_issues_new,
        "issues_closed": total_issues_closed,
        "prs_opened": total_prs_opened,
        "prs_merged": total_prs_merged,
        "contributors_unique": len(contributors),
        "top_repos": top_repos,
        "merged_prs_by_repo": merged_prs_by_repo,
        "new_issues_by_repo": new_issues_by_repo,
        "closed_issues_by_repo": closed_issues_by_repo,
    }
