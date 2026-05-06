(() => {
  const mapElement = document.getElementById("site-list-map");
  const dataElement = document.getElementById("site-list-map-data");
  const preferenceElement = document.getElementById("site-list-map-preference");
  const tileLayerElement = document.getElementById("site-list-map-tile-layer");
  const escapeHtml = window.AccessAtlas?.escapeHtml;
  const createThemeTileController = window.AccessAtlas?.createThemeTileController;
  const fitLayersOrDefault = window.AccessAtlas?.fitLayersOrDefault;
  const addHomeControl = window.AccessAtlas?.addHomeControl;
  const addFullscreenControl = window.AccessAtlas?.addFullscreenControl;
  const settleMapLayout = window.AccessAtlas?.settleMapLayout;
  const createLongitudeNormalizer = window.AccessAtlas?.createLongitudeNormalizer;
  const normalizeLatLng = window.AccessAtlas?.normalizeLatLng;
  const configureMapConstraints = window.AccessAtlas?.configureMapConstraints;
  const markerScaleForZoom = window.AccessAtlas?.markerScaleForZoom;
  const postJSON = window.AccessAtlas?.postJSON;

  if (
    !mapElement ||
    !dataElement ||
    !preferenceElement ||
    !tileLayerElement ||
    typeof escapeHtml !== "function" ||
    typeof createThemeTileController !== "function" ||
    typeof fitLayersOrDefault !== "function" ||
    typeof addHomeControl !== "function" ||
    typeof addFullscreenControl !== "function" ||
    typeof settleMapLayout !== "function" ||
    typeof createLongitudeNormalizer !== "function" ||
    typeof normalizeLatLng !== "function" ||
    typeof configureMapConstraints !== "function" ||
    typeof markerScaleForZoom !== "function" ||
    typeof L === "undefined"
  ) {
    return;
  }

  const sites = JSON.parse(dataElement.textContent);
  const preference = JSON.parse(preferenceElement.textContent);
  const tileLayer = JSON.parse(tileLayerElement.textContent);
  const savedPreference = preference.value || {};
  const defaultCenter = [-41.2865, 174.7762];
  const defaultZoom = 5;
  const map = L.map(mapElement).setView(defaultCenter, defaultZoom);
  configureMapConstraints(map);
  const markerLayer = L.layerGroup().addTo(map);
  const tileController = createThemeTileController(map, tileLayer);
  const longitudeNormalizer = createLongitudeNormalizer(
    sites.map((site) => site.longitude),
  );
  let viewportSaveTimeout = null;
  let markers = [];

  function currentViewport() {
    const center = map.getCenter();
    return {
      lat: center.lat,
      lng: center.lng,
      zoom: map.getZoom(),
    };
  }

  function savePreference() {
    if (typeof postJSON !== "function") {
      return;
    }

    postJSON(mapElement.dataset.preferenceUrl || "/accounts/preferences/", {
      key: preference.key,
      value: { viewport: currentViewport() },
    }).catch(() => {});
  }

  function queueViewportSave() {
    window.clearTimeout(viewportSaveTimeout);
    viewportSaveTimeout = window.setTimeout(savePreference, 500);
  }

  function markerColor(site) {
    if (site.hasWarnings) {
      return "#d97706";
    }
    if (site.syncStatus === "stale") {
      return "#667382";
    }
    return "#206bc4";
  }

  function markerIconClass(site) {
    if (site.hasWarnings) {
      return "ti-alert-triangle-filled";
    }
    if (site.syncStatus === "stale") {
      return "ti-clock-exclamation";
    }
    return "ti-point-filled";
  }

  function markerSize() {
    const scale = markerScaleForZoom(map.getZoom());
    if (scale === "world") {
      return { anchor: [4, 10], icon: 0, iconSize: [8, 10], pin: 8 };
    }
    if (scale === "far") {
      return { anchor: [6, 15], icon: 7, iconSize: [12, 15], pin: 12 };
    }
    return { anchor: [13, 32], icon: 14, iconSize: [26, 32], pin: 26 };
  }

  function markerIcon(site) {
    const size = markerSize();
    return L.divIcon({
      className: "site-list-map-marker",
      html: `
        <span class="site-list-map-marker-pin" style="--site-list-map-marker-color: ${escapeHtml(markerColor(site))}; --site-list-map-marker-size: ${size.pin}px; --site-list-map-marker-icon-size: ${size.icon}px;">
          <i class="ti ${escapeHtml(markerIconClass(site))}" aria-hidden="true"></i>
        </span>
      `,
      iconAnchor: size.anchor,
      iconSize: size.iconSize,
      popupAnchor: [0, -Math.max(size.iconSize[1] - 4, 6)],
    });
  }

  function buildPopup(site) {
    const statusBadgeClass =
      site.syncStatus === "active"
        ? "site-list-map-badge site-list-map-badge-active"
        : "site-list-map-badge site-list-map-badge-stale";
    const warningBadge = site.hasWarnings
      ? '<span class="badge site-list-map-badge site-list-map-badge-warning">Warnings</span>'
      : "";

    return `
      <div class="site-list-map-popup-code">
        <a href="${escapeHtml(site.url)}">${escapeHtml(site.code)}</a>
      </div>
      <div class="site-list-map-popup-name">${escapeHtml(site.name)}</div>
      <div class="site-list-map-popup-meta">
        <span class="badge ${statusBadgeClass}">${escapeHtml(site.syncStatusLabel)}</span>
        ${warningBadge}
      </div>
    `;
  }

  function drawMarkers() {
    markerLayer.clearLayers();
    const siteMarkers = [];

    for (const site of sites) {
      const latitude = Number(site.latitude);
      const longitude = Number(site.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        continue;
      }
      const marker = L.marker(
        normalizeLatLng(latitude, longitude, longitudeNormalizer),
        {
          icon: markerIcon(site),
        },
      );
      marker.siteData = site;
      marker.bindPopup(buildPopup(site));
      marker.addTo(markerLayer);
      siteMarkers.push(marker);
    }

    return siteMarkers;
  }

  function applySavedViewport() {
    if (
      savedPreference.viewport &&
      Number.isFinite(Number(savedPreference.viewport.lat)) &&
      Number.isFinite(Number(savedPreference.viewport.lng)) &&
      Number.isInteger(savedPreference.viewport.zoom)
    ) {
      map.setView(
        [Number(savedPreference.viewport.lat), Number(savedPreference.viewport.lng)],
        savedPreference.viewport.zoom,
      );
      return;
    }

    fitLayersOrDefault(map, markers, defaultCenter, defaultZoom);
  }

  addHomeControl(
    map,
    () => {
      fitLayersOrDefault(map, markers, defaultCenter, defaultZoom);
      savePreference();
    },
    { controlClassName: "job-map-home-control" },
  );
  addFullscreenControl(map);
  tileController.apply();
  markers = drawMarkers();
  applySavedViewport();
  settleMapLayout(map, applySavedViewport);
  map.on("zoomend", () => {
    for (const marker of markers) {
      marker.setIcon(markerIcon(marker.siteData));
    }
  });
  map.on("moveend zoomend", queueViewportSave);
})();
