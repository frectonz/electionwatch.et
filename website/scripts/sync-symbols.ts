import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(__dirname, "../../symbols/data/images");
const DEST = path.resolve(__dirname, "../public/symbols");

export function syncSymbols() {
  if (!fs.existsSync(SRC)) {
    console.warn(`[symbols] source dir not found, skipping: ${SRC}`);
    return;
  }
  fs.mkdirSync(DEST, { recursive: true });
  const files = fs.readdirSync(SRC).filter((f) => f.endsWith(".png"));
  for (const file of files) {
    fs.copyFileSync(path.join(SRC, file), path.join(DEST, file));
  }
  console.log(`[symbols] synced ${files.length} images to public/symbols/`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  syncSymbols();
}
