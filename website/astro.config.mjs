// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";
import { syncSymbols } from "./scripts/sync-symbols.ts";
import { buildPollingStationPoints } from "./scripts/build-ps-points.ts";
import { buildLlms } from "./scripts/build-llms.ts";

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

// Mirrors the source datasets into public/data/ and generates the agent entry
// points (llms.txt + manifest.json) before dev/build.
function llmsExport() {
  return {
    name: "llms-export",
    hooks: {
      "astro:config:setup": () => buildLlms(),
    },
  };
}

// https://astro.build/config
export default defineConfig({
  site: "https://electionwatch.et",
  integrations: [symbolAssets(), pollingStationMap(), llmsExport(), sitemap()],
  vite: {
    plugins: [tailwindcss()],
  },
});
