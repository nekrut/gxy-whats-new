"""Tests for GitHub API fetcher."""

import sys
from datetime import date
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

sys.path.insert(0, "scripts")

from fetcher import (
    handle_rate_limit,
    request_with_retry,
    fetch_repo_issues,
    fetch_repo_prs,
    fetch_all_repos_activity,
)


class TestRateLimitHandling:
    """Test rate limit detection and handling."""

    def test_rate_limit_not_hit(self):
        """When remaining > 0, should return False."""
        resp = Mock()
        resp.headers = {"X-RateLimit-Remaining": "100", "X-RateLimit-Reset": "1234567890"}
        assert handle_rate_limit(resp) is False

    def test_rate_limit_hit_waits(self):
        """When remaining = 0, should wait and return True."""
        import time
        resp = Mock()
        reset_time = int(time.time()) + 2
        resp.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_time)}

        with patch("fetcher.time.sleep") as mock_sleep:
            result = handle_rate_limit(resp)
            assert result is True
            mock_sleep.assert_called_once()

    def test_rate_limit_no_headers(self):
        """When no rate limit headers, should return False."""
        resp = Mock()
        resp.headers = {}
        assert handle_rate_limit(resp) is False


class TestRequestWithRetry:
    """Test retry logic with exponential backoff."""

    @patch("fetcher.requests.get")
    def test_success_first_try(self, mock_get):
        """Successful request on first try."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        resp = request_with_retry("get", "http://test.com", max_retries=3, timeout=10)
        assert resp.status_code == 200
        assert mock_get.call_count == 1

    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.get")
    def test_retry_on_timeout(self, mock_get, mock_sleep):
        """Should retry on timeout with exponential backoff."""
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            Mock(status_code=200),
        ]

        resp = request_with_retry("get", "http://test.com", max_retries=3, timeout=10)
        assert resp.status_code == 200
        assert mock_get.call_count == 3
        # Backoff delays: 1s, 2s
        assert mock_sleep.call_count == 2

    @patch("fetcher.time.sleep")
    @patch("fetcher.requests.get")
    def test_max_retries_exceeded(self, mock_get, mock_sleep):
        """Should raise after max retries."""
        mock_get.side_effect = requests.exceptions.Timeout()

        with pytest.raises(requests.exceptions.Timeout):
            request_with_retry("get", "http://test.com", max_retries=3, timeout=10)

        assert mock_get.call_count == 3


class TestFetchRepoIssues:
    """Test issue fetching with pagination."""

    @patch("fetcher.get_headers")
    @patch("fetcher.request_with_retry")
    def test_empty_repo_returns_empty(self, mock_request, mock_headers):
        """Empty repo should return empty lists."""
        mock_headers.return_value = {"Authorization": "Bearer test"}
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_request.return_value = mock_resp

        result = fetch_repo_issues("org", "repo", date(2025, 1, 1), date(2025, 1, 7))
        assert result == {"new": [], "closed": []}

    @patch("fetcher.get_headers")
    @patch("fetcher.request_with_retry")
    def test_404_returns_empty(self, mock_request, mock_headers):
        """404 should return empty lists (repo doesn't exist or no access)."""
        mock_headers.return_value = {"Authorization": "Bearer test"}
        mock_resp = Mock()
        mock_resp.status_code = 404
        mock_request.return_value = mock_resp

        result = fetch_repo_issues("org", "repo", date(2025, 1, 1), date(2025, 1, 7))
        assert result == {"new": [], "closed": []}

    @patch("fetcher.time.sleep")
    @patch("fetcher.get_headers")
    @patch("fetcher.request_with_retry")
    def test_filters_prs_from_issues(self, mock_request, mock_headers, mock_sleep):
        """PRs should be filtered out from issues endpoint."""
        mock_headers.return_value = {"Authorization": "Bearer test"}
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "title": "Real issue",
                "html_url": "http://github.com/issue/1",
                "user": {"login": "user1"},
                "created_at": "2025-01-05T10:00:00Z",
                "closed_at": None,
            },
            {
                "title": "This is a PR",
                "html_url": "http://github.com/pr/1",
                "user": {"login": "user2"},
                "created_at": "2025-01-05T10:00:00Z",
                "pull_request": {},  # This makes it a PR
            },
        ]
        mock_request.return_value = mock_resp

        result = fetch_repo_issues("org", "repo", date(2025, 1, 1), date(2025, 1, 7))
        assert len(result["new"]) == 1
        assert result["new"][0]["title"] == "Real issue"

    @patch("fetcher.time.sleep")
    @patch("fetcher.get_headers")
    @patch("fetcher.request_with_retry")
    def test_null_user_skipped(self, mock_request, mock_headers, mock_sleep):
        """Issues with null user should be skipped."""
        mock_headers.return_value = {"Authorization": "Bearer test"}
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "title": "Issue with null user",
                "html_url": "http://github.com/issue/1",
                "user": None,  # Deleted account
                "created_at": "2025-01-05T10:00:00Z",
                "closed_at": None,
            },
        ]
        mock_request.return_value = mock_resp

        result = fetch_repo_issues("org", "repo", date(2025, 1, 1), date(2025, 1, 7))
        assert len(result["new"]) == 0


class TestFetchAllReposActivity:
    """Test parallel fetching."""

    @patch("fetcher.fetch_repo_activity")
    def test_partial_failure_continues(self, mock_fetch):
        """Should continue and log warning on partial failures."""
        mock_fetch.side_effect = [
            {"repo": "repo1", "issues_new": [], "issues_closed": [], "prs_opened": [], "prs_merged": []},
            Exception("API Error"),
            {"repo": "repo3", "issues_new": [], "issues_closed": [], "prs_opened": [], "prs_merged": []},
        ]

        repos = [{"name": "repo1"}, {"name": "repo2"}, {"name": "repo3"}]
        config = {"api": {"max_workers": 1}}

        results = fetch_all_repos_activity("org", repos, date(2025, 1, 1), date(2025, 1, 7), config)

        # Should have 2 successful results
        assert len(results) == 2

    @patch("fetcher.fetch_repo_activity")
    def test_respects_max_workers(self, mock_fetch):
        """Should use max_workers from config."""
        mock_fetch.return_value = {
            "repo": "test", "issues_new": [], "issues_closed": [],
            "prs_opened": [], "prs_merged": []
        }

        repos = [{"name": f"repo{i}"} for i in range(10)]
        config = {"api": {"max_workers": 2}}

        with patch("fetcher.ThreadPoolExecutor") as mock_executor:
            mock_executor.return_value.__enter__ = Mock(return_value=MagicMock())
            mock_executor.return_value.__exit__ = Mock(return_value=False)

            fetch_all_repos_activity("org", repos, date(2025, 1, 1), date(2025, 1, 7), config)

            mock_executor.assert_called_once_with(max_workers=2)
