(function () {
  const canvas = document.getElementById("login-globe");

  if (!canvas) {
    return;
  }

  const context = canvas.getContext("2d");
  const palette = ["#2fb344", "#d63939", "#f59f00", "#e8590c", "#0ca678"];
  const sensors = [];
  const sensorCount = 18;
  let width = 0;
  let height = 0;
  let pixelRatio = 1;
  let rotation = 0;
  let lastTime = performance.now();

  function applySystemTheme() {
    const theme = window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
    document.documentElement.setAttribute("data-bs-theme", theme);
    document.body?.setAttribute("data-bs-theme", theme);
  }

  function themeIsDark() {
    return document.documentElement.getAttribute("data-bs-theme") === "dark";
  }

  function randomBetween(min, max) {
    return min + Math.random() * (max - min);
  }

  function resetSensor(sensor, now) {
    sensor.latitude = randomBetween(-62, 62);
    sensor.longitude = randomBetween(-180, 180);
    sensor.color = palette[Math.floor(Math.random() * palette.length)];
    sensor.startedAt = now + randomBetween(0, 2500);
    sensor.duration = randomBetween(1200, 2200);
  }

  function resize() {
    pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * pixelRatio);
    canvas.height = Math.floor(height * pixelRatio);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  }

  function globePoint(latitude, longitude, radius) {
    const lat = (latitude * Math.PI) / 180;
    const lon = ((longitude + rotation) * Math.PI) / 180;
    const x = Math.cos(lat) * Math.sin(lon);
    const y = Math.sin(lat);
    const z = Math.cos(lat) * Math.cos(lon);

    return {
      visible: z > -0.18,
      x: x * radius,
      y: -y * radius,
      z,
      scale: Math.max(0, (z + 1) / 2),
    };
  }

  function drawGlobe(centerX, centerY, radius) {
    const dark = themeIsDark();
    const lineColor = dark ? "rgba(245, 247, 251, .20)" : "rgba(32, 107, 196, .18)";
    const glowColor = dark ? "rgba(32, 107, 196, .18)" : "rgba(32, 107, 196, .10)";

    context.save();
    context.translate(centerX, centerY);
    context.beginPath();
    context.arc(0, 0, radius, 0, Math.PI * 2);
    context.fillStyle = dark ? "rgba(24, 36, 51, .46)" : "rgba(255, 255, 255, .42)";
    context.shadowColor = glowColor;
    context.shadowBlur = radius * 0.18;
    context.fill();
    context.shadowBlur = 0;
    context.strokeStyle = lineColor;
    context.lineWidth = 1;
    context.stroke();

    context.beginPath();
    context.arc(0, 0, radius * 0.96, 0, Math.PI * 2);
    context.clip();

    [-60, -30, 0, 30, 60].forEach((latitude) => {
      context.beginPath();
      for (let longitude = -180; longitude <= 180; longitude += 4) {
        const point = globePoint(latitude, longitude, radius);
        if (!point.visible) {
          continue;
        }
        if (longitude === -180) {
          context.moveTo(point.x, point.y);
        } else {
          context.lineTo(point.x, point.y);
        }
      }
      context.strokeStyle = lineColor;
      context.lineWidth = latitude === 0 ? 1.4 : 1;
      context.stroke();
    });

    [-120, -60, 0, 60, 120].forEach((longitude) => {
      context.beginPath();
      let started = false;
      for (let latitude = -84; latitude <= 84; latitude += 3) {
        const point = globePoint(latitude, longitude, radius);
        if (!point.visible) {
          started = false;
          continue;
        }
        if (!started) {
          context.moveTo(point.x, point.y);
          started = true;
        } else {
          context.lineTo(point.x, point.y);
        }
      }
      context.strokeStyle = lineColor;
      context.lineWidth = 1;
      context.stroke();
    });

    context.restore();
  }

  function drawSensor(sensor, now, centerX, centerY, radius) {
    if (now < sensor.startedAt) {
      return;
    }

    const age = now - sensor.startedAt;
    const progress = age / sensor.duration;
    if (progress >= 1) {
      resetSensor(sensor, now);
      return;
    }

    const point = globePoint(sensor.latitude, sensor.longitude, radius);
    if (!point.visible) {
      return;
    }

    const alpha = Math.sin(progress * Math.PI) * Math.max(0.18, point.scale);
    const pulseRadius = 5 + progress * 34;

    context.save();
    context.translate(centerX + point.x, centerY + point.y);
    context.globalAlpha = alpha;
    context.fillStyle = sensor.color;
    context.beginPath();
    context.arc(0, 0, 2.8 + point.scale * 1.8, 0, Math.PI * 2);
    context.fill();

    context.globalAlpha = alpha * (1 - progress);
    context.strokeStyle = sensor.color;
    context.lineWidth = 2;
    context.beginPath();
    context.arc(0, 0, pulseRadius, 0, Math.PI * 2);
    context.stroke();
    context.restore();
  }

  function draw(now) {
    const elapsed = Math.min(now - lastTime, 48);
    lastTime = now;
    rotation = (rotation + elapsed * 0.012) % 360;

    context.clearRect(0, 0, width, height);

    const radius = Math.min(width, height) * 0.34;
    const centerX = width * 0.5;
    const centerY = height * 0.48;

    drawGlobe(centerX, centerY, radius);
    sensors.forEach((sensor) => drawSensor(sensor, now, centerX, centerY, radius));
    requestAnimationFrame(draw);
  }

  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", applySystemTheme);

  applySystemTheme();
  resize();
  for (let index = 0; index < sensorCount; index += 1) {
    const sensor = {};
    resetSensor(sensor, performance.now() - randomBetween(0, 2200));
    sensors.push(sensor);
  }

  window.addEventListener("resize", resize);
  requestAnimationFrame(draw);
})();
