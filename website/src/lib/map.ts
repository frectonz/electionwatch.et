// Shared MapLibre helpers for the two station maps (PollingStationMap and
// PartyFootprintMap). Both render NEBE polling stations as GPU circle dots over
// the same Carto basemap; only their colouring, popups, and toggle semantics
// differ. maplibre-gl is bundled from npm (not a CDN), so it is fully typed.
import {
  Map as MlMap,
  NavigationControl,
  type StyleSpecification,
  type CircleLayerSpecification,
  type ExpressionSpecification,
} from "maplibre-gl";

// Wire-format types live in a dependency-free module so the Node build script
// can share them; re-exported here for the map components.
export type { ConstituencyRef, MapPoint, MapData } from "./map-data";

/** Circle paint shared by both maps; callers add their own `circle-color`. */
export const CIRCLE_PAINT_BASE: CircleLayerSpecification["paint"] = {
  "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 2.2, 12, 5],
  "circle-stroke-color": "#fff",
  "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 5, 0, 9, 1],
  "circle-opacity": 0.85,
};

/** Carto-tiled map centred on Ethiopia, scroll-zoom off until clicked. */
export function createMap(containerId: string): MlMap {
  const style: StyleSpecification = {
    version: 8,
    sources: {
      carto: {
        type: "raster",
        tiles: [
          "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
          "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        ],
        tileSize: 256,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      },
    },
    layers: [{ id: "carto", type: "raster", source: "carto" }],
  };
  const map = new MlMap({
    container: containerId,
    style,
    center: [39.5, 9.2],
    zoom: 5,
    scrollZoom: false, // don't hijack page scroll; enabled on click below
  });
  map.addControl(new NavigationControl(), "top-right");
  return map;
}

/** Enable scroll-zoom only after a click, and hide the "click to zoom" hint;
 *  disable again on mouse-leave. Returns the hint element. */
export function initScrollZoom(
  map: MlMap,
  container: HTMLElement,
  containerId: string,
): HTMLElement {
  const hint = document.getElementById(containerId + "-hint")!;
  container.addEventListener("click", () => {
    map.scrollZoom.enable();
    hint.style.opacity = "0";
  });
  container.addEventListener("mouseleave", () => {
    map.scrollZoom.disable();
    hint.style.opacity = "1";
  });
  return hint;
}

/** Wire the two-button mode toggle: owns the active/inactive class swap and
 *  calls `onChange(mode)` for the per-map semantics. Returns the bound setter
 *  so callers can pick the initial mode (or rely on server-rendered classes). */
export function wireModeToggle(
  containerId: string,
  onChange: (mode: string) => void,
): (mode: string) => void {
  const btns = [
    ...document
      .getElementById(containerId + "-mode")!
      .querySelectorAll<HTMLButtonElement>("button"),
  ];
  const setMode = (mode: string) => {
    onChange(mode);
    btns.forEach((b) => {
      const active = b.dataset.mode === mode;
      b.classList.toggle("bg-ew-shell", active);
      b.classList.toggle("text-white", active);
      b.classList.toggle("bg-ew-card", !active);
      b.classList.toggle("text-ew-text-dim", !active);
      // Drop the hover colour on the active button so its white text doesn't
      // turn navy-on-navy when hovered.
      b.classList.toggle("hover:text-ew-shell", !active);
    });
  };
  btns.forEach((b) =>
    b.addEventListener("click", () => setMode(b.dataset.mode!)),
  );
  return setMode;
}

/** Pointer cursor while hovering a layer's features. */
export function wireCursor(map: MlMap, layerId: string): void {
  map.on("mouseenter", layerId, () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", layerId, () => {
    map.getCanvas().style.cursor = "";
  });
}

/** A "match this categorical property, else fallback" colour expression. */
export function matchColor(
  prop: string,
  on: string,
  onColor: string,
  fallback: string,
): ExpressionSpecification {
  return ["case", ["==", ["get", prop], on], onColor, fallback];
}

/** Escape a string for safe interpolation into popup HTML. */
export function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}
