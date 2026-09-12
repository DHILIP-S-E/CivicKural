from wardwatch.geo import dedup_radius_m, haversine_m, in_ward_bbox, requires_merge_review
from wardwatch.models import GeoSource


def test_haversine_known_distance():
    d = haversine_m(9.9252, 78.1198, 9.9252, 78.1208)
    assert 100 < d < 120  # ~0.001 deg lng at this latitude ≈ 109 m


def test_radius_by_source():
    assert dedup_radius_m(GeoSource.WHATSAPP_SHARE) == 75
    assert dedup_radius_m(GeoSource.EXIF) == 75
    assert dedup_radius_m(GeoSource.GEOCODED) == 150
    assert dedup_radius_m(GeoSource.DESCRIBED) == 250


def test_only_described_needs_review():
    assert requires_merge_review(GeoSource.DESCRIBED)
    assert not requires_merge_review(GeoSource.WHATSAPP_SHARE)


def test_ward_bbox():
    assert in_ward_bbox("MDU-W14", 9.925, 78.12)
    assert not in_ward_bbox("MDU-W14", 10.5, 78.12)
    assert in_ward_bbox("UNKNOWN-WARD", 0, 0)  # unknown ward -> permissive
