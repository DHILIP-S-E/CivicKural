from wardwatch.agents.dedup import find_duplicate
from wardwatch.models import Geo, GeoSource

from .factories import make_complaint


def test_match_within_radius():
    existing = make_complaint(lat=9.9252, lng=78.1198)
    new_geo = Geo(lat=9.92525, lng=78.11985, source=GeoSource.WHATSAPP_SHARE)  # ~7 m
    decision = find_duplicate(new_geo, [existing])
    assert decision.is_duplicate
    assert decision.match is existing
    assert not decision.needs_review


def test_no_match_outside_radius():
    existing = make_complaint(lat=9.9252, lng=78.1198)
    new_geo = Geo(lat=9.9300, lng=78.1198, source=GeoSource.WHATSAPP_SHARE)  # ~530 m
    assert not find_duplicate(new_geo, [existing]).is_duplicate


def test_described_source_flags_review():
    existing = make_complaint(lat=9.9252, lng=78.1198, source=GeoSource.DESCRIBED)
    new_geo = Geo(lat=9.9254, lng=78.1200, source=GeoSource.DESCRIBED)  # ~30 m
    decision = find_duplicate(new_geo, [existing])
    assert decision.is_duplicate and decision.needs_review


def test_uses_wider_radius_of_the_two_sources():
    # described (250 m) vs exact new report ~180 m away -> still a match
    existing = make_complaint(lat=9.9252, lng=78.1198, source=GeoSource.DESCRIBED)
    new_geo = Geo(lat=9.9268, lng=78.1198, source=GeoSource.WHATSAPP_SHARE)
    assert find_duplicate(new_geo, [existing]).is_duplicate
