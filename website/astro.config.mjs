// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";
import { syncSymbols } from "./scripts/sync-symbols.mjs";

// Copies party symbol images into public/ before dev and build.
function symbolAssets() {
  return {
    name: "symbol-assets",
    hooks: {
      "astro:config:setup": () => syncSymbols(),
    },
  };
}

// https://astro.build/config
export default defineConfig({
  site: "https://electionwatch.et",
  integrations: [symbolAssets(), sitemap()],
  vite: {
    plugins: [tailwindcss()],
  },
});
