import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import type { APIRoute, GetStaticPaths } from "astro";
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { ogPages, type OgPage } from "@/lib/og-pages";

// --- Brand palette (mirrors src/styles/global.css) ---
const SHELL = "#1f2455";
const SHELL_DEEP = "#15172a";
const GOLD = "#c79a3a";
const PAPER = "#eeeff5";

// --- Fonts: read from the @fontsource packages at build time ---
const require = createRequire(import.meta.url);
function loadFont(pkgPath: string): Buffer {
  return readFileSync(require.resolve(pkgPath));
}

const instrumentSerif = loadFont(
  "@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff",
);
const loraRegular = loadFont(
  "@fontsource/lora/files/lora-latin-400-normal.woff",
);
const loraBold = loadFont("@fontsource/lora/files/lora-latin-700-normal.woff");
const notoEthiopic = loadFont(
  "@fontsource/noto-sans-ethiopic/files/noto-sans-ethiopic-ethiopic-400-normal.woff",
);

// --- Markup builder ---
function buildMarkup(page: OgPage) {
  return {
    type: "div",
    props: {
      style: {
        width: "100%",
        height: "100%",
        display: "flex",
        position: "relative",
        overflow: "hidden",
        background: `linear-gradient(135deg, ${SHELL} 0%, ${SHELL_DEEP} 100%)`,
      },
      children: [
        // Left gold accent bar
        {
          type: "div",
          props: {
            style: {
              position: "absolute",
              left: "0",
              top: "0",
              bottom: "0",
              width: "16px",
              background: GOLD,
            },
          },
        },
        // Decorative Ethiopic glyphs (ምርጫ = election)
        {
          type: "div",
          props: {
            style: {
              position: "absolute",
              top: "20px",
              right: "70px",
              fontSize: "300px",
              lineHeight: "1",
              color: GOLD,
              opacity: 0.05,
              fontFamily: "Noto Sans Ethiopic",
            },
            children: "ም",
          },
        },
        {
          type: "div",
          props: {
            style: {
              position: "absolute",
              top: "180px",
              right: "330px",
              fontSize: "200px",
              lineHeight: "1",
              color: GOLD,
              opacity: 0.04,
              fontFamily: "Noto Sans Ethiopic",
            },
            children: "ር",
          },
        },
        {
          type: "div",
          props: {
            style: {
              position: "absolute",
              bottom: "10px",
              left: "180px",
              fontSize: "240px",
              lineHeight: "1",
              color: GOLD,
              opacity: 0.04,
              fontFamily: "Noto Sans Ethiopic",
            },
            children: "ጫ",
          },
        },
        // Corner accents
        {
          type: "div",
          props: {
            style: {
              position: "absolute",
              top: "40px",
              right: "40px",
              width: "40px",
              height: "40px",
              borderTop: `3px solid ${GOLD}`,
              borderRight: `3px solid ${GOLD}`,
              opacity: 0.5,
            },
          },
        },
        {
          type: "div",
          props: {
            style: {
              position: "absolute",
              bottom: "40px",
              right: "40px",
              width: "40px",
              height: "40px",
              borderBottom: `3px solid ${GOLD}`,
              borderRight: `3px solid ${GOLD}`,
              opacity: 0.5,
            },
          },
        },
        // Main content
        {
          type: "div",
          props: {
            style: {
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              width: "100%",
              height: "100%",
              padding: "60px 70px 50px 56px",
            },
            children: [
              // Top: logo badge + wordmark
              {
                type: "div",
                props: {
                  style: {
                    display: "flex",
                    alignItems: "center",
                    gap: "14px",
                  },
                  children: [
                    {
                      type: "div",
                      props: {
                        style: {
                          width: "44px",
                          height: "44px",
                          borderRadius: "10px",
                          background: GOLD,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: "26px",
                          color: SHELL_DEEP,
                          fontFamily: "Noto Sans Ethiopic",
                          fontWeight: 700,
                        },
                        children: "ም",
                      },
                    },
                    {
                      type: "div",
                      props: {
                        style: {
                          fontSize: "30px",
                          color: GOLD,
                          fontFamily: "Instrument Serif",
                          letterSpacing: "0.02em",
                        },
                        children: "electionwatch.et",
                      },
                    },
                  ],
                },
              },
              // Center: title + description
              {
                type: "div",
                props: {
                  style: {
                    display: "flex",
                    flexDirection: "column",
                    gap: "16px",
                    maxWidth: "960px",
                  },
                  children: [
                    {
                      type: "div",
                      props: {
                        style: {
                          fontSize: page.title.length > 30 ? "52px" : "66px",
                          color: PAPER,
                          fontFamily: "Instrument Serif",
                          lineHeight: "1.12",
                        },
                        children: page.title,
                      },
                    },
                    ...(page.description
                      ? [
                          {
                            type: "div",
                            props: {
                              style: {
                                fontSize: "26px",
                                color: PAPER,
                                fontFamily: "Lora",
                                lineHeight: "1.5",
                                opacity: 0.8,
                              },
                              children: page.description,
                            },
                          },
                        ]
                      : []),
                  ],
                },
              },
              // Bottom: gold rule + tagline
              {
                type: "div",
                props: {
                  style: {
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  },
                  children: [
                    {
                      type: "div",
                      props: {
                        style: {
                          width: "100%",
                          height: "2px",
                          background: GOLD,
                          opacity: 0.4,
                        },
                      },
                    },
                    {
                      type: "div",
                      props: {
                        style: {
                          fontSize: "20px",
                          color: GOLD,
                          fontFamily: "Noto Sans Ethiopic",
                          opacity: 0.5,
                          letterSpacing: "0.15em",
                        },
                        children: "ምርጫ · Ethiopia's 7th General Election",
                      },
                    },
                  ],
                },
              },
            ],
          },
        },
      ],
    },
  };
}

// --- Render pipeline ---
async function renderOgImage(page: OgPage) {
  const svg = await satori(buildMarkup(page) as Parameters<typeof satori>[0], {
    width: 1200,
    height: 630,
    fonts: [
      {
        name: "Instrument Serif",
        data: instrumentSerif,
        weight: 400,
        style: "normal",
      },
      { name: "Lora", data: loraRegular, weight: 400, style: "normal" },
      { name: "Lora", data: loraBold, weight: 700, style: "normal" },
      {
        name: "Noto Sans Ethiopic",
        data: notoEthiopic,
        weight: 400,
        style: "normal",
      },
    ],
  });

  const resvg = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } });
  return resvg.render().asPng();
}

// --- Astro static paths + GET handler ---
export const getStaticPaths: GetStaticPaths = () =>
  Object.keys(ogPages).map((route) => ({ params: { route: `${route}.png` } }));

export const GET: APIRoute = async ({ params }) => {
  const route = (params.route as string).replace(/\.png$/, "");
  const page = ogPages[route];
  if (!page) return new Response("Not found", { status: 404 });

  const png = await renderOgImage(page);
  return new Response(png as unknown as BodyInit, {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "public, max-age=31536000, immutable",
    },
  });
};
