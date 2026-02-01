"""Tests for date range calculations."""

from datetime import date, timedelta
from unittest.mock import patch
import sys
sys.path.insert(0, "scripts")

from generate_summary import get_date_range


def make_config():
    return {"periods": {"weekly": {"days": 7}, "monthly": {"days": 30}, "yearly": {"days": 365}}}


class TestWeeklyDateRange:
    """Test weekly date range calculation for different days of the week."""

    def test_monday_gets_previous_week(self):
        """On Monday, should get the previous Mon-Sun."""
        with patch("generate_summary.date") as mock_date:
            mock_date.today.return_value = date(2025, 1, 27)  # Monday
            mock_date.fromisoformat = date.fromisoformat
            start, end = get_date_range("weekly", make_config())
            assert start == date(2025, 1, 20)  # Previous Monday
            assert end == date(2025, 1, 26)    # Previous Sunday

    def test_tuesday_gets_current_week_start(self):
        """On Tuesday, should get Mon-Sun of current week (started yesterday)."""
        with patch("generate_summary.date") as mock_date:
            mock_date.today.return_value = date(2025, 1, 28)  # Tuesday
            mock_date.fromisoformat = date.fromisoformat
            start, end = get_date_range("weekly", make_config())
            assert start == date(2025, 1, 27)  # Monday (yesterday)
            assert end == date(2025, 2, 2)     # Sunday

    def test_sunday_gets_current_week(self):
        """On Sunday, should get Mon-Sun of current week (today is Sunday)."""
        with patch("generate_summary.date") as mock_date:
            mock_date.today.return_value = date(2025, 1, 26)  # Sunday
            mock_date.fromisoformat = date.fromisoformat
            start, end = get_date_range("weekly", make_config())
            assert start == date(2025, 1, 20)  # Monday of this week
            assert end == date(2025, 1, 26)    # Today (Sunday)

    def test_wednesday_gets_current_week_start(self):
        """On Wednesday, should get Mon of current week."""
        with patch("generate_summary.date") as mock_date:
            mock_date.today.return_value = date(2025, 1, 29)  # Wednesday
            mock_date.fromisoformat = date.fromisoformat
            start, end = get_date_range("weekly", make_config())
            assert start == date(2025, 1, 27)  # Monday
            assert end == date(2025, 2, 2)     # Sunday

    def test_year_boundary(self):
        """Test date range across year boundary."""
        with patch("generate_summary.date") as mock_date:
            mock_date.today.return_value = date(2025, 1, 1)  # Wednesday
            mock_date.fromisoformat = date.fromisoformat
            start, end = get_date_range("weekly", make_config())
            assert start == date(2024, 12, 30)  # Monday (2024)
            assert end == date(2025, 1, 5)      # Sunday (2025)


class TestCustomDateRange:
    """Test custom date range."""

    def test_custom_dates(self):
        """Custom start/end should be used directly."""
        start, end = get_date_range(
            "weekly", make_config(),
            custom_start="2025-01-01", custom_end="2025-01-15"
        )
        assert start == date(2025, 1, 1)
        assert end == date(2025, 1, 15)
