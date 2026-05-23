// Renders the Site Visits map.
(() => {
  const mapElement = document.getElementById("site-visit-map");
  const dataElement = document.getElementById("site-visit-map-data");
  const basemapConfigElement = document.getElementById("map-basemap-config");
  const basemapPreferenceElement = document.getElementById("map-basemap-preference");
  const escapeHtml = window.AccessAtlas?.escapeHtml;
  const siteLabelHtml = window.AccessAtlas?.siteLabelHtml;
  const createBasemapController = window.AccessAtlas?.createBasemapController;
  const fitLayersOrDefault = window.AccessAtlas?.fitLayersOrDefault;
  const addHomeControl = window.AccessAtlas?.addHomeControl;
  const addFilterControl = window.AccessAtlas?.addFilterControl;
  const addBasemapControl = window.AccessAtlas?.addBasemapControl;
  const addFullscreenControl = window.AccessAtlas?.addFullscreenControl;
  const createFullscreenSafeOffcanvasController =
    window.AccessAtlas?.createFullscreenSafeOffcanvasController;
  const settleMapLayout = window.AccessAtlas?.settleMapLayout;
  const createLongitudeNormalizer = window.AccessAtlas?.createLongitudeNormalizer;
  const normalizeLatLng = window.AccessAtlas?.normalizeLatLng;
  const configureMapConstraints = window.AccessAtlas?.configureMapConstraints;

  if (
    !mapElement ||
    !dataElement ||
    !basemapConfigElement ||
    !basemapPreferenceElement ||
    typeof escapeHtml !== "function" ||
    typeof siteLabelHtml !== "function" ||
    typeof createBasemapController !== "function" ||
    typeof fitLayersOrDefault !== "function" ||
    typeof addHomeControl !== "function" ||
    typeof addFilterControl !== "function" ||
    typeof addBasemapControl !== "function" ||
    typeof addFullscreenControl !== "function" ||
    typeof createFullscreenSafeOffcanvasController !== "function" ||
    typeof settleMapLayout !== "function" ||
    typeof createLongitudeNormalizer !== "function" ||
    typeof normalizeLatLng !== "function" ||
    typeof configureMapConstraints !== "function" ||
    typeof L === "undefined"
  ) {
    return;
  }

  const visits = JSON.parse(dataElement.textContent);
  const basemapConfig = JSON.parse(basemapConfigElement.textContent);
  const basemapPreference = JSON.parse(basemapPreferenceElement.textContent);
  const defaultCenter = [-41.2865, 174.7762];
  const defaultZoom = 5;
  const initialFilterCount = Number(mapElement.dataset.filterCount || 0);
  const longitudeNormalizer = createLongitudeNormalizer(
    visits.map((visit) => visit.longitude),
  );
  const map = L.map(mapElement).setView(defaultCenter, defaultZoom);
  const filterPanel = createFullscreenSafeOffcanvasController(mapElement, { map });
  configureMapConstraints(map);
  const markerLayer = L.layerGroup().addTo(map);
  const basemapController = createBasemapController(
    map,
    basemapConfig,
    basemapPreference,
    mapElement,
  );
  let markers = [];

  function statusBadgeClass(status) {
    if (status === "completed") {
      return "bg-green-lt";
    }
    if (status === "skipped") {
      return "bg-yellow-lt";
    }
    return "bg-blue-lt";
  }

  function markerColor(groupVisits) {
    const statuses = new Set(groupVisits.map((visit) => visit.status));
    if (statuses.has("planned")) {
      return "#206bc4";
    }
    if (statuses.has("skipped")) {
      return "#f59f00";
    }
    if (statuses.has("completed")) {
      return "#2fb344";
    }
    return "#667382";
  }

  function markerLabel(groupVisits) {
    return groupVisits.length > 99 ? "99+" : String(groupVisits.length);
  }

  function markerIcon(groupVisits) {
    return L.divIcon({
      className: "site-visit-map-marker",
      html: `
        <span class="site-visit-map-marker-pin" style="--site-visit-map-marker-color: ${escapeHtml(markerColor(groupVisits))};">
          <span class="site-visit-map-marker-count">${escapeHtml(markerLabel(groupVisits))}</span>
        </span>
      `,
      iconAnchor: [13, 32],
      iconSize: [26, 32],
      popupAnchor: [0, -28],
    });
  }

  function jobCountLabel(jobCount) {
    const count = Number(jobCount);
    if (count === 1) {
      return "1 job";
    }
    return `${Number.isFinite(count) ? count : 0} jobs`;
  }

  function visitRow(visit) {
    return `
      <li class="site-visit-map-popup-visit">
        <div>
          <a href="${escapeHtml(visit.url)}">${siteLabelHtml(visit.siteCode, visit.siteName)}</a>
        </div>
        <div>
          <strong>Trip:</strong>
          <a href="${escapeHtml(visit.tripUrl)}">${escapeHtml(visit.tripName)}</a>
        </div>
        <div class="site-visit-map-popup-meta">
          <span>${escapeHtml(visit.plannedDayLabel)} ${escapeHtml(visit.timeLabel)}</span>
          <span class="badge ${statusBadgeClass(visit.status)}">${escapeHtml(visit.statusLabel)}</span>
          <span class="badge bg-secondary-lt">${escapeHtml(jobCountLabel(visit.jobCount))}</span>
        </div>
      </li>
    `;
  }

  function popupTitle(groupVisits) {
    if (groupVisits.length === 1) {
      const visit = groupVisits[0];
      return `<a href="${escapeHtml(visit.siteUrl)}">${siteLabelHtml(visit.siteCode, visit.siteName)}</a>`;
    }
    return `${groupVisits.length} Site Visits`;
  }

  function buildPopup(groupVisits) {
    return `
      <div class="site-visit-map-popup-title">${popupTitle(groupVisits)}</div>
      <ul class="site-visit-map-popup-list">
        ${groupVisits.map(visitRow).join("")}
      </ul>
    `;
  }

  function groupedVisits() {
    const groups = new Map();
    for (const visit of visits) {
      const latitude = Number(visit.latitude);
      const longitude = Number(visit.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        continue;
      }
      const key = `${latitude.toFixed(6)},${longitude.toFixed(6)}`;
      const group = groups.get(key) || {
        latitude,
        longitude,
        visits: [],
      };
      group.visits.push(visit);
      groups.set(key, group);
    }
    return Array.from(groups.values());
  }

  function drawMarkers() {
    markerLayer.clearLayers();
    const visitMarkers = [];

    for (const group of groupedVisits()) {
      const marker = L.marker(
        normalizeLatLng(group.latitude, group.longitude, longitudeNormalizer),
        { icon: markerIcon(group.visits) },
      );
      marker.bindPopup(buildPopup(group.visits));
      marker.addTo(markerLayer);
      visitMarkers.push(marker);
    }

    return visitMarkers;
  }

  function resetView() {
    fitLayersOrDefault(map, markers, defaultCenter, defaultZoom);
  }

  addHomeControl(map, resetView);
  addFullscreenControl(map);
  if (filterPanel) {
    addFilterControl(map, filterPanel.show, { count: initialFilterCount });
  }
  addBasemapControl(map, basemapController);
  basemapController.apply();
  markers = drawMarkers();
  resetView();
  settleMapLayout(map, resetView);
})();
