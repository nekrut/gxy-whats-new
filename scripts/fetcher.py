"""GitHub API interactions for fetching org repos and activity."""

import os
import time
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"


def get_headers():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable required")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_org_repos(org: str) -> list[dict]:
    """Fetch all repos in org using GraphQL pagination."""
    headers = get_headers()
    repos = []
    cursor = None

    query = """
    query($org: String!, $cursor: String) {
      organization(login: $org) {
        repositories(first: 100, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            name
            isArchived
            isEmpty
            updatedAt
          }
        }
      }
    }
    """

    while True:
        variables = {"org": org, "cursor": cursor}
        resp = requests.post(
            GITHUB_GRAPHQL,
            headers=headers,
            json={"query": query, "variables": variables},
        )
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            raise Exception(f"GraphQL error: {data['errors']}")

        repo_data = data["data"]["organization"]["repositories"]
        for node in repo_data["nodes"]:
            if not node["isArchived"] and not node["isEmpty"]:
                repos.append({
                    "name": node["name"],
                    "updated_at": node["updatedAt"],
                })

        if not repo_data["pageInfo"]["hasNextPage"]:
            break
        cursor = repo_data["pageInfo"]["endCursor"]
        time.sleep(0.1)

    return repos


def fetch_repo_issues(org: str, repo: str, start: date, end: date) -> dict:
    """Fetch issues created/closed in date range."""
    headers = get_headers()
    start_iso = start.isoformat() + "T00:00:00Z"
    end_iso = end.isoformat() + "T23:59:59Z"

    new_issues = []
    closed_issues = []

    # Fetch issues updated since start
    url = f"{GITHUB_API}/repos/{org}/{repo}/issues"
    params = {
        "since": start_iso,
        "state": "all",
        "per_page": 100,
        "sort": "updated",
        "direction": "desc",
    }

    page = 1
    while True:
        params["page"] = page
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 404:
            return {"new": [], "closed": []}
        resp.raise_for_status()
        items = resp.json()

        if not items:
            break

        for item in items:
            # Skip PRs (they appear in issues endpoint too)
            if "pull_request" in item:
                continue

            created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).date()
            closed_at = item.get("closed_at")

            if start <= created <= end:
                new_issues.append({
                    "title": item["title"],
                    "url": item["html_url"],
                    "author": item["user"]["login"] if item["user"] else "unknown",
                    "created_at": item["created_at"],
                })

            if closed_at:
                closed_date = datetime.fromisoformat(closed_at.replace("Z", "+00:00")).date()
                if start <= closed_date <= end:
                    closed_issues.append({
                        "title": item["title"],
                        "url": item["html_url"],
                        "closed_at": closed_at,
                    })

        page += 1
        time.sleep(0.1)

        if len(items) < 100:
            break

    return {"new": new_issues, "closed": closed_issues}


def fetch_repo_prs(org: str, repo: str, start: date, end: date) -> dict:
    """Fetch PRs opened/merged in date range."""
    headers = get_headers()
    start_iso = start.isoformat() + "T00:00:00Z"
    end_iso = end.isoformat() + "T23:59:59Z"

    opened_prs = []
    merged_prs = []

    url = f"{GITHUB_API}/repos/{org}/{repo}/pulls"
    params = {
        "state": "all",
        "per_page": 100,
        "sort": "updated",
        "direction": "desc",
    }

    page = 1
    while True:
        params["page"] = page
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 404:
            return {"opened": [], "merged": []}
        resp.raise_for_status()
        items = resp.json()

        if not items:
            break

        for item in items:
            created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).date()
            merged_at = item.get("merged_at")
            updated = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00")).date()

            # Stop if we've gone past our date range
            if updated < start:
                return {"opened": opened_prs, "merged": merged_prs}

            if start <= created <= end:
                opened_prs.append({
                    "title": item["title"],
                    "url": item["html_url"],
                    "author": item["user"]["login"] if item["user"] else "unknown",
                    "created_at": item["created_at"],
                })

            if merged_at:
                merged_date = datetime.fromisoformat(merged_at.replace("Z", "+00:00")).date()
                if start <= merged_date <= end:
                    merged_prs.append({
                        "title": item["title"],
                        "url": item["html_url"],
                        "author": item["user"]["login"] if item["user"] else "unknown",
                        "merged_at": merged_at,
                    })

        page += 1
        time.sleep(0.1)

        if len(items) < 100:
            break

    return {"opened": opened_prs, "merged": merged_prs}


def fetch_repo_activity(org: str, repo: str, start: date, end: date) -> dict:
    """Fetch all activity for a repo in date range."""
    issues = fetch_repo_issues(org, repo, start, end)
    prs = fetch_repo_prs(org, repo, start, end)

    return {
        "repo": repo,
        "issues_new": issues["new"],
        "issues_closed": issues["closed"],
        "prs_opened": prs["opened"],
        "prs_merged": prs["merged"],
    }


def fetch_all_repos_activity(
    org: str, repos: list[dict], start: date, end: date, max_workers: int = 5
) -> list[dict]:
    """Fetch activity for all repos in parallel."""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_repo_activity, org, r["name"], start, end): r["name"]
            for r in repos
        }

        for future in as_completed(futures):
            repo_name = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"  Fetched: {repo_name}")
            except Exception as e:
                print(f"  Error fetching {repo_name}: {e}")

    return results
