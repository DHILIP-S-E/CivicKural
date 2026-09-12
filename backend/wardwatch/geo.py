"""Geospatial helpers and geo-source-adjusted dedup radii (spec §1, §6)."""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from .models import GeoSource

# Dedup radius in metres, keyed by the confidence of the location source.
DEDUP_RADIUS_M: dict[GeoSource, int] = {
    GeoSource.WHATSAPP_SHARE: 75,
    GeoSource.EXIF: 75,
    GeoSource.GEOCODED: 150,
    GeoSource.DESCRIBED: 250,
}

# Text-only matches are never silently auto-merged — a human double-checks.
REVIEW_BEFORE_MERGE: set[GeoSource] = {GeoSource.DESCRIBED}

# Pattern-agent clustering radius (spec §6).
PATTERN_RADIUS_M = 150

# Ward bounding boxes (min_lat, min_lng, max_lat, max_lng) for geocoder biasing.
WARD_BBOX: dict[str, tuple[float, float, float, float]] = {
    "MDU-W14": (9.9100, 78.1000, 9.9400, 78.1400),
}


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * asin(sqrt(a))


def dedup_radius_m(source: GeoSource) -> int:
    return DEDUP_RADIUS_M[source]


def requires_merge_review(source: GeoSource) -> bool:
    return source in REVIEW_BEFORE_MERGE


def in_ward_bbox(ward_id: str, lat: float, lng: float) -> bool:
    bbox = WARD_BBOX.get(ward_id)
    if bbox is None:
        return True
    min_lat, min_lng, max_lat, max_lng = bbox
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng
