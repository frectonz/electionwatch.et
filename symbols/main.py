import io
import json
from pathlib import Path

import fitz
from PIL import Image

PDF_PATH = Path("symbols.pdf")
DATA_DIR = Path("data")
OUT_JSON = DATA_DIR / "symbols.json"
IMG_DIR = DATA_DIR / "images"
CATALOG_DIR = Path("images")  # high-quality stock symbols, named by subject
PARTIES_JSON = Path("../transcripts/data/parties.json")

# Parties whose symbol was confidently matched to a catalogue image (verified
# visually against the PDF render). These use the high-quality catalogue file;
# every other party falls back to the symbol cropped from the PDF.
CATALOG_MATCHES = {
    "welene-peoples-democratic-party": "Oil lamp.jpg",
    "wolaita-peoples-liberation-movement": "Bee.jpg",
    "wolaita-peoples-democratic-front": "Lion 1.jpg",
    "renaissance-party": "Mobile phone 1.jpg",
    "wollo-peoples-democratic-party": "lock.jpg",
    "democratic-unity-of-tigray": "Joigned Hands.jpg",
    "prosperity-party": "Wheat.jpg",
    "tinsae-seba-enderta-party": "thumbnail_bread symbol.png",
    "one-ethiopia-democratic-party": "Palm tree.jpg",
}

# Column indices in the extracted table.
COL_NUMBER = 0
COL_PARTY = 1
COL_SYMBOL_CELL = 2  # the cell that holds the symbol image
COL_SYMBOL_NAME = 3  # the symbol's name, in Amharic

RENDER_DPI = 300

# Points to inset the symbol cell on each side, cropping out the table's
# cell border lines so they don't show up as a box around the symbol.
CELL_INSET = 3

# When centering a PDF-cropped symbol on a square canvas, the blank margin to
# leave around it as a fraction of the symbol's longer side.
SYMBOL_MARGIN = 0.08

# Treat pixels lighter than this (0-255) as background when finding the symbol.
CONTENT_THRESHOLD = 245

# Amharic party name -> English slug. Slugs for the 24 parties already in
# transcripts/data/parties.json are reused verbatim; the rest follow the same
# kebab-case English convention.
SLUGS = {
    "የሲዳማ ሕዝብ አንድነት ዴሞክራሲያዊ ድርጅት": "sidama-peoples-unity-democratic-organization",
    "የመላው ሲዳማ ህዝብ ዴሞክራሲያዊ አንድነት ፓርቲ": "all-sidama-peoples-democratic-unity-party",
    "የሲዳማ አንድነት ፓርቲ": "sidama-unity-party",
    "የቁጫ ሕዝብ ዴሞክራሲያዊ ፓርቲ": "kucha-peoples-democratic-party",
    "የኢትዮጵያ ብሔራዊ አንድነት ፓርቲ": "ethiopian-national-unity-party",
    "የኦሮሞ ነፃነት ግንባር": "oromo-liberation-front",
    "ኅብር ኢትዮጵያ ዴሞክራሲያዊ ፓርቲ": "hibir-ethiopia-democratic-party",
    "የዎላይታ ብሔራዊ ንቅናቄ": "wolaita-national-movement",
    "የወለኔ ሕዝብ ዴሞክራሲያዊ ፓርቲ": "welene-peoples-democratic-party",
    "የኢትዮጵያ ሶሻል ዴሞክራቲክ ፓርቲ": "ethiopian-social-democratic-party",
    "ራያ ራዩማ ዴሞክራሲያዊ ፓርቲ": "raya-rayuma-democratic-party",
    "አርጎባ ህዝብ ዴሞክራሲያዊ ድርጅት": "argoba-peoples-democratic-organization",
    "የዎላይታ ሕዝቦች ነፃነት ንቅናቄ": "wolaita-peoples-liberation-movement",
    "የዎላይታ ሕዝብ ዴሞክራሲያዊ ግንባር": "wolaita-peoples-democratic-front",
    "የቤኒሻንጉል ሕዝብ ነፃነት ንቅናቄ": "benishangul-peoples-liberation-movement",
    "ባልደራስ ለእውነተኛ ዴሞክራሲ": "balderas-for-true-democracy-party",
    "ህዳሴ ፓርቲ": "renaissance-party",
    "የወሎ ህዝቦች ዴሞክራሲያዊ ፓርቲ": "wollo-peoples-democratic-party",
    "የኢትዮጵያ ዴሞክራቲክ ኅብረት": "ethiopian-democratic-union",
    "ትብብር ለኢትዮጵያ አንድነት": "cooperation-for-ethiopian-unity-party",
    "የጌዴኦ ሕዝብ ዴሞክራሲያዊ ድርጅት": "gedeo-peoples-democratic-organization",
    "አዲስ ትውልድ ፓርቲ": "new-generation-party",
    "የዶንጋ ህዝብ ዴሞክራሲያዊ ድርጅት": "donga-peoples-democratic-organization",
    "ሱማሌ ፌደራሊስት ፓርቲ": "somali-federalist-party",
    "የቅማንት ዲሞክራሲያዊ ፓርቲ": "qimant-democratic-party",
    "የኩሽ ህዝቦች ብሔራዊ ንቅናቄ": "kush-peoples-national-movement-party",
    "የምዕራብ ሶማሌ ዴሞክራሲ ፓርቲ": "western-somali-democratic-party",
    "የአርጎባ አንድነት ጀበርቲ": "argoba-unity-jeberti",
    "የጉሙዝ ሕዝብ ዴሞክራሲያዊ ንቅናቄ": "gumuz-peoples-democratic-movement",
    "ነፃነትና እኩልነት ፓርቲ": "freedom-and-equality-party",
    "የአማራ ዴሞክራሲያዊ ኃይል ንቅናቄ": "amhara-democratic-force-movement",
    "የአፋር ህዝብ ፓርቲ": "afar-peoples-party",
    "የአፋር ነጻ አውጭ ግንባር ፓርቲ": "afar-liberation-front-party",
    "ጎጎት ለጉራጌ አንድነት እና ፍትህ ፓርቲ": "gogot-for-gurage-unity-and-justice-party",
    "ዲሞክራሲያዊ ስምረት ትግራይ": "democratic-unity-of-tigray",
    "የኢትዮጵያ ዜጎች ለማኅበራዊ ፍትህ ፓርቲ": "ethiopian-citizens-for-social-justice",
    "እናት ፓርቲ": "enat-party",
    "የአማራ ብሔራዊ ንቅናቄ": "national-movement-of-amhara",
    "ሰላም ለኢትዮጵያ ጥምረት": "peace-for-ethiopia-coalition",
    "የኢትዮጵያ ፌዴራላዊ ዴሞክራሲያዊ አንድነት መድረክ": "ethiopian-federal-democratic-unity-forum",
    "አንድ ኢትዮጵያ ዴሞክራሲያዊ ፓርቲ": "one-ethiopia-democratic-party",
    "ብልጽግና ፓርቲ": "prosperity-party",
    "ኅብረት ለዲሞክራሲ እና ለነፃነት ፓርቲ": "union-for-democracy-and-freedom-party",
    "የኦጋዴን ብሔራዊ ነፃነት ግንባር": "ogaden-national-liberation-front",
    "ትንሳኤ ሰብዓ እንደርታ ፓርቲ": "tinsae-seba-enderta-party",
    "የጋምቤላ ሕዝቦች ነፃነት ንቅናቄ": "gambela-peoples-liberation-movement",
    "የሐረሪ ዲሞክራሲያዊ ድርጅት": "harari-democratic-organization",
    "ትንሳኤ ስርዓት ቃንጪ ሃቂ": "tinsae-sirat-kanchi-haqi",
}


def clean(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def slug_for(party_name: str) -> str:
    slug = SLUGS.get(party_name)
    if not slug:
        raise KeyError(f"No slug registered for party '{party_name}'")
    return slug


def center_on_square(img: Image.Image) -> Image.Image:
    """Crop to the symbol's content bounds, then center it on a white square."""
    img = img.convert("RGB")
    mask = img.convert("L").point(lambda p: 255 if p < CONTENT_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox:
        img = img.crop(bbox)

    w, h = img.size
    side = max(w, h)
    margin = round(side * SYMBOL_MARGIN)
    canvas_side = side + 2 * margin
    canvas = Image.new("RGB", (canvas_side, canvas_side), (255, 255, 255))
    canvas.paste(img, ((canvas_side - w) // 2, (canvas_side - h) // 2))
    return canvas


def render_cell(page: fitz.Page, cell: tuple) -> Image.Image:
    """Render a table cell from the PDF, inset to drop its border lines."""
    clip = fitz.Rect(cell) + (CELL_INSET, CELL_INSET, -CELL_INSET, -CELL_INSET)
    pix = page.get_pixmap(clip=clip, dpi=RENDER_DPI)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def save_symbol(slug: str, page: fitz.Page, cell: tuple):
    catalog_name = CATALOG_MATCHES.get(slug)
    if catalog_name and (CATALOG_DIR / catalog_name).exists():
        # Use the high-quality catalogue image as-is (already centered/square).
        Image.open(CATALOG_DIR / catalog_name).convert("RGB").save(
            IMG_DIR / f"{slug}.png"
        )
    else:
        # Fall back to the symbol cropped from the PDF, centered to match.
        center_on_square(render_cell(page, cell)).save(IMG_DIR / f"{slug}.png")


def extract(doc: fitz.Document) -> list[dict]:
    rows = []
    for page in doc:
        for table in page.find_tables().tables:
            # `extract()` gives clean, row-aligned text; `rows` gives cell bboxes.
            for values, row in zip(table.extract(), table.rows):
                number = clean(values[COL_NUMBER])
                if not number.isdigit():
                    continue

                slug = slug_for(clean(values[COL_PARTY]))
                symbol_name = clean(values[COL_SYMBOL_NAME])
                save_symbol(slug, page, row.cells[COL_SYMBOL_CELL])

                rows.append((int(number), slug, symbol_name))

    rows.sort()
    return [
        {"slug": slug, "symbol_name": symbol_name, "image": f"{slug}.png"}
        for _, slug, symbol_name in rows
    ]


def check_registry(parties: list[dict]):
    if not PARTIES_JSON.exists():
        return
    registry = set(json.loads(PARTIES_JSON.read_text(encoding="utf-8")).keys())
    slugs = {p["slug"] for p in parties}
    print(f"Reused {len(slugs & registry)}/{len(registry)} slugs from parties.json.")
    missing = registry - slugs
    if missing:
        print(f"WARNING: registry slugs not matched: {sorted(missing)}")


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading {PDF_PATH}...")
    doc = fitz.open(PDF_PATH)
    parties = extract(doc)
    doc.close()

    OUT_JSON.write_text(
        json.dumps(parties, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(parties)} parties to {OUT_JSON} and symbols to {IMG_DIR}/.")
    check_registry(parties)


if __name__ == "__main__":
    main()
