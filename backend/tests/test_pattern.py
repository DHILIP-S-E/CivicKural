from datetime import datetime, timedelta, timezone

from wardwatch.agents import pattern
from wardwatch.models import Category

from .factories import make_complaint

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def _fake_summary(sp, ut):
    return "Recurring failure — recommend infrastructure review."


def test_below_threshold_no_flag():
    cs = [make_complaint(category=Category.WATER_LEAK, created_at=NOW) for _ in range(2)]
    assert pattern.find_flags("MDU-CORP", "MDU-W14", cs, NOW, _fake_summary) == []


def test_three_within_radius_and_window_flags():
    cs = [
        make_complaint(category=Category.WATER_LEAK, lat=9.9252, lng=78.1198, created_at=NOW),
        make_complaint(category=Category.WATER_LEAK, lat=9.9253, lng=78.1199, created_at=NOW - timedelta(days=20)),
        make_complaint(category=Category.WATER_LEAK, lat=9.9251, lng=78.1197, created_at=NOW - timedelta(days=60)),
    ]
    flags = pattern.find_flags("MDU-CORP", "MDU-W14", cs, NOW, _fake_summary)
    assert len(flags) == 1
    assert flags[0].incident_count == 3
    assert flags[0].category == Category.WATER_LEAK
    assert pattern.find_flags(
        "MDU-CORP", "MDU-W14", cs, NOW, _fake_summary, {flags[0].flag_id}
    ) == []


def test_outside_90_day_window_excluded():
    cs = [
        make_complaint(category=Category.WATER_LEAK, created_at=NOW),
        make_complaint(category=Category.WATER_LEAK, created_at=NOW - timedelta(days=20)),
        make_complaint(category=Category.WATER_LEAK, created_at=NOW - timedelta(days=200)),
    ]
    assert pattern.find_flags("MDU-CORP", "MDU-W14", cs, NOW, _fake_summary) == []


def test_far_apart_not_clustered():
    cs = [
        make_complaint(category=Category.POTHOLE, lat=9.9252, lng=78.1198, created_at=NOW),
        make_complaint(category=Category.POTHOLE, lat=9.9252, lng=78.1198, created_at=NOW),
        make_complaint(category=Category.POTHOLE, lat=9.9500, lng=78.1500, created_at=NOW),
    ]
    assert pattern.find_flags("MDU-CORP", "MDU-W14", cs, NOW, _fake_summary) == []
