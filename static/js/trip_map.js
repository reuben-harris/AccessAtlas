(() => {
  const mapElement = document.getElementById("trip-map");
  const dataElement = document.getElementById("trip-map-data");
  const tileLayerElement = document.getElementById("trip-map-tile-layer");
  const escapeHtml = window.AccessAtlas?.escapeHtml;
  const createThemeTileController = window.AccessAtlas?.createThemeTileController;
  const fitLayersOrDefault = window.AccessAtlas?.fitLayersOrDefault;
  const addHomeControl = window.AccessAtlas?.addHomeControl;
  const addFullscreenControl = window.AccessAtlas?.addFullscreenControl;
  const settleMapLayout = window.AccessAtlas?.settleMapLayout;
  const createLongitudeNormalizer = window.AccessAtlas?.createLongitudeNormalizer;
  const normalizeLatLng = window.AccessAtlas?.normalizeLatLng;
  const configureMapConstraints = window.AccessAtlas?.configureMapConstraints;

  if (
    !mapElement ||
    !dataElement ||
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
    typeof L === "undefined"
  ) {
    return;
  }

  const mapData = JSON.parse(dataElement.textContent);
  const tileLayer = JSON.parse(tileLayerElement.textContent);
  const visits = Array.isArray(mapData.visits) ? mapData.visits : [];
  const accessPoints = Array.isArray(mapData.accessPoints) ? mapData.accessPoints : [];
  const accessTracks = Array.isArray(mapData.accessTracks) ? mapData.accessTracks : [];
  const defaultCenter = [-41.2865, 174.7762];
  const defaultZoom = 5;
  const longitudes = [
    ...visits.map((visit) => visit.longitude),
    ...accessPoints.map((point) => point.longitude),
    ...accessTracks.flatMap((track) =>
      Array.isArray(track.path) ? track.path.map((position) => position.longitude) : [],
    ),
  ];
  const longitudeNormalizer = createLongitudeNormalizer(longitudes);
  const map = L.map(mapElement).setView(defaultCenter, defaultZoom);
  configureMapConstraints(map);
  const featureLayer = L.layerGroup().addTo(map);
  const tileController = createThemeTileController(map, tileLayer);
  let layers = [];

  function visitMarkerLabel(siteVisits) {
    const labels = Array.from(
      new Set(siteVisits.map((visit) => visit.orderLabel).filter(Boolean)),
    );
    if (labels.length === 0) {
      return "-";
    }
    if (labels.length === 1) {
      return labels[0];
    }
    return `${labels[0]}+`;
  }

  function visitIcon(siteVisits) {
    return L.divIcon({
      className: "trip-map-visit-marker",
      html: `<span class="trip-map-visit-marker-pin"><span>${escapeHtml(visitMarkerLabel(siteVisits))}</span></span>`,
      iconAnchor: [13, 32],
      iconSize: [26, 32],
      popupAnchor: [0, -28],
    });
  }

  function accessStartIcon() {
    return L.divIcon({
      className: "trip-map-access-marker",
      html: '<span class="trip-map-access-marker-pin"><i class="ti ti-route-2" aria-hidden="true"></i></span>',
      iconAnchor: [8, 8],
      iconSize: [16, 16],
      popupAnchor: [0, -8],
    });
  }

  function visitRow(visit) {
    return `
      <li class="trip-map-popup-visit">
        <div>
          <a href="${escapeHtml(visit.url)}">${escapeHtml(visit.dateLabel)} ${escapeHtml(visit.timeLabel)}</a>
          <span class="badge bg-blue-lt">${escapeHtml(visit.statusLabel)}</span>
        </div>
        ${
          visit.orderNote
            ? `<div class="text-secondary">${escapeHtml(visit.orderNote)}</div>`
            : ""
        }
      </li>
    `;
  }

  function buildVisitPopup(siteVisits) {
    const first = siteVisits[0];
    return `
      <div class="trip-map-popup-title">
        <a href="${escapeHtml(first.siteUrl)}">${escapeHtml(first.siteCode || "-")}</a>
      </div>
      <div class="trip-map-popup-name">${escapeHtml(first.siteName)}</div>
      <ul class="trip-map-popup-list">
        ${siteVisits.map(visitRow).join("")}
      </ul>
    `;
  }

  function buildAccessPointPopup(point) {
    return `
      <div class="trip-map-popup-title">Access start</div>
      <div><strong>Site:</strong> <a href="${escapeHtml(point.siteUrl || "#")}">${escapeHtml(point.siteCode || "-")}</a> ${escapeHtml(point.siteName || "")}</div>
      <div><strong>Access Record:</strong> ${escapeHtml(point.recordName || "-")}</div>
      <div><strong>Label:</strong> ${escapeHtml(point.label || "-")}</div>
    `;
  }

  function buildTrackPopup(track) {
    return `
      <div class="trip-map-popup-title">Access track</div>
      <div><strong>Label:</strong> ${escapeHtml(track.label || "-")}</div>
      ${
        track.suitability
          ? `<div><strong>Suitability:</strong> ${escapeHtml(track.suitability)}</div>`
          : ""
      }
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

  function drawFeatures() {
    featureLayer.clearLayers();
    const drawnLayers = [];

    for (const track of accessTracks) {
      if (!Array.isArray(track.path)) {
        continue;
      }
      const path = track.path
        .map((position) =>
          normalizeLatLng(position.latitude, position.longitude, longitudeNormalizer),
        )
        .filter(
          ([latitude, longitude]) =>
            Number.isFinite(latitude) && Number.isFinite(longitude),
        );
      if (path.length < 2) {
        continue;
      }
      const layer = L.polyline(path, {
        color: track.color || "#667382",
        opacity: 0.75,
        weight: 3,
      });
      layer.bindPopup(buildTrackPopup(track));
      layer.addTo(featureLayer);
      drawnLayers.push(layer);
    }

    for (const point of accessPoints) {
      const latitude = Number(point.latitude);
      const longitude = Number(point.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        continue;
      }
      const marker = L.marker(
        normalizeLatLng(latitude, longitude, longitudeNormalizer),
        { icon: accessStartIcon() },
      );
      marker.bindPopup(buildAccessPointPopup(point));
      marker.addTo(featureLayer);
      drawnLayers.push(marker);
    }

    for (const group of groupedVisits()) {
      const marker = L.marker(
        normalizeLatLng(group.latitude, group.longitude, longitudeNormalizer),
        { icon: visitIcon(group.visits) },
      );
      marker.bindPopup(buildVisitPopup(group.visits));
      marker.addTo(featureLayer);
      drawnLayers.push(marker);
    }

    return drawnLayers;
  }

  function resetView() {
    fitLayersOrDefault(map, layers, defaultCenter, defaultZoom);
  }

  tileController.apply();
  layers = drawFeatures();
  resetView();
  addHomeControl(map, resetView, { controlClassName: "job-map-home-control" });
  addFullscreenControl(map);
  settleMapLayout(map, resetView);
})();
