"""Landmark geocoding via AWS Location Service, biased to a ward bounding box (spec §1)."""
from __future__ import annotations

from typing import Callable

import boto3

from .config import get_settings
from .geo import WARD_BBOX, in_ward_bbox

_hook: Callable[[str, str], tuple[float, float] | None] | None = None
PLACE_INDEX = "wardwatch-places"


def set_geocode_hook(fn: Callable[[str, str], tuple[float, float] | None] | None) -> None:
    global _hook
    _hook = fn


def geocode_landmark(ward_id: str, text: str) -> tuple[float, float] | None:
    """Return (lat, lng) if a landmark in `text` resolves inside the ward, else None."""
    if _hook is not None:
        return _hook(ward_id, text)

    bbox = WARD_BBOX.get(ward_id)
    client = boto3.client("location", region_name=get_settings().aws_region)
    params = {"IndexName": PLACE_INDEX, "Text": text, "MaxResults": 3}
    if bbox:
        min_lat, min_lng, max_lat, max_lng = bbox
        params["FilterBBox"] = [min_lng, min_lat, max_lng, max_lat]

    results = client.search_place_index_for_text(**params).get("Results", [])
    for r in results:
        lng, lat = r["Place"]["Geometry"]["Point"]
        if in_ward_bbox(ward_id, lat, lng):
            return (lat, lng)
    return None
