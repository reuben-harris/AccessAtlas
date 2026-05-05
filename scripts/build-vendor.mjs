import { cp, mkdir, rm } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const vendorRoot = path.join(root, "static", "vendor");

async function copyIntoVendor(targetDir, entries) {
  await mkdir(targetDir, { recursive: true });
  for (const [from, to] of entries) {
    await cp(from, path.join(targetDir, to), { recursive: true });
  }
}

await rm(vendorRoot, { recursive: true, force: true });

/* Keep runtime map assets local so the app serves the exact versions pinned in
   package.json instead of relying on CDN URLs embedded in templates. */
await copyIntoVendor(path.join(vendorRoot, "leaflet"), [
  [path.join(root, "node_modules", "leaflet", "dist", "leaflet.css"), "leaflet.css"],
  [path.join(root, "node_modules", "leaflet", "dist", "leaflet.js"), "leaflet.js"],
  [path.join(root, "node_modules", "leaflet", "dist", "images"), "images"],
]);

await copyIntoVendor(path.join(vendorRoot, "leaflet.fullscreen"), [
  [
    path.join(root, "node_modules", "leaflet.fullscreen", "dist", "Control.FullScreen.css"),
    "Control.FullScreen.css",
  ],
  [
    path.join(root, "node_modules", "leaflet.fullscreen", "dist", "Control.FullScreen.umd.js"),
    "Control.FullScreen.umd.js",
  ],
]);

await copyIntoVendor(path.join(vendorRoot, "leaflet-ant-path"), [
  [
    path.join(root, "node_modules", "leaflet-ant-path", "dist", "leaflet-ant-path.js"),
    "leaflet-ant-path.js",
  ],
]);

await copyIntoVendor(path.join(vendorRoot, "frappe-gantt"), [
  [
    path.join(root, "node_modules", "frappe-gantt", "dist", "frappe-gantt.css"),
    "frappe-gantt.css",
  ],
  [
    path.join(root, "node_modules", "frappe-gantt", "dist", "frappe-gantt.umd.js"),
    "frappe-gantt.umd.js",
  ],
]);

await copyIntoVendor(path.join(vendorRoot, "photoswipe"), [
  [
    path.join(root, "node_modules", "photoswipe", "dist", "photoswipe.css"),
    "photoswipe.css",
  ],
  [
    path.join(root, "node_modules", "photoswipe", "dist", "photoswipe.esm.min.js"),
    "photoswipe.esm.min.js",
  ],
  [
    path.join(
      root,
      "node_modules",
      "photoswipe",
      "dist",
      "photoswipe-lightbox.esm.min.js",
    ),
    "photoswipe-lightbox.esm.min.js",
  ],
]);
