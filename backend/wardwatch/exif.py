"""Photo EXIF GPS extraction (spec §1, tier 2)."""
from __future__ import annotations

import io

from PIL import ExifTags, Image

_GPS_IFD = next(k for k, v in ExifTags.TAGS.items() if v == "GPSInfo")


def _to_deg(value) -> float:
    d, m, s = (float(x) for x in value)
    return d + m / 60 + s / 3600


def extract_gps(photo: bytes) -> tuple[float, float] | None:
    try:
        img = Image.open(io.BytesIO(photo))
        exif = img.getexif()
        gps = exif.get_ifd(_GPS_IFD)
    except Exception:  # noqa: BLE001
        return None
    if not gps:
        return None
    try:
        lat = _to_deg(gps[2])
        lng = _to_deg(gps[4])
        if gps.get(1) == "S":
            lat = -lat
        if gps.get(3) == "W":
            lng = -lng
        return (lat, lng)
    except (KeyError, TypeError, ValueError):
        return None
