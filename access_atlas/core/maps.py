from __future__ import annotations

from typing import Any
from urllib.parse import quote

from django.conf import settings

from access_atlas.accounts.models import User
from access_atlas.accounts.preferences import (
    MAP_BASEMAP_PREFERENCE_KEY,
    default_map_basemap_preference,
    get_user_preference,
)

CARTO_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">'
    "OpenStreetMap</a> contributors &copy; "
    '<a href="https://carto.com/attributions">CARTO</a>'
)

OSM_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">'
    "OpenStreetMap</a> contributors"
)

TRACESTRACK_TOPO_ATTRIBUTION = (
    'Data: &copy; <a href="https://www.openstreetmap.org/copyright">'
    "OpenStreetMap</a> contributors, SRTM, GEBCO, SONNY's LiDAR DTM, "
    "NASADEM, ESA WorldCover; Maps &copy; "
    '<a href="https://tracestrack.com/">Tracestrack</a>'
)

ESRI_OPEN_HYBRID_DETAIL_ATTRIBUTION = (
    'Map data &copy; <a href="https://www.openstreetmap.org/copyright">'
    "OpenStreetMap</a> contributors, Microsoft, Esri Community Maps "
    'contributors; Map layer by <a href="https://www.esri.com/">Esri</a>'
)

ESRI_WORLD_IMAGERY_ATTRIBUTION = (
    '<a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics, '
    "and the GIS User Community"
)


def _has_tile_source(layer: dict[str, object]) -> bool:
    if isinstance(layer.get("url"), str):
        return bool(layer["url"])
    tiles = layer.get("tiles")
    if not isinstance(tiles, list):
        return False
    return any(isinstance(tile, dict) and bool(tile.get("url")) for tile in tiles)


def _available_layer(layer: dict[str, object]) -> dict[str, object]:
    layer["available"] = True
    return layer


def _unavailable_layer(
    layer_id: str,
    label: str,
    disabled_reason: str,
) -> dict[str, object]:
    return {
        "id": layer_id,
        "label": label,
        "available": False,
        "disabledReason": disabled_reason,
    }


def _provider_url(url_template: str, token_parameter: str, token: str) -> str:
    return f"{url_template}?{token_parameter}={quote(token, safe='')}"


def _esri_world_imagery_tile() -> dict[str, object]:
    return {
        "url": _provider_url(
            (
                "https://ibasemaps-api.arcgis.com/arcgis/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}"
            ),
            "token",
            settings.MAP_ARCGIS_API_KEY,
        ),
        "attribution": ESRI_WORLD_IMAGERY_ATTRIBUTION,
        "maxZoom": 19,
    }


def _esri_open_hybrid_detail_tile() -> dict[str, object]:
    # Esri Static Basemap Tiles use 512px tiles; the Leaflet zoom offset keeps
    # the Open Hybrid Detail tile matrix aligned with 256px raster providers.
    return {
        "url": _provider_url(
            (
                "https://static-map-tiles-api.arcgis.com/arcgis/rest/services/"
                "static-basemap-tiles-service/v1/open/hybrid/detail/static/"
                "tile/{z}/{y}/{x}"
            ),
            "token",
            settings.MAP_ARCGIS_API_KEY,
        ),
        "attribution": ESRI_OPEN_HYBRID_DETAIL_ATTRIBUTION,
        "tileSize": 512,
        "zoomOffset": -1,
        "minZoom": 1,
        "maxZoom": 23,
    }


def _carto_layers() -> list[dict[str, object]]:
    return [
        _available_layer(
            {
                "id": "carto-voyager",
                "label": "CARTO Voyager",
                "url": (
                    "https://{s}.basemaps.cartocdn.com/rastertiles/"
                    "voyager/{z}/{x}/{y}{r}.png"
                ),
                "attribution": CARTO_ATTRIBUTION,
                "maxZoom": 19,
            }
        ),
        _available_layer(
            {
                "id": "carto-dark",
                "label": "CARTO Dark",
                "url": (
                    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                ),
                "attribution": CARTO_ATTRIBUTION,
                "maxZoom": 19,
            }
        ),
    ]


def _osm_layer() -> dict[str, object]:
    # OSM's public tile policy requires this exact URL and a non-empty Referer.
    return _available_layer(
        {
            "id": "osm-standard",
            "label": "OpenStreetMap",
            "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": OSM_ATTRIBUTION,
            "maxZoom": 19,
            "referrerPolicy": "strict-origin-when-cross-origin",
        }
    )


def _esri_world_imagery_layer() -> dict[str, object]:
    if not settings.MAP_ARCGIS_API_KEY:
        return _unavailable_layer(
            "esri-world-imagery",
            "Esri World Imagery",
            "Set MAP_ARCGIS_API_KEY to enable Esri imagery layers.",
        )

    return _available_layer(
        {
            "id": "esri-world-imagery",
            "label": "Esri World Imagery",
            **_esri_world_imagery_tile(),
            "maxZoom": 19,
        }
    )


def _esri_open_hybrid_detail_layer() -> dict[str, object]:
    if not settings.MAP_ARCGIS_API_KEY:
        return _unavailable_layer(
            "esri-open-hybrid-detail",
            "Esri Imagery + Streets",
            "Set MAP_ARCGIS_API_KEY to enable Esri imagery layers.",
        )

    return _available_layer(
        {
            "id": "esri-open-hybrid-detail",
            "label": "Esri Imagery + Streets",
            "tiles": [
                _esri_world_imagery_tile(),
                _esri_open_hybrid_detail_tile(),
            ],
            "maxZoom": 23,
        }
    )


def _tracestrack_topo_layer() -> dict[str, object]:
    if not settings.MAP_TRACESTRACK_API_KEY:
        return _unavailable_layer(
            "tracestrack-topo",
            "Tracestrack Topo",
            "Set MAP_TRACESTRACK_API_KEY to enable this layer.",
        )

    return _available_layer(
        {
            "id": "tracestrack-topo",
            "label": "Tracestrack Topo",
            "url": _provider_url(
                "https://tile.tracestrack.com/topo_en/{z}/{x}/{y}.webp",
                "key",
                settings.MAP_TRACESTRACK_API_KEY,
            ),
            "attribution": TRACESTRACK_TOPO_ATTRIBUTION,
            "maxZoom": 19,
        }
    )


def map_basemap_config() -> dict[str, object]:
    """Return the configured basemap registry for Leaflet map pages."""
    layers: list[dict[str, object]] = [
        *_carto_layers(),
        _osm_layer(),
        _esri_world_imagery_layer(),
        _esri_open_hybrid_detail_layer(),
        _tracestrack_topo_layer(),
    ]

    return {
        "defaults": default_map_basemap_preference(),
        "layers": layers,
    }


def map_basemap_preference(user: User) -> dict[str, Any]:
    value = get_user_preference(
        user,
        MAP_BASEMAP_PREFERENCE_KEY,
        default_map_basemap_preference(),
    )
    available_layer_ids = {
        str(layer["id"])
        for layer in map_basemap_config()["layers"]
        if layer.get("available") is not False and _has_tile_source(layer)
    }
    saved_layer_values = [
        layer_id
        for layer_id in (value.get("light"), value.get("dark"))
        if layer_id is not None
    ]
    saved_layer_ids = {
        layer_id for layer_id in saved_layer_values if isinstance(layer_id, str)
    }
    has_stale_layer = len(saved_layer_ids) != len(saved_layer_values)
    has_stale_layer = has_stale_layer or not saved_layer_ids.issubset(
        available_layer_ids
    )
    if has_stale_layer:
        # Provider-backed basemaps can disappear when deployment env changes.
        # Clearing the stale user value keeps the browser on the default layer.
        if getattr(user, "is_authenticated", False):
            user.preferences.filter(key=MAP_BASEMAP_PREFERENCE_KEY).delete()
        value = default_map_basemap_preference()

    return {
        "key": MAP_BASEMAP_PREFERENCE_KEY,
        "value": value,
    }
