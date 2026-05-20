import json
from pathlib import Path

import fitz

PDF_PATH = Path("symbols.pdf")
DATA_DIR = Path("data")
OUT_JSON = DATA_DIR / "symbols.json"
IMG_DIR = DATA_DIR / "images"
PARTIES_JSON = Path("../transcripts/data/parties.json")

# Column indices in the extracted table.
COL_NUMBER = 0
COL_PARTY = 1
COL_SYMBOL_CELL = 2  # the cell that holds the symbol image

RENDER_DPI = 300

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

                # Render the symbol cell as a standalone image named by slug.
                clip = fitz.Rect(row.cells[COL_SYMBOL_CELL])
                page.get_pixmap(clip=clip, dpi=RENDER_DPI).save(IMG_DIR / f"{slug}.png")

                rows.append((int(number), slug))

    rows.sort()
    return [{"slug": slug, "image": f"{slug}.png"} for _, slug in rows]


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
