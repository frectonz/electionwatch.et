import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEST = path.resolve(__dirname, "../public");

const SHELL = "#1f2455";
const GOLD = "#c79a3a";

interface IconSpec {
  file: string;
  size: number;
  radius: number;
  safe?: boolean;
}

const ICONS: IconSpec[] = [
  { file: "favicon-16x16.png", size: 16, radius: 0.2 },
  { file: "favicon-32x32.png", size: 32, radius: 0.2 },
  { file: "favicon-96x96.png", size: 96, radius: 0.2 },
  { file: "apple-touch-icon.png", size: 180, radius: 0 },
  { file: "icon-192.png", size: 192, radius: 0.2 },
  { file: "icon-512.png", size: 512, radius: 0.2 },
  { file: "icon-maskable-512.png", size: 512, radius: 0, safe: true },
];

const FONT_URL =
  "https://cdn.jsdelivr.net/fontsource/fonts/noto-sans-ethiopic@latest/ethiopic-700-normal.ttf";

function buildMarkup(spec: IconSpec) {
  const glyphFraction = spec.safe ? 0.42 : 0.62;
  return {
    type: "div",
    props: {
      style: {
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: SHELL,
        borderRadius: `${Math.round(spec.size * spec.radius)}px`,
        color: GOLD,
        fontFamily: "Noto Sans Ethiopic",
        fontWeight: 700,
        fontSize: `${Math.round(spec.size * glyphFraction)}px`,
        lineHeight: 1,
        paddingTop: `${Math.round(spec.size * 0.04)}px`,
      },
      children: "ም",
    },
  };
}

export async function buildIcons() {
  const fontData = await (await fetch(FONT_URL)).arrayBuffer();

  fs.mkdirSync(DEST, { recursive: true });

  for (const spec of ICONS) {
    const svg = await satori(
      buildMarkup(spec) as Parameters<typeof satori>[0],
      {
        width: spec.size,
        height: spec.size,
        fonts: [
          {
            name: "Noto Sans Ethiopic",
            data: fontData,
            weight: 700,
            style: "normal",
          },
        ],
      },
    );
    const png = new Resvg(svg, {
      fitTo: { mode: "width", value: spec.size },
    })
      .render()
      .asPng();
    fs.writeFileSync(path.join(DEST, spec.file), png);
  }

  console.log(`[icons] generated ${ICONS.length} icons in public/`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  buildIcons();
}
