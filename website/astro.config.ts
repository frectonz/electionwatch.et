import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";
import icon from "astro-icon";
import AstroPWA from "@vite-pwa/astro";
import { syncSymbols } from "./scripts/sync-symbols.ts";
import { buildPollingStationPoints } from "./scripts/build-ps-points.ts";

function symbolAssets() {
  return {
    name: "symbol-assets",
    hooks: {
      "astro:config:setup": () => syncSymbols(),
    },
  };
}

function pollingStationMap() {
  return {
    name: "polling-station-map",
    hooks: {
      "astro:config:setup": () => buildPollingStationPoints(),
    },
  };
}

function pwa() {
  return AstroPWA({
    registerType: "autoUpdate",
    injectRegister: "script",
    workbox: {
      globPatterns: ["offline/index.html", "manifest.webmanifest"],
      navigateFallback: undefined,
      runtimeCaching: [
        {
          urlPattern: ({ request }) => request.mode === "navigate",
          handler: "StaleWhileRevalidate",
          options: {
            cacheName: "electionwatch-et-pages",
            precacheFallback: { fallbackURL: "/offline" },
          },
        },
        {
          urlPattern: ({ sameOrigin }) => sameOrigin,
          handler: "StaleWhileRevalidate",
          options: { cacheName: "electionwatch-et-assets" },
        },
      ],
    },
    manifest: {
      id: "/",
      name: "electionwatch.et",
      short_name: "electionwatch.et",
      description:
        "Open datasets on Ethiopia's 7th General Election: candidates, polling stations, party debates, and positions. Every record links to its source.",
      start_url: "/",
      scope: "/",
      display: "standalone",
      orientation: "portrait",
      background_color: "#1f2455",
      theme_color: "#1f2455",
      lang: "en",
      categories: ["government", "education", "reference"],
      icons: [
        {
          src: "/favicon.svg",
          type: "image/svg+xml",
          sizes: "512x512",
          purpose: "any",
        },
        {
          src: "/icon-192.png",
          type: "image/png",
          sizes: "192x192",
          purpose: "any",
        },
        {
          src: "/icon-512.png",
          type: "image/png",
          sizes: "512x512",
          purpose: "any",
        },
        {
          src: "/icon-maskable-512.png",
          type: "image/png",
          sizes: "512x512",
          purpose: "maskable",
        },
      ],
      screenshots: [
        {
          src: "/screenshots/desktop-home.png",
          sizes: "1280x800",
          type: "image/png",
          form_factor: "wide",
          label: "Home — open data for Ethiopia's 7th General Election",
        },
        {
          src: "/screenshots/desktop-map.png",
          sizes: "1280x800",
          type: "image/png",
          form_factor: "wide",
          label: "50,126 polling stations mapped across Ethiopia",
        },
        {
          src: "/screenshots/desktop-debates.png",
          sizes: "1280x800",
          type: "image/png",
          form_factor: "wide",
          label: "Every party debate, analysed question by question",
        },
        {
          src: "/screenshots/mobile-home.png",
          sizes: "780x1688",
          type: "image/png",
          form_factor: "narrow",
          label: "Home — open data for Ethiopia's 7th General Election",
        },
        {
          src: "/screenshots/mobile-candidates.png",
          sizes: "780x1688",
          type: "image/png",
          form_factor: "narrow",
          label: "10,438 candidates by region, constituency, and party",
        },
        {
          src: "/screenshots/mobile-debates.png",
          sizes: "780x1688",
          type: "image/png",
          form_factor: "narrow",
          label: "Every party debate, analysed question by question",
        },
      ],
    },
    devOptions: {
      enabled: false,
    },
  });
}

export default defineConfig({
  site: "https://electionwatch.et",
  integrations: [
    symbolAssets(),
    pollingStationMap(),
    icon(),
    sitemap({ filter: (page) => !/\/(offline|404)\/?$/.test(page) }),
    pwa(),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
