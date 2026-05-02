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
  const markerLayer = L.layerGroup().addTo(map);
  const tileController = createThemeTileController(map, tileLayer);
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

  function markerIcon(site) {
    return L.divIcon({
      className: "site-list-map-marker",
      html: `
        <span class="site-list-map-marker-pin" style="--site-list-map-marker-color: ${escapeHtml(markerColor(site))};">
          <i class="ti ${escapeHtml(markerIconClass(site))}" aria-hidden="true"></i>
        </span>
      `,
      iconAnchor: [13, 32],
      iconSize: [26, 32],
      popupAnchor: [0, -28],
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
      const marker = L.marker([latitude, longitude], { icon: markerIcon(site) });
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
  map.on("moveend zoomend", queueViewportSave);
})();
