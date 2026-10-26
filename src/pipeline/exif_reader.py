"""EXIF metadata extraction stage."""
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from .base import PipelineStage


class ExifReader(PipelineStage):
    """Pipeline stage that extracts EXIF metadata from images using Pillow."""

    stage_name = "exif"

    def process(self, image_id: int, file_path: str):
        """Extract EXIF fields from the image and persist them to the database."""
        img = Image.open(file_path)
        exif_dict = {"width": img.width, "height": img.height}

        exif_raw = img.getexif()
        if not exif_raw:
            self.db.save_exif(image_id, exif_dict)
            return

        # Merge main IFD and ExifIFD (0x8769).
        # ISO, FNumber, FocalLength, ExposureTime, DateTimeOriginal are in ExifIFD,
        # NOT in the main IFD — getexif().items() alone misses them.
        raw_exif = {}
        for tag_id, value in exif_raw.items():
            raw_exif[TAGS.get(tag_id, tag_id)] = value
        for tag_id, value in exif_raw.get_ifd(0x8769).items():
            raw_exif[TAGS.get(tag_id, tag_id)] = value

        # decoded only for raw_json field
        decoded = {}
        for tag, value in raw_exif.items():
            try:
                decoded[tag] = str(value)
            except Exception:
                pass

        exif_dict["make"] = decoded.get("Make")
        exif_dict["model"] = decoded.get("Model")
        exif_dict["date_taken"] = _normalize_date(
            decoded.get("DateTimeOriginal") or decoded.get("DateTime")
        )

        # ISO: can be int or tuple like (800,)
        iso_raw = raw_exif.get("ISOSpeedRatings")
        if isinstance(iso_raw, (tuple, list)):
            iso_raw = iso_raw[0]
        exif_dict["iso"] = _safe_int(iso_raw)

        # FocalLength, FNumber, ExposureTime: IFDRational supports float() directly
        exif_dict["focal_length"] = _safe_float(raw_exif.get("FocalLength"))
        exif_dict["aperture"] = _safe_float(raw_exif.get("FNumber"))
        exif_dict["exposure_time"] = _safe_float(raw_exif.get("ExposureTime"))
        exif_dict["orientation"] = _safe_int(raw_exif.get("Orientation"))

        # GPS
        gps_info = exif_raw.get_ifd(0x8825)
        if gps_info:
            lat = _convert_gps(gps_info.get(2), gps_info.get(1))
            lon = _convert_gps(gps_info.get(4), gps_info.get(3))
            if lat and lon:
                exif_dict["gps_lat"] = lat
                exif_dict["gps_lon"] = lon

        # exif_dict["raw"] = decoded # not needed, was for debugging only and fill the database
        # if this is enabled, remember to run from the GUI Clear EXIF ...
        self.db.save_exif(image_id, exif_dict)


def _normalize_date(val: str | None) -> str | None:
    """Convert EXIF date YYYY:MM:DD HH:MM:SS → YYYY-MM-DD HH:MM:SS."""
    if not val:
        return None
    # EXIF uses colons as date separators: '2023:06:15 14:30:22'
    if len(val) >= 10 and val[4] == ":" and val[7] == ":":
        val = val[:4] + "-" + val[5:7] + "-" + val[8:]
    return val


def _safe_int(val):
    """Convert val to int, returning None on failure."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_float(val):
    """Convert val to float, returning None on failure."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _convert_gps(coord, ref):
    """Convert a GPS coordinate tuple (degrees, minutes, seconds) and hemisphere ref to decimal degrees."""
    if not coord or not ref:
        return None
    try:
        degrees = float(coord[0])
        minutes = float(coord[1])
        seconds = float(coord[2])
        result = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ("S", "W"):
            result = -result
        return result
    except (TypeError, ValueError, IndexError, ZeroDivisionError):
        return None
