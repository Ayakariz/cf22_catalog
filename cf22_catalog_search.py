"""Comic Frontier 22 catalog search.

A small Tkinter GUI that fetches the CF22 catalog once, then lets the user
search by Fandom, Circle Name, and Circle Code using strict substring matching.
Results appear in a table. Click on column headers to sort ASC/DESC.
Right-clicking a row opens that circle's page in the default browser.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tkinter as tk
import urllib.request
import webbrowser
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Any

CATALOG_URL = "https://catalog.comifuro.net/catalog"
CIRCLE_URL_TEMPLATE = "https://catalog.comifuro.net/circle/{id}"
CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "catalog_cache.json"
)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class Circle:
    id: int
    name: str
    circle_code: str
    fandom: str
    other_fandom: str

    @property
    def combined_fandom(self) -> str:
        if self.other_fandom and self.other_fandom not in ("-", ""):
            return f"{self.fandom} / {self.other_fandom}"
        return self.fandom


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_initial_state(html: str) -> dict[str, Any]:
    marker = "window.__INITIAL_STATE__="
    idx = html.find(marker)
    if idx == -1:
        raise RuntimeError("Could not locate __INITIAL_STATE__ in catalog HTML.")
    start = idx + len(marker)
    depth = 0
    in_str = False
    esc = False
    i = start
    while i < len(html):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(html[start : i + 1])
        i += 1
    raise RuntimeError("Could not parse __INITIAL_STATE__ JSON (unbalanced braces).")


def load_circles(force_refresh: bool = False) -> list[Circle]:
    """Load the full CF22 circle list. Cached to disk after first fetch."""
    if not force_refresh and os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            raw = None
        if raw:
            return [_to_circle(c) for c in raw]

    html = _fetch_html(CATALOG_URL)
    state = _extract_initial_state(html)
    raw_list = state.get("circle", {}).get("allCircle", [])
    if not raw_list:
        raise RuntimeError("Catalog returned no circles.")
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(raw_list, f)
    return [_to_circle(c) for c in raw_list]


def _to_circle(data: dict[str, Any]) -> Circle:
    return Circle(
        id=int(data.get("id", 0)),
        name=(data.get("name") or "").strip(),
        circle_code=(data.get("circle_code") or "").strip(),
        fandom=(data.get("fandom") or "").strip(),
        other_fandom=(data.get("other_fandom") or "").strip(),
    )


# ---------- exact substring matching ----------

_ws_re = re.compile(r"\s+")


def _normalize(s: str) -> str:
    # Ubah @ menjadi 'a'
    s = s.replace("@", "a")
    # Hapus SELURUH spasi agar "uma musume" dan "umamusume" dianggap sama
    return _ws_re.sub("", s.strip().lower())


def search_circles(
    circles: list[Circle],
    fandom_q: str,
    name_q: str,
    code_q: str,
) -> list[Circle]:
    """Return circles that exactly contain the search query as a substring."""
    fandom_q = _normalize(fandom_q)
    name_q = _normalize(name_q)
    code_q = _normalize(code_q)

    if not any([fandom_q, name_q, code_q]):
        return list(circles) 

    results: list[Circle] = []
    for c in circles:
        match = True
        
        # Cek Fandom
        if fandom_q:
            f_target = _normalize(c.fandom)
            o_target = _normalize(c.other_fandom)
            if fandom_q not in f_target and fandom_q not in o_target:
                match = False
                
        # Cek Nama Circle
        if name_q and match:
            if name_q not in _normalize(c.name):
                match = False
                
        # Cek Kode Circle
        if code_q and match:
            if code_q not in _normalize(c.circle_code):
                match = False

        if match:
            results.append(c)

    return results


# ---------- GUI ----------


class CatalogSearchApp:
    def __init__(self, root: tk.Tk, circles: list[Circle]):
        self.root = root
        self.circles = circles
        self.filtered: list[Circle] = []
        
        # State untuk fitur sorting
        self.sort_col = "code"
        self.sort_desc = False

        root.title("Comic Frontier 22 Catalog Search")
        root.geometry("900x600")

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Fandom").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text="Circle Name").grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(top, text="Circle Code").grid(row=0, column=2, sticky="w", padx=(8, 0))

        self.fandom_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.code_var = tk.StringVar()

        for var in (self.fandom_var, self.name_var, self.code_var):
            var.trace_add("write", lambda *_: self._on_query_changed())

        self.fandom_entry = ttk.Entry(top, textvariable=self.fandom_var, width=30)
        self.name_entry = ttk.Entry(top, textvariable=self.name_var, width=30)
        self.code_entry = ttk.Entry(top, textvariable=self.code_var, width=20)
        self.fandom_entry.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.name_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(2, 0))
        self.code_entry.grid(row=1, column=2, sticky="ew", padx=(8, 0), pady=(2, 0))

        top.columnconfigure(0, weight=2)
        top.columnconfigure(1, weight=2)
        top.columnconfigure(2, weight=1)

        refresh_btn = ttk.Button(top, text="Refresh", command=self._refresh_catalog)
        refresh_btn.grid(row=1, column=3, padx=(8, 0))

        self.status_var = tk.StringVar(value=f"{len(circles)} circles loaded.")
        status = ttk.Label(root, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", padx=10)

        table_frame = ttk.Frame(root, padding=(10, 4, 10, 10))
        table_frame.pack(fill="both", expand=True)

        columns = ("name", "code", "fandom")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse"
        )
        
        # Tambahkan command klik pada heading untuk fitur sorting
        self.tree.heading("name", text="Circle Name", command=lambda: self._sort_tree("name"))
        self.tree.heading("code", text="Circle Code", command=lambda: self._sort_tree("code"))
        self.tree.heading("fandom", text="Fandom", command=lambda: self._sort_tree("fandom"))
        
        self.tree.column("name", width=240, anchor="w")
        self.tree.column("code", width=140, anchor="w")
        self.tree.column("fandom", width=380, anchor="w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.context_menu = tk.Menu(root, tearoff=0)
        self.context_menu.add_command(
            label="Open circle page", command=self._open_selected_circle
        )
        self.context_menu.add_command(
            label="Copy circle URL", command=self._copy_selected_url
        )

        # Right-click (Button-3 on Linux/Windows, Button-2 on some macOS setups).
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Button-2>", self._show_context_menu)
        self.tree.bind("<Double-1>", lambda _e: self._open_selected_circle())

        self._apply_filter()

    # ---- handlers ----

    def _on_query_changed(self) -> None:
        self._apply_filter()
        
    def _sort_tree(self, col: str) -> None:
        """Handler saat judul kolom diklik."""
        if self.sort_col == col:
            # Jika kolom yang sama diklik lagi, balik urutannya
            self.sort_desc = not self.sort_desc
        else:
            # Jika kolom baru, set jadi ascending
            self.sort_col = col
            self.sort_desc = False
        
        self._render_tree()

    def _apply_filter(self) -> None:
        self.filtered = search_circles(
            self.circles,
            self.fandom_var.get(),
            self.name_var.get(),
            self.code_var.get(),
        )
        self._render_tree()
        
    def _render_tree(self) -> None:
        """Mengurutkan dan menampilkan data ke dalam Treeview."""
        # Proses sorting data yang sudah difilter
        if self.sort_col == "name":
            self.filtered.sort(key=lambda c: c.name.lower(), reverse=self.sort_desc)
        elif self.sort_col == "code":
            self.filtered.sort(key=lambda c: c.circle_code.lower(), reverse=self.sort_desc)
        elif self.sort_col == "fandom":
            self.filtered.sort(key=lambda c: c.combined_fandom.lower(), reverse=self.sort_desc)

        # Hapus isi tabel lama
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Masukkan isi tabel baru
        for circle in self.filtered:
            self.tree.insert(
                "",
                "end",
                iid=str(circle.id),
                values=(circle.name, circle.circle_code, circle.combined_fandom),
            )
            
        # Update panah arah sorting pada teks header
        arrow = " \u2193" if self.sort_desc else " \u2191"
        self.tree.heading("name", text=f"Circle Name{' '+arrow if self.sort_col=='name' else ''}")
        self.tree.heading("code", text=f"Circle Code{' '+arrow if self.sort_col=='code' else ''}")
        self.tree.heading("fandom", text=f"Fandom{' '+arrow if self.sort_col=='fandom' else ''}")
            
        self.status_var.set(
            f"{len(self.filtered)} of {len(self.circles)} circles match."
        )

    def _show_context_menu(self, event: tk.Event) -> None:
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _selected_circle_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _open_selected_circle(self) -> None:
        cid = self._selected_circle_id()
        if cid is None:
            return
        webbrowser.open_new_tab(CIRCLE_URL_TEMPLATE.format(id=cid))

    def _copy_selected_url(self) -> None:
        cid = self._selected_circle_id()
        if cid is None:
            return
        url = CIRCLE_URL_TEMPLATE.format(id=cid)
        self.root.clipboard_clear()
        self.root.clipboard_append(url)

    def _refresh_catalog(self) -> None:
        self.status_var.set("Refreshing catalog…")
        self.root.update_idletasks()
        try:
            self.circles = load_circles(force_refresh=True)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Refresh failed", str(exc))
            return
        self.status_var.set(f"{len(self.circles)} circles loaded.")
        self._apply_filter()


def main() -> int:
    try:
        circles = load_circles()
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to load catalog: {exc}", file=sys.stderr)
        return 1

    root = tk.Tk()
    CatalogSearchApp(root, circles)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())