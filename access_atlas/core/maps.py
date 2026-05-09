from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from django.conf import settings

from access_atlas.accounts.models import User
from access_atlas.accounts.preferences import (
    BASEMAP_LAYER_CARTO_DARK,
    BASEMAP_LAYER_CARTO_VOYAGER,
    BASEMAP_LAYER_ESRI_IMAGERY_STREETS,
    BASEMAP_LAYER_ESRI_WORLD_IMAGERY,
    BASEMAP_LAYER_OSM_STANDARD,
    BASEMAP_LAYER_TRACESTRACK_TOPO,
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


@dataclass(frozen=True)
class MapTile:
    """Tile source options emitted to Leaflet using the frontend JSON contract."""

    url: str
    attribution: str = ""
    max_zoom: int | None = 19
    min_zoom: int | None = None
    tile_size: int | None = None
    zoom_offset: int | None = None
    referrer_policy: str = ""

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "url": self.url,
            "attribution": self.attribution,
        }
        if self.max_zoom is not None:
            payload["maxZoom"] = self.max_zoom
        if self.min_zoom is not None:
            payload["minZoom"] = self.min_zoom
        if self.tile_size is not None:
            payload["tileSize"] = self.tile_size
        if self.zoom_offset is not None:
            payload["zoomOffset"] = self.zoom_offset
        if self.referrer_policy:
            payload["referrerPolicy"] = self.referrer_policy
        return payload


@dataclass(frozen=True)
class MapLayer:
    """Selectable basemap layer, including disabled setup states."""

    id: str
    label: str
    tiles: tuple[MapTile, ...] = ()
    available: bool = True
    disabled_reason: str = ""
    max_zoom: int | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "label": self.label,
            "available": self.available,
        }
        if not self.available:
            payload["disabledReason"] = self.disabled_reason
            return payload
        if len(self.tiles) == 1:
            payload.update(self.tiles[0].to_dict())
            return payload
        payload["tiles"] = [tile.to_dict() for tile in self.tiles]
        if self.max_zoom is not None:
            payload["maxZoom"] = self.max_zoom
        return payload


def _has_tile_source(layer: dict[str, object]) -> bool:
    if isinstance(layer.get("url"), str):
        return bool(layer["url"])
    tiles = layer.get("tiles")
    if not isinstance(tiles, list):
        return False
    return any(isinstance(tile, dict) and bool(tile.get("url")) for tile in tiles)


def _unavailable_layer(
    layer_id: str,
    label: str,
    disabled_reason: str,
) -> MapLayer:
    return MapLayer(
        id=layer_id,
        label=label,
        available=False,
        disabled_reason=disabled_reason,
    )


def _provider_url(url_template: str, token_parameter: str, token: str) -> str:
    return f"{url_template}?{token_parameter}={quote(token, safe='')}"


def _esri_world_imagery_tile() -> MapTile:
    # Esri World Imagery is the satellite base. The hybrid layer below reuses
    # this tile and stacks Esri's reference/detail tiles over it.
    return MapTile(
        url=_provider_url(
            (
                "https://ibasemaps-api.arcgis.com/arcgis/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}"
            ),
            "token",
            settings.MAP_ARCGIS_API_KEY,
        ),
        attribution=ESRI_WORLD_IMAGERY_ATTRIBUTION,
        max_zoom=19,
    )


def _esri_open_hybrid_detail_tile() -> MapTile:
    # Open Hybrid Detail is a reference/detail overlay, not a full imagery
    # basemap. It must be rendered above World Imagery to show satellite data.
    # Esri Static Basemap Tiles use 512px tiles; the Leaflet zoom offset keeps
    # the Open Hybrid Detail tile matrix aligned with 256px raster providers.
    return MapTile(
        url=_provider_url(
            (
                "https://static-map-tiles-api.arcgis.com/arcgis/rest/services/"
                "static-basemap-tiles-service/v1/open/hybrid/detail/static/"
                "tile/{z}/{y}/{x}"
            ),
            "token",
            settings.MAP_ARCGIS_API_KEY,
        ),
        attribution=ESRI_OPEN_HYBRID_DETAIL_ATTRIBUTION,
        tile_size=512,
        zoom_offset=-1,
        min_zoom=1,
        max_zoom=23,
    )


def _carto_layers() -> list[MapLayer]:
    return [
        MapLayer(
            id=BASEMAP_LAYER_CARTO_VOYAGER,
            label="CARTO Voyager",
            tiles=(
                MapTile(
                    url=(
                        "https://{s}.basemaps.cartocdn.com/rastertiles/"
                        "voyager/{z}/{x}/{y}{r}.png"
                    ),
                    attribution=CARTO_ATTRIBUTION,
                    max_zoom=19,
                ),
            ),
        ),
        MapLayer(
            id=BASEMAP_LAYER_CARTO_DARK,
            label="CARTO Dark",
            tiles=(
                MapTile(
                    url=(
                        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                    ),
                    attribution=CARTO_ATTRIBUTION,
                    max_zoom=19,
                ),
            ),
        ),
    ]


def _osm_layer() -> MapLayer:
    # OSM's public tile policy requires this exact URL and a non-empty Referer.
    return MapLayer(
        id=BASEMAP_LAYER_OSM_STANDARD,
        label="OpenStreetMap",
        tiles=(
            MapTile(
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                attribution=OSM_ATTRIBUTION,
                max_zoom=19,
                referrer_policy="strict-origin-when-cross-origin",
            ),
        ),
    )


def _esri_world_imagery_layer() -> MapLayer:
    if not settings.MAP_ARCGIS_API_KEY:
        return _unavailable_layer(
            BASEMAP_LAYER_ESRI_WORLD_IMAGERY,
            "Esri World Imagery",
            "Set MAP_ARCGIS_API_KEY to enable Esri imagery layers.",
        )

    return MapLayer(
        id=BASEMAP_LAYER_ESRI_WORLD_IMAGERY,
        label="Esri World Imagery",
        tiles=(_esri_world_imagery_tile(),),
    )


def _esri_imagery_streets_layer() -> MapLayer:
    if not settings.MAP_ARCGIS_API_KEY:
        return _unavailable_layer(
            BASEMAP_LAYER_ESRI_IMAGERY_STREETS,
            "Esri Imagery + Streets",
            "Set MAP_ARCGIS_API_KEY to enable Esri imagery layers.",
        )

    return MapLayer(
        id=BASEMAP_LAYER_ESRI_IMAGERY_STREETS,
        label="Esri Imagery + Streets",
        tiles=(
            _esri_world_imagery_tile(),
            _esri_open_hybrid_detail_tile(),
        ),
        max_zoom=23,
    )


def _tracestrack_topo_layer() -> MapLayer:
    if not settings.MAP_TRACESTRACK_API_KEY:
        return _unavailable_layer(
            BASEMAP_LAYER_TRACESTRACK_TOPO,
            "Tracestrack Topo",
            "Set MAP_TRACESTRACK_API_KEY to enable this layer.",
        )

    return MapLayer(
        id=BASEMAP_LAYER_TRACESTRACK_TOPO,
        label="Tracestrack Topo",
        tiles=(
            MapTile(
                url=_provider_url(
                    "https://tile.tracestrack.com/topo_en/{z}/{x}/{y}.webp",
                    "key",
                    settings.MAP_TRACESTRACK_API_KEY,
                ),
                attribution=TRACESTRACK_TOPO_ATTRIBUTION,
                max_zoom=19,
            ),
        ),
    )


def map_basemap_config() -> dict[str, object]:
    """Return the configured basemap registry for Leaflet map pages."""
    layers = [
        *_carto_layers(),
        _osm_layer(),
        _esri_world_imagery_layer(),
        _esri_imagery_streets_layer(),
        _tracestrack_topo_layer(),
    ]

    return {
        "defaults": default_map_basemap_preference(),
        "layers": [layer.to_dict() for layer in layers],
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
