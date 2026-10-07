import {
  Map as MlMap,
  NavigationControl,
  GeolocateControl,
  type CircleLayerSpecification,
  type ExpressionSpecification,
} from "maplibre-gl";

export type { ConstituencyRef, MapPoint, MapData } from "./map-data";

export const CIRCLE_PAINT_BASE: CircleLayerSpecification["paint"] = {
  "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 2.2, 12, 5],
  "circle-stroke-color": "#fff",
  "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 5, 0, 9, 1],
  "circle-opacity": 0.85,
};

export function createMap(containerId: string): MlMap {
  const map = new MlMap({
    container: containerId,
    center: [39.5, 9.2],
    zoom: 5,
    scrollZoom: false,
  });
  map.setStyle("https://tiles.openfreemap.org/styles/positron", {
    transformStyle: (_, style) => ({
      ...style,
      sources: Object.fromEntries(
        Object.entries(style.sources).map(([id, source]) => [
          id,
          {
            ...source,
            attribution:
              '&copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          },
        ]),
      ),
    }),
  });
  map.addControl(new NavigationControl(), "top-right");
  map.addControl(
    new GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: true,
      showUserLocation: true,
    }),
    "top-right",
  );
  return map;
}

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
      b.classList.toggle("hover:text-ew-shell", !active);
    });
  };
  btns.forEach((b) =>
    b.addEventListener("click", () => setMode(b.dataset.mode!)),
  );
  return setMode;
}

export function wireCursor(map: MlMap, layerId: string): void {
  map.on("mouseenter", layerId, () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", layerId, () => {
    map.getCanvas().style.cursor = "";
  });
}

export function matchColor(
  prop: string,
  on: string,
  onColor: string,
  fallback: string,
): ExpressionSpecification {
  return ["case", ["==", ["get", prop], on], onColor, fallback];
}

export function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}
