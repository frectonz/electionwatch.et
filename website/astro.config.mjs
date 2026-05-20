// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";
import { syncSymbols } from "./scripts/sync-symbols.mjs";
import { buildPollingStationPoints } from "./scripts/build-ps-points.mjs";

// Copies party symbol images into public/ before dev and build.
function symbolAssets() {
  return {
    name: "symbol-assets",
    hooks: {
      "astro:config:setup": () => syncSymbols(),
    },
  };
}

// Builds the compact polling-station map dataset into public/ before dev/build.
function pollingStationMap() {
  return {
    name: "polling-station-map",
    hooks: {
      "astro:config:setup": () => buildPollingStationPoints(),
    },
  };
}

// https://astro.build/config
export default defineConfig({
  site: "https://electionwatch.et",
  integrations: [symbolAssets(), pollingStationMap(), sitemap()],
  vite: {
    plugins: [tailwindcss()],
  },
});
