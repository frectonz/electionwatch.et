// Client-side search for the top-level /candidates page. Fetches the compact
// index emitted by src/pages/candidates-index.json.ts, then filters it in the
// browser on every keystroke or filter change and renders the top matches.

// Tuple layout, mirrored from the index endpoint.
type Row = [
  name: string,
  partyEn: string,
  partySlug: string,
  region: string,
  constituency: string,
  conSlug: string,
  body: string,
  gender: string,
  education: string,
  disability: number,
];

const MAX_RESULTS = 100;

const BODY_SHORT: Record<string, string> = { hopr: "HoPR", rc: "RC" };

// Education ordered high -> low so the filter dropdown reads top-down.
const EDU_ORDER = [
  "Doctorate",
  "Master of Law",
  "Master of Science",
  "Master of Arts",
  "Bachelor of Law",
  "Bachelor of Science",
  "Bachelor of Arts",
  "Diploma",
  "High School",
  "Middle School",
  "Primary School",
  "No Education",
];

const escapeHtml = (s: string) =>
  s.replace(
    /[&<>"']/g,
    (ch) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[ch]!,
  );

const fmt = (n: number) => n.toLocaleString("en-US");

function fillSelect(
  select: HTMLSelectElement,
  values: string[],
  label: (v: string) => string = (v) => v,
) {
  const frag = document.createDocumentFragment();
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = label(v);
    frag.appendChild(opt);
  }
  select.appendChild(frag);
}

export async function initCandidateSearch() {
  const root = document.getElementById("candidate-search");
  if (!root) return;

  const input = root.querySelector<HTMLInputElement>("[data-search]")!;
  const results = root.querySelector<HTMLElement>("#cand-results")!;
  const countEl = root.querySelector<HTMLElement>("#cand-count")!;
  const emptyEl = root.querySelector<HTMLElement>("#cand-empty")!;
  const statusEl = root.querySelector<HTMLElement>("#cand-status")!;
  const filterEls = {
    region: root.querySelector<HTMLSelectElement>('[data-filter="region"]')!,
    body: root.querySelector<HTMLSelectElement>('[data-filter="body"]')!,
    party: root.querySelector<HTMLSelectElement>('[data-filter="party"]')!,
    gender: root.querySelector<HTMLSelectElement>('[data-filter="gender"]')!,
    education: root.querySelector<HTMLSelectElement>(
      '[data-filter="education"]',
    )!,
    disability: root.querySelector<HTMLSelectElement>(
      '[data-filter="disability"]',
    )!,
  };

  let rows: Row[];
  try {
    rows = (await fetch("/data/candidates/search-index.json").then((r) =>
      r.json(),
    )) as Row[];
  } catch {
    statusEl.textContent = "Could not load the candidate list. Try refreshing.";
    return;
  }

  // Populate the dynamic dropdowns from the data.
  const uniq = (i: number) =>
    [...new Set(rows.map((r) => r[i] as string))].filter(Boolean);
  fillSelect(
    filterEls.region,
    uniq(3).sort((a, b) => a.localeCompare(b)),
  );
  fillSelect(
    filterEls.party,
    uniq(1).sort((a, b) => a.localeCompare(b)),
  );
  fillSelect(
    filterEls.gender,
    uniq(7).sort((a, b) => a.localeCompare(b)),
  );
  fillSelect(
    filterEls.education,
    uniq(8).sort((a, b) => {
      const ai = EDU_ORDER.indexOf(a);
      const bi = EDU_ORDER.indexOf(b);
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
    }),
  );

  const lower = rows.map((r) => `${r[0]} ${r[1]}`.toLowerCase());

  const renderRow = (r: Row) => {
    const partyCell = r[2]
      ? `<a href="/data/candidates/party/${escapeHtml(
          r[2],
        )}" class="text-ew-shell hover:text-ew-gold transition-colors">${escapeHtml(
          r[1],
        )}</a>`
      : escapeHtml(r[1]);
    const conCell = r[5]
      ? `<a href="/data/candidates/c/${escapeHtml(
          r[5],
        )}" class="hover:text-ew-shell transition-colors">${escapeHtml(
          r[4],
        )}</a>`
      : escapeHtml(r[4]);
    const disability = r[9]
      ? '<span class="text-[10px] uppercase tracking-wider text-ew-gold-deep bg-ew-gold/15 rounded px-1.5 py-0.5">Disability</span>'
      : "";
    return `<div class="px-4 py-3">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-ew-text font-medium">${escapeHtml(r[0])}</span>
        <span class="text-[10px] uppercase tracking-wider text-ew-shell bg-ew-shell/10 rounded px-1.5 py-0.5">${
          BODY_SHORT[r[6]] ?? r[6]
        }</span>
        ${disability}
      </div>
      <div class="mt-1 text-sm text-ew-text-muted flex flex-wrap gap-x-2 gap-y-0.5">
        <span>${partyCell}</span>
        <span aria-hidden="true">&middot;</span>
        <span>${conCell}</span>
        <span aria-hidden="true">&middot;</span>
        <span>${escapeHtml(r[3])}</span>
        <span aria-hidden="true">&middot;</span>
        <span>${escapeHtml(r[7])}</span>
        ${
          r[8]
            ? `<span aria-hidden="true">&middot;</span><span>${escapeHtml(
                r[8],
              )}</span>`
            : ""
        }
      </div>
    </div>`;
  };

  const render = () => {
    const q = input.value.trim().toLowerCase();
    const f = {
      region: filterEls.region.value,
      body: filterEls.body.value,
      party: filterEls.party.value,
      gender: filterEls.gender.value,
      education: filterEls.education.value,
      disability: filterEls.disability.value,
    };

    const matches: Row[] = [];
    let total = 0;
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      if (q && !lower[i].includes(q)) continue;
      if (f.region && r[3] !== f.region) continue;
      if (f.body && r[6] !== f.body) continue;
      if (f.party && r[1] !== f.party) continue;
      if (f.gender && r[7] !== f.gender) continue;
      if (f.education && r[8] !== f.education) continue;
      if (f.disability && String(r[9]) !== f.disability) continue;
      total++;
      if (matches.length < MAX_RESULTS) matches.push(r);
    }

    if (total === 0) {
      results.innerHTML = "";
      emptyEl.classList.remove("hidden");
      countEl.textContent = "No matches";
      return;
    }

    emptyEl.classList.add("hidden");
    results.innerHTML = matches.map(renderRow).join("");
    countEl.textContent =
      total > matches.length
        ? `Showing ${fmt(matches.length)} of ${fmt(total)} matches`
        : `${fmt(total)} ${total === 1 ? "candidate" : "candidates"}`;
  };

  let raf = 0;
  const schedule = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(render);
  };

  input.addEventListener("input", schedule);
  for (const el of Object.values(filterEls))
    el.addEventListener("change", render);

  statusEl.classList.add("hidden");
  render();
}
