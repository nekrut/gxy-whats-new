"""GitHub API interactions for fetching org repos and activity."""

import logging
import os
import time
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"

# Defaults (can be overridden via config)
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RATE_LIMIT_DELAY = 0.1


def get_headers():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable required")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def handle_rate_limit(response, max_retries=DEFAULT_MAX_RETRIES):
    """Check rate limit headers and wait if necessary. Returns True if should retry."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset_time = response.headers.get("X-RateLimit-Reset")

    if remaining is not None and int(remaining) == 0:
        if reset_time:
            wait_seconds = int(reset_time) - int(time.time()) + 1
            if wait_seconds > 0 and wait_seconds < 300:  # Max 5 min wait
                log.warning(f"Rate limit hit, waiting {wait_seconds}s")
                time.sleep(wait_seconds)
                return True
        log.error("Rate limit exceeded, no reset time available")
    return False


def request_with_retry(method, url, max_retries=DEFAULT_MAX_RETRIES, timeout=DEFAULT_TIMEOUT, **kwargs):
    """Make HTTP request with exponential backoff retry."""
    last_error = None
    for attempt in range(max_retries):
        try:
            if method == "get":
                resp = requests.get(url, timeout=timeout, **kwargs)
            else:
                resp = requests.post(url, timeout=timeout, **kwargs)

            # Handle rate limiting
            if resp.status_code == 403 and handle_rate_limit(resp, max_retries):
                continue

            return resp
        except requests.exceptions.Timeout as e:
            last_error = e
            log.warning(f"Request timeout (attempt {attempt + 1}/{max_retries}): {url}")
        except requests.exceptions.RequestException as e:
            last_error = e
            log.warning(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")

        # Exponential backoff: 1s, 2s, 4s
        if attempt < max_retries - 1:
            delay = 2 ** attempt
            log.debug(f"Retrying in {delay}s...")
            time.sleep(delay)

    raise last_error or requests.exceptions.RequestException(f"Failed after {max_retries} retries")


def fetch_org_repos(org: str, config: dict = None) -> list[dict]:
    """Fetch all repos in org using GraphQL pagination."""
    headers = get_headers()
    repos = []
    cursor = None

    cfg = config or {}
    api_cfg = cfg.get("api", {})
    timeout = api_cfg.get("request_timeout", DEFAULT_TIMEOUT)
    max_retries = api_cfg.get("max_retries", DEFAULT_MAX_RETRIES)
    rate_delay = api_cfg.get("rate_limit_delay", DEFAULT_RATE_LIMIT_DELAY)

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
        resp = request_with_retry(
            "post",
            GITHUB_GRAPHQL,
            max_retries=max_retries,
            timeout=timeout,
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
        time.sleep(rate_delay)

    return repos


def fetch_repo_issues(org: str, repo: str, start: date, end: date, config: dict = None) -> dict:
    """Fetch issues created/closed in date range."""
    headers = get_headers()
    start_iso = start.isoformat() + "T00:00:00Z"

    cfg = config or {}
    api_cfg = cfg.get("api", {})
    timeout = api_cfg.get("request_timeout", DEFAULT_TIMEOUT)
    max_retries = api_cfg.get("max_retries", DEFAULT_MAX_RETRIES)
    rate_delay = api_cfg.get("rate_limit_delay", DEFAULT_RATE_LIMIT_DELAY)

    new_issues = []
    closed_issues = []

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
        resp = request_with_retry(
            "get", url, max_retries=max_retries, timeout=timeout,
            headers=headers, params=params
        )
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

            # Skip null users instead of adding "unknown"
            author = item["user"]["login"] if item.get("user") else None

            if start <= created <= end:
                if author:  # Only add if we have a valid author
                    new_issues.append({
                        "title": item["title"],
                        "url": item["html_url"],
                        "author": author,
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
        time.sleep(rate_delay)

        if len(items) < 100:
            break

    return {"new": new_issues, "closed": closed_issues}


def fetch_repo_prs(org: str, repo: str, start: date, end: date, config: dict = None) -> dict:
    """Fetch PRs opened/merged in date range."""
    headers = get_headers()

    cfg = config or {}
    api_cfg = cfg.get("api", {})
    timeout = api_cfg.get("request_timeout", DEFAULT_TIMEOUT)
    max_retries = api_cfg.get("max_retries", DEFAULT_MAX_RETRIES)
    rate_delay = api_cfg.get("rate_limit_delay", DEFAULT_RATE_LIMIT_DELAY)

    opened_prs = []
    merged_prs = []

    url = f"{GITHUB_API}/repos/{org}/{repo}/pulls"
    params = {
        "state": "all",
        "per_page": 100,
        "sort": "created",
        "direction": "desc",
    }

    page = 1
    while True:
        params["page"] = page
        resp = request_with_retry(
            "get", url, max_retries=max_retries, timeout=timeout,
            headers=headers, params=params
        )
        if resp.status_code == 404:
            return {"opened": [], "merged": []}
        resp.raise_for_status()
        items = resp.json()

        if not items:
            break

        for item in items:
            created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).date()
            merged_at = item.get("merged_at")

            # Stop if we've gone past our date range (sorted by created desc)
            if created < start:
                return {"opened": opened_prs, "merged": merged_prs}

            # Skip null users instead of adding "unknown"
            author = item["user"]["login"] if item.get("user") else None

            if start <= created <= end and author:
                opened_prs.append({
                    "title": item["title"],
                    "url": item["html_url"],
                    "author": author,
                    "created_at": item["created_at"],
                })

            if merged_at and author:
                merged_date = datetime.fromisoformat(merged_at.replace("Z", "+00:00")).date()
                if start <= merged_date <= end:
                    merged_prs.append({
                        "title": item["title"],
                        "url": item["html_url"],
                        "author": author,
                        "merged_at": merged_at,
                    })

        page += 1
        time.sleep(rate_delay)

        if len(items) < 100:
            break

    return {"opened": opened_prs, "merged": merged_prs}


def fetch_repo_activity(org: str, repo: str, start: date, end: date, config: dict = None) -> dict:
    """Fetch all activity for a repo in date range."""
    issues = fetch_repo_issues(org, repo, start, end, config)
    prs = fetch_repo_prs(org, repo, start, end, config)

    return {
        "repo": repo,
        "issues_new": issues["new"],
        "issues_closed": issues["closed"],
        "prs_opened": prs["opened"],
        "prs_merged": prs["merged"],
    }


def fetch_all_repos_activity(
    org: str, repos: list[dict], start: date, end: date, config: dict = None
) -> list[dict]:
    """Fetch activity for all repos in parallel."""
    cfg = config or {}
    api_cfg = cfg.get("api", {})
    max_workers = api_cfg.get("max_workers", 3)

    results = []
    failed_repos = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_repo_activity, org, r["name"], start, end, config): r["name"]
            for r in repos
        }

        for future in as_completed(futures):
            repo_name = futures[future]
            try:
                result = future.result()
                results.append(result)
                log.info(f"Fetched: {repo_name}")
            except Exception as e:
                log.error(f"Error fetching {repo_name}: {e}")
                failed_repos.append(repo_name)

    if failed_repos:
        log.warning(f"Failed to fetch {len(failed_repos)} repos: {', '.join(failed_repos)}")

    return results
