"""Tests for data aggregation."""

import sys
sys.path.insert(0, "scripts")

from aggregator import aggregate_metrics


class TestAggregateMetrics:
    """Test metrics aggregation."""

    def test_empty_data(self):
        """Empty input should return zero metrics."""
        result = aggregate_metrics([])
        assert result["repos_active"] == 0
        assert result["issues_new"] == 0
        assert result["issues_closed"] == 0
        assert result["prs_opened"] == 0
        assert result["prs_merged"] == 0
        assert result["contributors_unique"] == 0
        assert result["top_repos"] == []

    def test_single_repo_activity(self):
        """Single repo with activity."""
        data = [{
            "repo": "test-repo",
            "issues_new": [{"title": "New issue", "author": "user1"}],
            "issues_closed": [{"title": "Closed issue"}],
            "prs_opened": [{"title": "New PR", "author": "user2"}],
            "prs_merged": [{"title": "Merged PR", "author": "user1"}],
        }]

        result = aggregate_metrics(data)
        assert result["repos_active"] == 1
        assert result["issues_new"] == 1
        assert result["issues_closed"] == 1
        assert result["prs_opened"] == 1
        assert result["prs_merged"] == 1
        assert result["contributors_unique"] == 2

    def test_inactive_repo_not_counted(self):
        """Repo with no activity should not count as active."""
        data = [{
            "repo": "inactive-repo",
            "issues_new": [],
            "issues_closed": [],
            "prs_opened": [],
            "prs_merged": [],
        }]

        result = aggregate_metrics(data)
        assert result["repos_active"] == 0

    def test_contributor_deduplication(self):
        """Same contributor across PRs/issues should only count once."""
        data = [{
            "repo": "test-repo",
            "issues_new": [
                {"title": "Issue 1", "author": "user1"},
                {"title": "Issue 2", "author": "user1"},
            ],
            "issues_closed": [],
            "prs_opened": [{"title": "PR 1", "author": "user1"}],
            "prs_merged": [{"title": "PR 2", "author": "user1"}],
        }]

        result = aggregate_metrics(data)
        assert result["contributors_unique"] == 1

    def test_top_repos_ranking(self):
        """Repos should be ranked by activity score."""
        data = [
            {
                "repo": "low-activity",
                "issues_new": [{"author": "u1"}],
                "issues_closed": [],
                "prs_opened": [],
                "prs_merged": [],
            },
            {
                "repo": "high-activity",
                "issues_new": [],
                "issues_closed": [],
                "prs_opened": [],
                "prs_merged": [{"author": "u1"}, {"author": "u2"}, {"author": "u3"}],
            },
        ]

        result = aggregate_metrics(data)
        assert result["top_repos"][0]["name"] == "high-activity"
        assert result["top_repos"][1]["name"] == "low-activity"

    def test_top_repos_limited_to_10(self):
        """Top repos should be limited to 10."""
        data = [{
            "repo": f"repo-{i}",
            "issues_new": [{"author": "u1"}],
            "issues_closed": [],
            "prs_opened": [],
            "prs_merged": [],
        } for i in range(15)]

        result = aggregate_metrics(data)
        assert len(result["top_repos"]) == 10

    def test_grouped_items_sorted_alphabetically(self):
        """Grouped items should be sorted by repo name."""
        data = [
            {
                "repo": "zebra",
                "issues_new": [],
                "issues_closed": [],
                "prs_opened": [],
                "prs_merged": [{"title": "PR", "author": "u1"}],
            },
            {
                "repo": "alpha",
                "issues_new": [],
                "issues_closed": [],
                "prs_opened": [],
                "prs_merged": [{"title": "PR", "author": "u1"}],
            },
        ]

        result = aggregate_metrics(data)
        keys = list(result["merged_prs_by_repo"].keys())
        assert keys == ["alpha", "zebra"]

    def test_activity_score_calculation(self):
        """Activity score: merged*3 + opened*2 + closed + new."""
        data = [{
            "repo": "test",
            "issues_new": [{"author": "u"}],           # +1
            "issues_closed": [{}],                     # +1
            "prs_opened": [{"author": "u"}],           # +2
            "prs_merged": [{"author": "u"}],           # +3
        }]

        result = aggregate_metrics(data)
        assert result["top_repos"][0]["activity_score"] == 7
