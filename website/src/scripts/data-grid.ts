// Progressive enhancement for <DataGrid>. Every grid renders its rows server-
// side; this adds client-side search, per-column enum filters, and sortable
// columns by reading the data-* attributes the component emits. Column state is
// addressed by column index: each row carries data-s{i} (sort value) and
// data-c{i} (filter value), plus a combined data-search string.
type Dir = "asc" | "desc";

export function initDataGrids() {
  document.querySelectorAll<HTMLElement>("[data-grid]").forEach((grid) => {
    if (grid.dataset.gridReady === "1") return; // enhance once
    grid.dataset.gridReady = "1";
    const search = grid.querySelector<HTMLInputElement>("[data-search]");
    const filters = [
      ...grid.querySelectorAll<HTMLSelectElement>("[data-filter]"),
    ];
    const sortSel = grid.querySelector<HTMLSelectElement>("[data-sort-select]");
    const rowsWrap = grid.querySelector<HTMLElement>("[data-rows]");
    if (!rowsWrap) return;
    const rows = [...rowsWrap.children] as HTMLElement[];
    const total = rows.length;
    const countEl = grid.querySelector<HTMLElement>("[data-count]");
    const emptyEl = grid.querySelector<HTMLElement>("[data-empty]");
    const headers = [
      ...grid.querySelectorAll<HTMLButtonElement>("[data-sort]"),
    ];

    let sortKey = grid.dataset.defaultSort ?? "";
    let sortDir: Dir = (grid.dataset.defaultDir as Dir) ?? "asc";

    const apply = () => {
      const q = (search?.value ?? "").trim().toLowerCase();

      if (sortKey !== "") {
        const sorted = [...rows].sort((a, b) => {
          const av = a.dataset["s" + sortKey] ?? "";
          const bv = b.dataset["s" + sortKey] ?? "";
          const cmp = av.localeCompare(bv, undefined, {
            numeric: true,
            sensitivity: "base",
          });
          return sortDir === "asc" ? cmp : -cmp;
        });
        sorted.forEach((r) => rowsWrap.appendChild(r));
      }

      let shown = 0;
      for (const r of rows) {
        let ok = !q || (r.dataset.search ?? "").includes(q);
        if (ok) {
          for (const f of filters) {
            if (f.value && r.dataset["c" + f.dataset.filter] !== f.value) {
              ok = false;
              break;
            }
          }
        }
        r.style.display = ok ? "" : "none";
        if (ok) shown++;
      }

      if (countEl) countEl.textContent = `${shown} of ${total}`;
      if (emptyEl) emptyEl.classList.toggle("hidden", shown !== 0);

      for (const h of headers) {
        const arrow = h.querySelector<HTMLElement>("[data-arrow]");
        const active = h.dataset.sort === sortKey;
        if (arrow) {
          arrow.style.opacity = active ? "1" : "0";
          arrow.textContent = active ? (sortDir === "asc" ? "↑" : "↓") : "";
        }
      }
    };

    const setSort = (k: string) => {
      if (sortKey === k) sortDir = sortDir === "asc" ? "desc" : "asc";
      else {
        sortKey = k;
        sortDir = "asc";
      }
      if (sortSel) sortSel.value = sortKey;
      apply();
    };

    search?.addEventListener("input", apply);
    filters.forEach((f) => f.addEventListener("change", apply));
    sortSel?.addEventListener("change", () => setSort(sortSel.value));
    headers.forEach((h) =>
      h.addEventListener("click", () => setSort(h.dataset.sort!)),
    );

    apply();
  });
}
