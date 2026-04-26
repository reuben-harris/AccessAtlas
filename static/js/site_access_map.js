(function () {
  const mapElement = document.getElementById("site-access-map");
  const dataElement = document.getElementById("site-access-map-data");
  const preferenceElement = document.getElementById("site-access-map-preference");
  const tileLayerElement = document.getElementById("site-access-map-tile-layer");
  const siteLatitudeElement = document.getElementById("site-access-map-site-latitude");
  const siteLongitudeElement = document.getElementById("site-access-map-site-longitude");
  const toggleButtons = Array.from(
    document.querySelectorAll('[data-map-toggle="access-record"]')
  );
  const escapeHtml = window.AccessAtlas?.escapeHtml;
  const createThemeTileController = window.AccessAtlas?.createThemeTileController;
  const fitLayersOrDefault = window.AccessAtlas?.fitLayersOrDefault;

  if (
    !mapElement ||
    !dataElement ||
    !preferenceElement ||
    !tileLayerElement ||
    !siteLatitudeElement ||
    !siteLongitudeElement ||
    typeof escapeHtml !== "function" ||
    typeof createThemeTileController !== "function" ||
    typeof fitLayersOrDefault !== "function" ||
    typeof L === "undefined"
  ) {
    return;
  }

  const mapData = JSON.parse(dataElement.textContent);
  const preference = JSON.parse(preferenceElement.textContent);
  const savedPreference = preference.value || {};
  const postJSON = window.AccessAtlas?.postJSON;
  const points = Array.isArray(mapData.points) ? mapData.points : [];
  const tracks = Array.isArray(mapData.tracks) ? mapData.tracks : [];
  const tileLayer = JSON.parse(tileLayerElement.textContent);
  const siteLatitude = Number(JSON.parse(siteLatitudeElement.textContent));
  const siteLongitude = Number(JSON.parse(siteLongitudeElement.textContent));
  const featureLayer = L.layerGroup();
  const featureColors = {
    access_start: "#1a5fb4",
    site: "#2fb344",
    gate: "#f59f00",
    note: "#9467bd",
  };
  const allRecordIds = toggleButtons
    .map((button) => Number(button.dataset.recordId))
    .filter((value) => Number.isInteger(value));
  const savedVisibleRecordIds = Array.isArray(savedPreference.visible_record_ids)
    ? savedPreference.visible_record_ids
        .map((recordId) => Number(recordId))
        .filter((recordId) => Number.isInteger(recordId))
    : [];
  const visibleRecordIds = new Set(
    savedVisibleRecordIds.length > 0 ? savedVisibleRecordIds : allRecordIds
  );
  const hasRecordToggles = toggleButtons.length > 0;

  const map = L.map(mapElement).setView([siteLatitude, siteLongitude], 12);
  featureLayer.addTo(map);
  const tileController = createThemeTileController(map, tileLayer);

  function makeMarkerIcon(featureType) {
    const color = featureColors[featureType] || "#667382";
    return L.divIcon({
      className: "site-access-map-marker",
      html: `<span class="site-access-map-marker-pin" style="--site-access-map-marker-color: ${escapeHtml(color)};"></span>`,
      iconAnchor: [10, 20],
      iconSize: [20, 20],
      popupAnchor: [0, -15],
    });
  }

  function buildPointPopup(feature) {
    return `
      <div class="site-access-map-popup-title">${escapeHtml(feature.typeLabel)}</div>
      <div><strong>Access Record:</strong> ${escapeHtml(feature.recordName)}</div>
      <div><strong>Label:</strong> ${escapeHtml(feature.label || "-")}</div>
      <div><strong>Coordinates:</strong> ${escapeHtml(
        `${Number(feature.latitude).toFixed(6)}, ${Number(feature.longitude).toFixed(6)}`
      )}</div>
    `;
  }

  function buildTrackPopup(track) {
    return `
      <div class="site-access-map-popup-title">Track</div>
      <div><strong>Label:</strong> ${escapeHtml(track.label || "-")}</div>
      ${
        track.suitability
          ? `<div><strong>Suitability:</strong> ${escapeHtml(track.suitability)}</div>`
          : ""
      }
    `;
  }

  function drawFeatures() {
    featureLayer.clearLayers();
    const layers = [];
    points.forEach((point) => {
      if (
        hasRecordToggles &&
        point.recordId &&
        !visibleRecordIds.has(Number(point.recordId))
      ) {
        return;
      }
      const latitude = Number(point.latitude);
      const longitude = Number(point.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        return;
      }
      const marker = L.marker([latitude, longitude], {
        icon: makeMarkerIcon(point.type),
      });
      marker.bindPopup(buildPointPopup(point));
      marker.addTo(featureLayer);
      layers.push(marker);
    });
    tracks.forEach((track) => {
      if (
        hasRecordToggles &&
        track.recordId &&
        !visibleRecordIds.has(Number(track.recordId))
      ) {
        return;
      }
      const path = Array.isArray(track.path)
        ? track.path
            .map((position) => [
              Number(position.latitude),
              Number(position.longitude),
            ])
            .filter(
              ([latitude, longitude]) =>
                Number.isFinite(latitude) && Number.isFinite(longitude)
            )
        : [];
      if (path.length < 2) {
        return;
      }
      const polyline = L.polyline(path, {
        color: track.color || "#667382",
        weight: 3,
        opacity: 0.9,
      });
      polyline.bindPopup(buildTrackPopup(track));
      polyline.addTo(featureLayer);
      layers.push(polyline);
    });
    return layers;
  }

  function fitFeatures(layers) {
    fitLayersOrDefault(map, layers, [siteLatitude, siteLongitude], 12);
  }

  function updateToggleButton(button, isVisible) {
    const icon = button.querySelector("i");
    button.classList.toggle("btn-secondary", isVisible);
    button.classList.toggle("btn-outline-secondary", !isVisible);
    button.title = isVisible ? "Hide on map" : "Show on map";
    button.setAttribute(
      "aria-label",
      isVisible ? "Hide access record on map" : "Show access record on map"
    );
    if (!icon) {
      return;
    }
    icon.classList.toggle("ti-eye", isVisible);
    icon.classList.toggle("ti-eye-off", !isVisible);
  }

  function savePreference() {
    const url = mapElement.dataset.preferenceUrl;
    if (!url || typeof postJSON !== "function") {
      return;
    }
    postJSON(url, {
      key: preference.key,
      value: {
        visible_record_ids: Array.from(visibleRecordIds),
      },
    }).catch(() => {});
  }

  tileController.apply();
  let drawnLayers = drawFeatures();
  fitFeatures(drawnLayers);

  toggleButtons.forEach((button) => {
    const recordId = Number(button.dataset.recordId);
    if (!Number.isInteger(recordId)) {
      return;
    }
    updateToggleButton(button, visibleRecordIds.has(recordId));
    button.addEventListener("click", () => {
      if (visibleRecordIds.has(recordId)) {
        visibleRecordIds.delete(recordId);
      } else {
        visibleRecordIds.add(recordId);
      }
      updateToggleButton(button, visibleRecordIds.has(recordId));
      drawnLayers = drawFeatures();
      fitFeatures(drawnLayers);
      savePreference();
    });
  });

})();
