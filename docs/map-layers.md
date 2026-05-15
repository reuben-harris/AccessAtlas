# Map Layers

Access Atlas includes built-in CARTO and OpenStreetMap base layers. To 
enable additional map layers, follow the instructions below.

## Supported Layers

| Layer | Setup |
| --- | --- |
| CARTO Voyager | Built in |
| CARTO Dark | Built in |
| OpenStreetMap | Built in |
| Esri World Imagery | Set `MAP_ARCGIS_API_KEY` |
| Esri Imagery + Streets | Set `MAP_ARCGIS_API_KEY` |
| Tracestrack Topo | Set `MAP_TRACESTRACK_API_KEY` |

Layers that need a missing API key still appear in the map layer picker, but are
disabled until the key is configured.

## ArcGIS Imagery Layers

1. [Follow this guide here to create an API key with the correct scope.](https://developers.arcgis.com/openlayers/maps/raster-tile-basemaps/display-multiple-basemap-layers/#set-up-authentication)
2. Set the key in the Access Atlas environment, check .env.example for reference.

## Tracestrack Topo

Access Atlas uses the Tracestrack Topo raster layer.

1. Create or sign in to a Tracestrack account. [https://tracestrack.com/](https://tracestrack.com/)
2. Create a new app in the Tracestack dashboard. [https://console.tracestrack.com/app](https://console.tracestrack.com/app)
3. Open the Tracestrack map explorer. [https://console.tracestrack.com/explorer](https://console.tracestrack.com/explorer)
4. Configure the `Base Layers` to `Topo Base`
5. Copy the key from the generated tile URL.
6. Set the key in the Access Atlas environment, check .env.example for reference.
