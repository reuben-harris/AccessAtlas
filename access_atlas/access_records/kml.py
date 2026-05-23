from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory


def convert_geojson_to_kml_bytes(geojson_value: dict) -> bytes:
    from geojson2kml.buildkml import build_kml

    with TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "access-record.kml"
        # geojson2kml mutates feature properties when building popup content.
        build_kml(deepcopy(geojson_value), output_path=output_path)
        return output_path.read_bytes()
