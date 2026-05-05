/* Comic Frontier 22 catalog search — vanilla JS, no dependencies. */

const CIRCLE_URL = (id) => `https://catalog.comifuro.net/circle/${id}`;

const els = {
  fandom: document.getElementById("q-fandom"),
  name: document.getElementById("q-name"),
  code: document.getElementById("q-code"),
  reset: document.getElementById("reset-btn"),
  status: document.getElementById("status"),
  tbody: document.querySelector("#results tbody"),
  thead: document.querySelector("#results thead"),
};

let CIRCLES = [];
let filtered = [];
let sortCol = "code";
let sortDesc = false;

/* --- normalization & search -------------------------------------------- */

const WS_RE = /\s+/g;

/** Lowercase, replace `@` with `a`, strip ALL whitespace.
 *  Mirrors the desktop app so behaviour is identical. */
function normalize(s) {
  if (!s) return "";
  return String(s).replace(/@/g, "a").toLowerCase().replace(WS_RE, "");
}

function search(circles, fandomQ, nameQ, codeQ) {
  const f = normalize(fandomQ);
  const n = normalize(nameQ);
  const c = normalize(codeQ);
  if (!f && !n && !c) return circles.slice();

  const out = [];
  for (const x of circles) {
    if (f && !x._nf.includes(f) && !x._no.includes(f)) continue;
    if (n && !x._nn.includes(n)) continue;
    if (c && !x._nc.includes(c)) continue;
    out.push(x);
  }
  return out;
}

/* --- rendering --------------------------------------------------------- */

function combinedFandom(c) {
  if (c.other && c.other !== "-") return `${c.fandom} / ${c.other}`;
  return c.fandom;
}

function compareBy(key) {
  return (a, b) => {
    let va, vb;
    if (key === "name") { va = a.name; vb = b.name; }
    else if (key === "code") { va = a.code; vb = b.code; }
    else { va = combinedFandom(a); vb = combinedFandom(b); }
    va = (va || "").toLowerCase();
    vb = (vb || "").toLowerCase();
    if (va < vb) return -1;
    if (va > vb) return 1;
    return 0;
  };
}

function applySort() {
  const cmp = compareBy(sortCol);
  filtered.sort(cmp);
  if (sortDesc) filtered.reverse();
}

function render() {
  applySort();

  // Update sort indicators
  for (const th of els.thead.querySelectorAll("th.sortable")) {
    const k = th.dataset.sort;
    th.classList.remove("sort-asc", "sort-desc");
    if (k === sortCol) {
      th.classList.add(sortDesc ? "sort-desc" : "sort-asc");
    }
  }

  // Status
  const total = CIRCLES.length;
  els.status.textContent = `${filtered.length} of ${total} circles match.`;

  // Table body — use DocumentFragment for speed.
  els.tbody.replaceChildren();
  if (filtered.length === 0) {
    const tr = document.createElement("tr");
    tr.className = "no-results";
    const td = document.createElement("td");
    td.colSpan = 3;
    td.textContent = "Tidak ada circle yang cocok dengan pencarian.";
    tr.appendChild(td);
    els.tbody.appendChild(tr);
    return;
  }

  const frag = document.createDocumentFragment();
  for (const c of filtered) {
    const tr = document.createElement("tr");
    tr.dataset.id = c.id;
    tr.title = `Buka ${c.name} (id ${c.id})`;

    const tdName = document.createElement("td");
    tdName.className = "name";
    tdName.textContent = c.name;

    const tdCode = document.createElement("td");
    tdCode.className = "code";
    tdCode.textContent = c.code;

    const tdFandom = document.createElement("td");
    tdFandom.className = "fandom";
    tdFandom.textContent = combinedFandom(c);

    tr.append(tdName, tdCode, tdFandom);
    frag.appendChild(tr);
  }
  els.tbody.appendChild(frag);
}

/* --- event wiring ------------------------------------------------------ */

function onQueryChanged() {
  filtered = search(CIRCLES, els.fandom.value, els.name.value, els.code.value);
  render();
  syncQueryString();
}

function onSortClick(e) {
  const th = e.target.closest("th.sortable");
  if (!th) return;
  const key = th.dataset.sort;
  if (sortCol === key) {
    sortDesc = !sortDesc;
  } else {
    sortCol = key;
    sortDesc = false;
  }
  render();
}

function onRowClick(e) {
  const tr = e.target.closest("tr[data-id]");
  if (!tr) return;
  const id = tr.dataset.id;
  // Open in new tab; respects modifier keys naturally on most browsers.
  window.open(CIRCLE_URL(id), "_blank", "noopener");
}

function onResetClick() {
  els.fandom.value = "";
  els.name.value = "";
  els.code.value = "";
  onQueryChanged();
  els.fandom.focus();
}

/* Keep the URL in sync so users can share a search. */
function syncQueryString() {
  const params = new URLSearchParams();
  if (els.fandom.value) params.set("fandom", els.fandom.value);
  if (els.name.value) params.set("name", els.name.value);
  if (els.code.value) params.set("code", els.code.value);
  const qs = params.toString();
  const url = qs ? `?${qs}` : window.location.pathname;
  history.replaceState(null, "", url);
}

function loadFromQueryString() {
  const params = new URLSearchParams(window.location.search);
  if (params.has("fandom")) els.fandom.value = params.get("fandom");
  if (params.has("name")) els.name.value = params.get("name");
  if (params.has("code")) els.code.value = params.get("code");
}

/* --- bootstrap --------------------------------------------------------- */

async function loadCatalog() {
  const t0 = performance.now();
  const resp = await fetch("circles.json", { cache: "force-cache" });
  if (!resp.ok) {
    throw new Error(`Failed to load catalog: HTTP ${resp.status}`);
  }
  const raw = await resp.json();
  // Pre-compute normalized strings once so each keystroke is O(N) string
  // includes instead of O(N) full normalization.
  for (const c of raw) {
    c._nn = normalize(c.name);
    c._nc = normalize(c.code);
    c._nf = normalize(c.fandom);
    c._no = normalize(c.other);
  }
  CIRCLES = raw;
  const ms = Math.round(performance.now() - t0);
  console.log(`Loaded ${raw.length} circles in ${ms}ms`);
}

async function init() {
  try {
    await loadCatalog();
  } catch (err) {
    els.status.textContent = `Gagal load data: ${err.message}`;
    return;
  }

  loadFromQueryString();

  els.fandom.addEventListener("input", onQueryChanged);
  els.name.addEventListener("input", onQueryChanged);
  els.code.addEventListener("input", onQueryChanged);
  els.reset.addEventListener("click", onResetClick);
  els.thead.addEventListener("click", onSortClick);
  els.tbody.addEventListener("click", onRowClick);

  onQueryChanged();
}

init();
