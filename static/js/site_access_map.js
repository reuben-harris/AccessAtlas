(() => {
  const mapElement = document.getElementById("site-access-map");
  const dataElement = document.getElementById("site-access-map-data");
  const preferenceElement = document.getElementById("site-access-map-preference");
  const tileLayerElement = document.getElementById("site-access-map-tile-layer");
  const siteLatitudeElement = document.getElementById("site-access-map-site-latitude");
  const siteLongitudeElement = document.getElementById(
    "site-access-map-site-longitude",
  );
  const toggleButtons = Array.from(
    document.querySelectorAll('[data-map-toggle="access-record"]'),
  );
  const escapeHtml = window.AccessAtlas?.escapeHtml;
  const createThemeTileController = window.AccessAtlas?.createThemeTileController;
  const fitLayersOrDefault = window.AccessAtlas?.fitLayersOrDefault;
  const sharedAddHomeControl = window.AccessAtlas?.addHomeControl;
  const addFullscreenControl = window.AccessAtlas?.addFullscreenControl;
  const settleMapLayout = window.AccessAtlas?.settleMapLayout;

  if (
    !mapElement ||
    !dataElement ||
    !preferenceElement ||
    !tileLayerElement ||
    typeof escapeHtml !== "function" ||
    typeof createThemeTileController !== "function" ||
    typeof fitLayersOrDefault !== "function" ||
    typeof sharedAddHomeControl !== "function" ||
    typeof addFullscreenControl !== "function" ||
    typeof settleMapLayout !== "function" ||
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
  const defaultCenter = [-41.2865, 174.7762];
  const defaultZoom = 5;
  // Site access-record pages provide site coordinates, so the shared Home
  // control returns to the site when there are no visible access features.
  // The global Access Records map omits them and falls back to the NZ overview.
  const hasSiteCenter = siteLatitudeElement && siteLongitudeElement;
  const siteLatitude = hasSiteCenter
    ? Number(JSON.parse(siteLatitudeElement.textContent))
    : defaultCenter[0];
  const siteLongitude = hasSiteCenter
    ? Number(JSON.parse(siteLongitudeElement.textContent))
    : defaultCenter[1];
  const initialZoom = hasSiteCenter ? 12 : defaultZoom;
  const featureLayer = L.layerGroup();
  const featureColors = {
    access_start: "#1a5fb4",
    site: "#2fb344",
    gate: "#f59f00",
    note: "#9467bd",
  };
  const arrivalMethodIcons = {
    road: "ti-car",
    boat: "ti-ship",
    heli: "ti-helicopter",
    other: "ti-map-pin",
  };
  const allRecordIds = toggleButtons
    .map((button) => Number(button.dataset.recordId))
    .filter((value) => Number.isInteger(value));
  const savedVisibleRecordIds = Array.isArray(savedPreference.visible_record_ids)
    ? savedPreference.visible_record_ids
        .map((recordId) => Number(recordId))
        .filter((recordId) => Number.isInteger(recordId))
    : [];
  const hasSavedVisibilityPreference = Object.prototype.hasOwnProperty.call(
    savedPreference,
    "visible_record_ids",
  );
  const animateTracksEnabled = {
    value:
      typeof savedPreference.animate_tracks === "boolean"
        ? savedPreference.animate_tracks
        : true,
  };
  const visibleRecordIds = new Set(
    hasSavedVisibilityPreference ? savedVisibleRecordIds : allRecordIds,
  );
  // Visibility is per-record rather than per-feature so a user can hide an
  // entire access record and all of its points/tracks together.
  const hasRecordToggles = toggleButtons.length > 0;

  const map = L.map(mapElement).setView([siteLatitude, siteLongitude], initialZoom);
  featureLayer.addTo(map);
  const tileController = createThemeTileController(map, tileLayer);

  function markerIconClass(feature) {
    if (feature.type === "site") {
      return "ti-home";
    }
    if (feature.type === "access_start") {
      return arrivalMethodIcons[feature.arrivalMethod] || "ti-map-pin";
    }
    if (feature.type === "gate") {
      return "ti-lock";
    }
    if (feature.type === "note") {
      return "ti-note";
    }
    return "ti-map-pin";
  }

  function makeMarkerIcon(feature) {
    const featureType = feature.type;
    const color = featureColors[featureType] || "#667382";
    const iconClass = markerIconClass(feature);
    return L.divIcon({
      className: "site-access-map-marker",
      html: `<span class="site-access-map-marker-pin" style="--site-access-map-marker-color: ${escapeHtml(color)};"><i class="ti ${escapeHtml(iconClass)}" aria-hidden="true"></i></span>`,
      iconAnchor: [12, 12],
      iconSize: [24, 24],
      popupAnchor: [0, -12],
    });
  }

  function buildPointPopup(feature) {
    const details =
      typeof feature.details === "string" && feature.details.trim().length > 0
        ? feature.details.trim()
        : "";
    return `
      <div class="site-access-map-popup-title">${escapeHtml(feature.typeLabel)}</div>
      ${
        feature.siteCode
          ? `<div><strong>Site:</strong> <a href="${escapeHtml(feature.siteUrl || "#")}">${escapeHtml(feature.siteCode)}</a> ${escapeHtml(feature.siteName || "")}</div>`
          : ""
      }
      <div><strong>Access Record:</strong> ${escapeHtml(feature.recordName)}</div>
      <div><strong>Label:</strong> ${escapeHtml(feature.label || "-")}</div>
      <div><strong>Coordinates:</strong> ${escapeHtml(
        `${Number(feature.latitude).toFixed(6)}, ${Number(feature.longitude).toFixed(6)}`,
      )}</div>
      ${
        details
          ? `<div class="site-access-map-popup-details"><strong>Details:</strong> ${escapeHtml(details)}</div>`
          : ""
      }
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

  function buildTrackLayer(track, path) {
    if (
      animateTracksEnabled.value &&
      L.polyline &&
      typeof L.polyline.antPath === "function"
    ) {
      return L.polyline.antPath(path, {
        color: track.color || "#667382",
        pulseColor: track.color || "#667382",
        delay: 1800,
        dashArray: [12, 20],
        weight: 3,
        opacity: 0.75,
      });
    }

    return L.polyline(path, {
      color: track.color || "#667382",
      weight: 3,
      opacity: 0.9,
    });
  }

  function drawFeatures() {
    featureLayer.clearLayers();
    const layers = [];
    // The server emits a normalized map payload, so the client only concerns
    // itself with visibility filters and rendering choices.
    for (const point of points) {
      if (
        hasRecordToggles &&
        point.recordId &&
        !visibleRecordIds.has(Number(point.recordId))
      ) {
        continue;
      }
      const latitude = Number(point.latitude);
      const longitude = Number(point.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        continue;
      }
      const marker = L.marker([latitude, longitude], {
        icon: makeMarkerIcon(point),
      });
      marker.bindPopup(buildPointPopup(point));
      marker.addTo(featureLayer);
      layers.push(marker);
    }
    for (const track of tracks) {
      if (
        hasRecordToggles &&
        track.recordId &&
        !visibleRecordIds.has(Number(track.recordId))
      ) {
        continue;
      }
      const path = Array.isArray(track.path)
        ? track.path
            .map((position) => [Number(position.latitude), Number(position.longitude)])
            .filter(
              ([latitude, longitude]) =>
                Number.isFinite(latitude) && Number.isFinite(longitude),
            )
        : [];
      if (path.length < 2) {
        continue;
      }
      const polyline = buildTrackLayer(track, path);
      polyline.bindPopup(buildTrackPopup(track));
      polyline.addTo(featureLayer);
      layers.push(polyline);
    }
    return layers;
  }

  function fitFeatures(layers) {
    fitLayersOrDefault(map, layers, [siteLatitude, siteLongitude], initialZoom);
  }

  function updateToggleButton(button, isVisible) {
    const icon = button.querySelector("i");
    button.classList.toggle("btn-secondary", isVisible);
    button.classList.toggle("btn-outline-secondary", !isVisible);
    button.title = isVisible ? "Hide on map" : "Show on map";
    button.setAttribute(
      "aria-label",
      isVisible ? "Hide access record on map" : "Show access record on map",
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
        animate_tracks: animateTracksEnabled.value,
      },
    }).catch(() => {});
  }

  function updateAnimationButton(button) {
    const toggle = button.querySelector('[data-role="toggle"]');
    const enabled = animateTracksEnabled.value;
    button.classList.toggle("is-on", enabled);
    button.classList.toggle("is-off", !enabled);
    button.title = enabled ? "Track animation on" : "Track animation off";
    button.setAttribute(
      "aria-label",
      enabled ? "Disable track animation" : "Enable track animation",
    );
    if (toggle) {
      toggle.checked = enabled;
    }
  }

  const TrackAnimationControl = L.Control.extend({
    onAdd() {
      // Animation is persisted because users tend to have a stable preference
      // about whether ant-path motion is helpful or distracting.
      const container = L.DomUtil.create("div", "site-map-animation-control");
      const button = L.DomUtil.create("button", "", container);
      button.type = "button";
      button.innerHTML =
        '<span class="form-check form-switch m-0"><input class="form-check-input" data-role="toggle" type="checkbox" tabindex="-1" aria-hidden="true"></span><span class="site-map-animation-label">Animation</span>';
      updateAnimationButton(button);

      L.DomEvent.disableClickPropagation(container);
      L.DomEvent.on(button, "click", () => {
        animateTracksEnabled.value = !animateTracksEnabled.value;
        updateAnimationButton(button);
        drawnLayers = drawFeatures();
        fitFeatures(drawnLayers);
        savePreference();
        button.blur();
      });

      return container;
    },
  });

  tileController.apply();
  sharedAddHomeControl(
    map,
    () => {
      fitFeatures(drawnLayers);
    },
    {
      controlClassName: "site-map-home-control",
      title: "Reset map view",
      ariaLabel: "Reset map view",
    },
  );
  addFullscreenControl(map);
  map.addControl(new TrackAnimationControl({ position: "topright" }));
  let drawnLayers = drawFeatures();
  fitFeatures(drawnLayers);
  settleMapLayout(map, () => {
    fitFeatures(drawnLayers);
  });

  for (const button of toggleButtons) {
    const recordId = Number(button.dataset.recordId);
    if (!Number.isInteger(recordId)) {
      continue;
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
  }
})();
