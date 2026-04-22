const globeContainer = document.getElementById("login-globe");
const themeQuery = window.matchMedia("(prefers-color-scheme: dark)");
const countryDataUrl =
  "https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson";
const palette = ["#2fb344", "#d63939", "#f59f00", "#e8590c", "#0ca678"];

function applySystemTheme() {
  const theme = themeQuery.matches ? "dark" : "light";
  document.documentElement.setAttribute("data-bs-theme", theme);
  document.body?.setAttribute("data-bs-theme", theme);
}

function themeIsDark() {
  return document.documentElement.getAttribute("data-bs-theme") === "dark";
}

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function randomColor() {
  return palette[Math.floor(Math.random() * palette.length)];
}

function latLngToVector(THREE, latitude, longitude, radius) {
  const phi = ((90 - latitude) * Math.PI) / 180;
  const theta = ((longitude + 180) * Math.PI) / 180;

  return new THREE.Vector3(
    -(radius * Math.sin(phi) * Math.cos(theta)),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

function createFallbackMessage() {
  if (!globeContainer) {
    return;
  }

  globeContainer.innerHTML =
    '<div class="text-secondary position-absolute top-50 start-50 translate-middle">Globe preview unavailable</div>';
}

async function loadCountryData(globe, updateColors) {
  try {
    const response = await fetch(countryDataUrl);

    if (!response.ok) {
      return;
    }

    const countries = await response.json();
    globe.polygonsData(countries.features.filter((country) => country.properties.name !== "Antarctica"));
    updateColors();
  } catch (error) {
    // The base globe remains useful when the external country data is unavailable.
  }
}

async function initGlobe() {
  if (!globeContainer) {
    return;
  }

  applySystemTheme();

  let THREE;
  let ThreeGlobe;

  try {
    THREE = await import("https://cdn.jsdelivr.net/npm/three@0.183.2/+esm");
    ThreeGlobe = (await import("https://cdn.jsdelivr.net/npm/three-globe@2.45.2/+esm")).default;
  } catch (error) {
    createFallbackMessage();
    return;
  }

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(44, 1, 1, 1000);
  camera.position.set(0, 12, 315);

  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  globeContainer.appendChild(renderer.domElement);

  const ambientLight = new THREE.AmbientLight(0xffffff, 2.2);
  const keyLight = new THREE.DirectionalLight(0xffffff, 2.6);
  const rimLight = new THREE.DirectionalLight(0x2fb344, 1.2);
  keyLight.position.set(-170, 70, 160);
  rimLight.position.set(150, 40, -160);
  scene.add(ambientLight, keyLight, rimLight);

  const globe = new ThreeGlobe()
    .showAtmosphere(true)
    .atmosphereAltitude(0.18)
    .polygonAltitude(0.014)
    .polygonStrokeColor(() => (themeIsDark() ? "rgba(245,247,251,.22)" : "rgba(24,36,51,.24)"));

  globe.rotation.set(0.04, -0.55, 0.05);
  scene.add(globe);

  const globeMaterial = globe.globeMaterial();
  globeMaterial.transparent = true;
  globeMaterial.opacity = 0.96;
  globeMaterial.shininess = 18;

  const pulses = [];

  function updateColors() {
    const dark = themeIsDark();
    renderer.setClearColor(0x000000, 0);
    globeMaterial.color = new THREE.Color(dark ? "#132233" : "#b8dcf0");
    globeMaterial.emissive = new THREE.Color(dark ? "#07131f" : "#dff2fb");
    globeMaterial.emissiveIntensity = dark ? 0.32 : 0.24;
    globe
      .atmosphereColor(dark ? "#2fb344" : "#206bc4")
      .polygonCapColor(() => (dark ? "rgba(47, 179, 68, .28)" : "rgba(125, 211, 137, .48)"))
      .polygonSideColor(() => (dark ? "rgba(12, 166, 120, .20)" : "rgba(47, 179, 68, .24)"))
      .polygonStrokeColor(() => (dark ? "rgba(245,247,251,.22)" : "rgba(35, 125, 55, .30)"));
  }

  function createPulse() {
    const latitude = randomBetween(-58, 66);
    const longitude = randomBetween(-180, 180);
    const color = randomColor();
    const position = latLngToVector(THREE, latitude, longitude, 102);
    const normal = position.clone().normalize();
    const group = new THREE.Group();
    const dotMaterial = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.95,
      depthWrite: false,
    });
    const ringMaterial = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.4,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const dot = new THREE.Mesh(new THREE.SphereGeometry(0.9, 16, 8), dotMaterial);
    const ring = new THREE.Mesh(new THREE.RingGeometry(1.45, 1.9, 64), ringMaterial);

    group.position.copy(position);
    group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
    group.add(dot, ring);
    globe.add(group);

    pulses.push({
      age: 0,
      duration: randomBetween(1.7, 2.5),
      dotMaterial,
      group,
      ring,
      ringMaterial,
    });
  }

  function resize() {
    const width = globeContainer.clientWidth || window.innerWidth;
    const height = globeContainer.clientHeight || window.innerHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();

    const narrow = window.matchMedia("(max-width: 767.98px)").matches;
    camera.position.z = narrow ? 390 : 335;
    globe.scale.setScalar(narrow ? 0.92 : 1.06);
  }

  function animate(now) {
    const currentTime = now / 1000;
    const delta = Math.min(currentTime - (animate.lastTime || currentTime), 0.05);
    animate.lastTime = currentTime;

    globe.rotation.y += delta * 0.22;

    if (!animate.lastPulse || currentTime - animate.lastPulse > randomBetween(0.26, 0.52)) {
      createPulse();
      animate.lastPulse = currentTime;
    }

    for (let index = pulses.length - 1; index >= 0; index -= 1) {
      const pulse = pulses[index];
      pulse.age += delta;
      const progress = pulse.age / pulse.duration;

      if (progress >= 1) {
        globe.remove(pulse.group);
        pulse.ring.geometry.dispose();
        pulse.ringMaterial.dispose();
        pulse.dotMaterial.dispose();
        pulses.splice(index, 1);
        continue;
      }

      pulse.ring.scale.setScalar(1 + progress * 8);
      pulse.ringMaterial.opacity = Math.max(0, 0.42 * (1 - progress));
      pulse.dotMaterial.opacity = Math.max(0.2, 1 - progress * 0.8);
    }

    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }

  themeQuery.addEventListener("change", () => {
    applySystemTheme();
    updateColors();
  });

  updateColors();
  resize();
  window.addEventListener("resize", resize);
  loadCountryData(globe, updateColors);
  requestAnimationFrame(animate);
}

initGlobe();
