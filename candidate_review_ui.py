"""Per-supermarket candidate selection with a live price preview.

The reviewer sees every store listing the robot considered for one BAP product, grouped by supermarket, and
chooses which ones count towards the price. Works like the Review prices tab: A / R decide and move on,
decided rows stay listed until the filters are refreshed, Ctrl+Z / Ctrl+Y undo and redo.
"""
import re
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from price_review import NAME, PRICE, number
from matcher_core import normalize


# ---------------------------------------------------------------------------
# Plain-language reasons. The robot writes short technical notes ("SIZE-DISTANT MATCH REMOVED: ratio=0.42; …");
# each rule turns one kind of note into a sentence. Anything not recognised is shown as written.
# ---------------------------------------------------------------------------
def _pct(value):
    try:
        return f"{float(value) * 100:.0f} %"
    except (TypeError, ValueError):
        return "?"


_REASON_RULES = [
    (r"^accepted; sold by weight", lambda m: ("Aceptado: se vende por peso", "Accepted: sold by weight")),
    (r"^accepted; size strategy=PREFERRED.*?ratio=([\d.]+)",
     lambda m: (f"Aceptado: tamaño parecido ({_pct(m[1])} del producto BAP)",
                f"Accepted: similar size ({_pct(m[1])} of the BAP product)")),
    (r"^accepted; size strategy=CLOSE.*?ratio=([\d.]+)",
     lambda m: (f"Aceptado: tamaño cercano ({_pct(m[1])} del producto BAP)",
                f"Accepted: close size ({_pct(m[1])} of the BAP product)")),
    (r"^accepted; size strategy=FALLBACK.*?ratio=([\d.]+)",
     lambda m: (f"Aceptado: el tamaño más cercano disponible ({_pct(m[1])} del producto BAP)",
                f"Accepted: nearest size available ({_pct(m[1])} of the BAP product)")),
    (r"^accepted", lambda m: ("Aceptado", "Accepted")),
    (r"SIZE-DISTANT MATCH REMOVED: ratio=([\d.]+)",
     lambda m: (f"Tamaño muy distinto ({_pct(m[1])} del producto BAP)",
                f"Size too different ({_pct(m[1])} of the BAP product)")),
    (r"SIZE PEER REMOVED", lambda m: ("Sin tamaño, mientras otros productos sí lo tienen",
                                      "No size, while other listings have one")),
    (r"cannot normalize candidate to kg", lambda m: ("No se pudo leer el tamaño del paquete",
                                                      "The package size couldn't be read")),
    (r"cannot count units", lambda m: ("No se pudieron contar las unidades del paquete",
                                       "The number of units couldn't be read")),
    (r"missing required identity word\(s\): (.+)",
     lambda m: (f"Le faltan palabras clave: {m[1]}", f"Missing key words: {m[1]}")),
    (r"unexpected subtype for plain '(.+?)': (.+)",
     lambda m: (f"Variante distinta de «{m[1]}»: {m[2]}", f"Different kind of “{m[1]}”: {m[2]}")),
    (r"PRICE OUTLIER REMOVED: \$([\d.,]+)/kg vs median \$([\d.,]+)/kg",
     lambda m: (f"Precio fuera de rango: ${m[1]}/kg frente a la mediana ${m[2]}/kg",
                f"Price out of range: ${m[1]}/kg vs median ${m[2]}/kg")),
    (r"different item size: target ([\d.]+), candidate ([\d.]+)",
     lambda m: (f"Tamaño por unidad distinto: BAP {m[1]}, tienda {m[2]} (kg/L)",
                f"Different unit size: BAP {m[1]}, store {m[2]} (kg/L)")),
    (r"different dimensions: target (\S+), candidate (\S+)",
     lambda m: (f"Medidas distintas: BAP {m[1]}, tienda {m[2]}", f"Different dimensions: BAP {m[1]}, store {m[2]}")),
    (r"target word only appears after '(.+?)'",
     lambda m: (f"La palabra clave solo aparece después de «{m[1]}» (ingrediente o sabor, no el producto)",
                f"The key word only appears after “{m[1]}” (ingredient or flavour, not the product)")),
    (r"different product: title leads with '(.+?)'",
     lambda m: (f"Otro producto: el nombre empieza con «{m[1]}»", f"Different product: the name starts with “{m[1]}”")),
    (r"speciality/premium version of the product: (.+)",
     lambda m: (f"Versión especial o premium: {m[1]}", f"Special or premium version: {m[1]}")),
    (r"preparation/mix, not the product itself: (.+)",
     lambda m: (f"Mezcla o preparado, no el producto: {m[1]}", f"Mix or preparation, not the product: {m[1]}")),
    (r"made from/with '(.+?)', not the product itself",
     lambda m: (f"Hecho con «{m[1]}», no es el producto", f"Made with “{m[1]}”, not the product itself")),
    (r"false[- ]positive (?:family )?term\(s\): (.+)",
     lambda m: (f"Coincidencia engañosa: {m[1]}", f"Misleading match: {m[1]}")),
    (r"alcoholic product: (.+)", lambda m: (f"Producto alcohólico: {m[1]}", f"Alcoholic product: {m[1]}")),
    (r"pet product: (.+)", lambda m: (f"Producto para mascotas: {m[1]}", f"Pet product: {m[1]}")),
    (r"non-food product for a food target: (.+)", lambda m: (f"No es un alimento: {m[1]}", f"Not a food product: {m[1]}")),
    (r"breaded/prepared version of the product: (.+)",
     lambda m: (f"Versión empanizada o preparada: {m[1]}", f"Breaded or prepared version: {m[1]}")),
    (r"processed/canned product for a fresh-produce target: (.+)",
     lambda m: (f"Procesado o enlatado (se busca fresco): {m[1]}", f"Processed or canned (fresh wanted): {m[1]}")),
    (r"cooked/deli/seasoned version of a raw meat product: (.+)",
     lambda m: (f"Versión cocida o de charcutería: {m[1]}", f"Cooked or deli version: {m[1]}")),
    (r"physical-form mismatch: (.+)",
     lambda m: ("Forma distinta (sólido frente a líquido)", "Different form (solid vs liquid)")),
    (r"different/extra flavour\(s\): (.+)", lambda m: (f"Sabor distinto o adicional: {m[1]}", f"Different or extra flavour: {m[1]}")),
    (r"NEAR-DUPLICATE REMOVED: overlaps SKU \S+ \((.+)\)",
     lambda m: (f"Duplicado de «{m[1]}»", f"Duplicate of “{m[1]}”")),
    (r"generic product word '(.+?)' appears too late",
     lambda m: (f"«{m[1]}» aparece muy tarde en el nombre", f"“{m[1]}” appears too late in the name")),
]
_REASON_RULES = [(re.compile(pattern, re.I), build) for pattern, build in _REASON_RULES]


def friendly_reason(reason, lang="es", short=False):
    """The robot's technical note as a sentence in the reviewer's language. short=True drops what the
    table already shows elsewhere ("Accepted:" — that's the Robot column — and "of the BAP product")."""
    text = str(reason or "").strip()
    for pattern, build in _REASON_RULES:
        match = pattern.search(text)
        if match:
            es, en = build(match)
            text = es if lang == "es" else en
            if short:
                text = re.sub(r"^(Aceptado|Accepted)(: |$)", "", text)
                text = text.replace(" del producto BAP", "").replace(" of the BAP product", "")
                text = text[:1].upper() + text[1:] if text else ("Aceptado" if lang == "es" else "Accepted")
            return text
    return text


_STORE_SITES = {"super99": "https://www.super99.com", "superxtra": "https://www.superxtra.com",
                "rey": "https://www.smrey.com", "ribasmith": "https://www.ribasmith.com"}


def product_url(candidate):
    """A web address that a browser can open, or "" when there is none. Stores save links in different shapes:
    Super 99 leaves out "https:" ("//www.super99.com/…"), some are relative ("/product/…"), and some search
    links carry accents that were encoded twice ("ESP%C3%83%C2%91OL" instead of "ESPAÑOL")."""
    from urllib.parse import quote, unquote, urlsplit, urlunsplit
    url = str(candidate.get("Product URL") or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        site = _STORE_SITES.get(str(candidate.get("Store") or "").strip().lower())
        if not site:
            return ""
        url = site + url
    elif not url.lower().startswith(("http://", "https://")):
        if url.lower().startswith("www."):
            url = "https://" + url
        else:
            return ""
    parts = urlsplit(url)
    query = unquote(parts.query)
    try:  # undo double encoding: "Ã\x91" (UTF-8 bytes read as Latin-1) back to "Ñ"
        repaired = query.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        repaired = query
    if repaired != query:
        parts = parts._replace(query=quote(repaired, safe="=&+"))
    return urlunsplit(parts)


def open_in_browser(url):
    """Open a web page in the default browser (Windows: through the shell, which is the most reliable)."""
    import os
    import sys
    if sys.platform.startswith("win"):
        try:
            os.startfile(url)
            return True
        except OSError:
            pass
    return webbrowser.open(url)


def _size_text(value):
    value = number(value)
    if value is None:
        return "—"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


class CandidateReviewWindow(tk.Toplevel):
    def __init__(self, parent, key):
        super().__init__(parent)
        from price_robot_ui import (C_BG, C_CARD, C_TEXT, C_MUTED, C_ACCENT, C_HEADER, C_BORDER, FONT,
                                    fit_window, register_scroll, on_mouse_wheel)
        self.review = parent
        self.session, self.key, self.tr = parent.session, key, parent.tr
        self.lang = self.session.lang
        tr = self.tr
        self.colors = dict(bg=C_BG, card=C_CARD, text=C_TEXT, muted=C_MUTED, accent=C_ACCENT, header=C_HEADER, border=C_BORDER)
        self.overrides = dict(self.session.items[key]["candidate_overrides"])
        self.candidates = self.session.candidates[key]
        self.undo_stack, self.redo_stack = [], []
        self._drag_anchor = self._drag_timer = self._drag_tree = None
        self.sorts = {}
        body_font, heading_font = parent.body_font, parent.heading_font
        unit = parent.unit
        gap = max(8, unit // 2)
        self.title(tr("Choose supermarket candidates", "Elegir candidatos por supermercado"))
        self.configure(background=C_BG)
        fit_window(self, 1280, 2000, 780, 560)   # as tall as the screen allows
        self.transient(parent.winfo_toplevel())
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        style = ttk.Style(self)
        style.configure("Cand.TNotebook", background=C_BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("Cand.TNotebook.Tab", font=body_font, padding=(gap * 2, 2))
        style.map("Cand.TNotebook.Tab", font=[("selected", heading_font)],
                  foreground=[("selected", C_HEADER)], background=[("selected", C_CARD)])
        style.configure("CandCard.TFrame", background=C_CARD)

        def card(row, pady=(0, gap)):
            frame = tk.Frame(self, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
            frame.grid(row=row, column=0, sticky="nsew", padx=gap * 2, pady=pady)
            return frame

        # 1. Header (one compact card): which product, the price it leads to, and the filters.
        header = card(0, pady=(gap, gap // 2))
        header.columnconfigure(0, weight=1)
        titles = tk.Frame(header, bg=C_CARD)
        titles.grid(row=0, column=0, sticky="nsew", padx=gap * 2, pady=(gap, 0))
        product = tk.Label(titles, text=f'{self.session.items[key]["row"].get(NAME) or ""}', bg=C_CARD, fg=C_HEADER,
                           font=(FONT, 12, "bold"), anchor="w", justify="left")
        product.pack(anchor="w", fill="x")
        product.bind("<Configure>", lambda e: product.configure(wraplength=max(200, e.width)))
        tk.Label(titles, text=key, bg=C_CARD, fg=C_MUTED, font=(FONT, 9)).pack(anchor="w")
        self.preview_label = tk.Label(titles, bg=C_CARD, fg=C_MUTED, font=(FONT, 9), anchor="w", justify="left")
        self.preview_label.pack(anchor="w", fill="x")
        boxes = tk.Frame(header, bg=C_CARD)
        boxes.grid(row=0, column=1, sticky="ne", padx=(0, gap * 2), pady=(gap, 0))
        self.metrics = {}
        for index, (name, label) in enumerate((("current", tr("CURRENT BAP", "ACTUAL BAP")),
                                               ("before", tr("PROPOSAL NOW", "PROPUESTA AHORA")),
                                               ("after", tr("WITH THIS SELECTION", "CON ESTA SELECCIÓN")))):
            box = tk.Frame(boxes, bg="#F0F5F0" if name != "after" else "#E3F1E5",
                           highlightbackground=C_BORDER if name != "after" else C_ACCENT, highlightthickness=1,
                           padx=gap, pady=2)
            box.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else gap // 2, 0))
            tk.Label(box, text=label, bg=box["bg"], fg=C_MUTED, font=(FONT, 7, "bold")).pack(anchor="w")
            line = tk.Frame(box, bg=box["bg"])
            line.pack(fill="x")
            note = tk.Label(line, text="", bg=box["bg"], fg=C_MUTED, font=(FONT, 8))
            note.pack(side="left", anchor="s", padx=(0, gap // 2))
            value = tk.Label(line, text="—", bg=box["bg"], fg=C_HEADER, font=(FONT, 13, "bold"), anchor="e")
            value.pack(side="right")
            self.metrics[name] = (value, note)

        # filters, second line of the same card
        inner = tk.Frame(header, bg=C_CARD)
        inner.grid(row=1, column=0, columnspan=2, sticky="ew", padx=gap * 2, pady=(gap // 2, gap))
        inner.columnconfigure(1, weight=1)
        tk.Label(inner, text=tr("Search:", "Buscar:"), bg=C_CARD, fg=C_TEXT, font=body_font).grid(row=0, column=0, padx=(0, gap))
        self.search = tk.StringVar()
        self.search_entry = ttk.Entry(inner, textvariable=self.search, font=body_font)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, gap * 2))
        self.filter_values = [tr("All listings", "Todos los productos"), tr("Included", "Incluidos"),
                              tr("Excluded", "Excluidos"), tr("Changed by me", "Cambiados por mí")]
        self.original_values = [tr("Robot: any decision", "Robot: cualquier decisión"),
                                tr("Robot accepted", "Aceptados por el robot"), tr("Robot rejected", "Rechazados por el robot")]
        self.filter = tk.StringVar(value=self.filter_values[0])
        self.original_filter = tk.StringVar(value=self.original_values[0])
        for column, (variable, values) in enumerate(((self.filter, self.filter_values),
                                                    (self.original_filter, self.original_values)), start=2):
            selector = ttk.Combobox(inner, textvariable=variable, values=values, state="readonly", font=body_font,
                                    width=max(len(v) for v in values) + 2)
            selector.grid(row=0, column=column, padx=(0, gap))
            selector.bind("<<ComboboxSelected>>", lambda _e: self.refresh_list())
        ttk.Button(inner, text=tr("Refresh list", "Actualizar lista"), style="Review.TButton",
                   command=self.refresh_list).grid(row=0, column=4, padx=(0, gap))
        ttk.Button(inner, text=tr("Clear filters", "Limpiar filtros"), style="Review.TButton",
                   command=self.clear_filters).grid(row=0, column=5)
        self.visible_label = tk.Label(inner, bg=C_CARD, fg=C_MUTED, font=(FONT, 9))
        self.visible_label.grid(row=0, column=6, padx=(gap, 0))

        # 3. One tab per supermarket
        self.notebook = ttk.Notebook(self, style="Cand.TNotebook")
        self.notebook.grid(row=2, column=0, sticky="nsew", padx=gap * 2)
        self.trees, self.tabs = {}, {}
        stores = {}
        for candidate in self.candidates:
            store = str(candidate.get("Store") or candidate.get("Store Name") or "Unknown")
            stores[store] = str(candidate.get("Store Name") or store)
        for store in str(self.session.original_rows[key].get("Selected Stores") or "").split(","):
            if store.strip():
                stores.setdefault(store.strip(), store.strip())
        names = {"super99": "Super 99", "superxtra": "Super Xtra", "rey": "Rey", "ribasmith": "Riba Smith"}
        self.store_names = {store: names.get(store, name) for store, name in stores.items()}
        columns = ("used", "original", "name", "price", "size", "unit", "reason")
        labels = (tr("Use", "Usar"), tr("Robot", "Robot"), tr("Store product", "Producto de la tienda"), tr("Price", "Precio"),
                  tr("Size (kg / u)", "Tamaño (kg / u)"), tr("Price per kg / u", "Precio por kg / u"),
                  tr("Robot's reason", "Motivo del robot"))
        self.column_labels = dict(zip(columns, labels))
        samples = {"used": [tr("Included · changed", "Incluido · cambiado"), tr("Excluded · changed", "Excluido · cambiado")],
                   "price": ["$9,999.99"], "size": ["99,999.999"], "unit": ["$9,999.99"],
                   "original": [tr("Accepted", "Aceptó"), tr("Rejected", "Rechazó")]}
        for store in stores:
            tab = tk.Frame(self.notebook, bg=C_CARD)
            self.notebook.add(tab, text=self.store_names[store])
            self.tabs[store] = tab
            tab.rowconfigure(0, weight=1)
            tab.columnconfigure(0, weight=1)
            tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="extended", style="Review.Treeview")
            self.sorts[store] = (None, False)
            for col, label in zip(columns, labels):
                tree.heading(col, text=label, anchor="e" if col in ("price", "size", "unit") else "w",
                             command=lambda s=store, c=col: self.sort_by(s, c))
                width = max(heading_font.measure(text) for text in [label + " ↓"] + samples.get(col, [])) + gap * 4
                if col == "name":
                    width = body_font.measure("M") * 26
                elif col == "reason":
                    width = body_font.measure("M") * 24
                tree.column(col, width=width, minwidth=width if col not in ("name", "reason") else width // 2,
                            stretch=col in ("name", "reason"), anchor="e" if col in ("price", "size", "unit") else "w")
            tree.grid(row=0, column=0, sticky="nsew")
            yscroll = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            yscroll.grid(row=0, column=1, sticky="ns")
            xscroll = ttk.Scrollbar(tab, orient="horizontal", command=tree.xview)
            xscroll.grid(row=1, column=0, sticky="ew")
            tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
            tree.tag_configure("included", background="#edf7ee")
            tree.tag_configure("excluded", background="#fbf1f1", foreground="#6B5B5B")
            tree.tag_configure("changed", font=heading_font)
            tree.bind("<<TreeviewSelect>>", self.show_selection)
            tree.bind("<KeyPress>", self.tree_key)
            tree.bind("<ButtonPress-1>", self.drag_start)
            tree.bind("<B1-Motion>", self.drag_move)
            tree.bind("<ButtonRelease-1>", self.drag_end)
            tree.bind("<Double-1>", lambda _e: self.choose_toggle())
            register_scroll(tree, text_lines=True)
            tree.bind("<MouseWheel>", on_mouse_wheel)
            self.trees[store] = tree
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_changed)

        # 4. One row of buttons: decisions on the left, finishing on the right.
        actions = tk.Frame(self, bg=C_BG)
        actions.grid(row=3, column=0, sticky="ew", padx=gap * 2, pady=(gap // 2, 0))
        self.include_button = ttk.Button(actions, text=tr("Include [A]", "Incluir [A]"), style="ReviewAccent.TButton",
                                         command=lambda: self.choose(True, advance=True))
        self.include_button.pack(side="left")
        self.exclude_button = ttk.Button(actions, text=tr("Exclude [R]", "Excluir [R]"), style="Review.TButton",
                                         command=lambda: self.choose(False, advance=True))
        self.exclude_button.pack(side="left", padx=(gap // 2, 0))
        self.undo_button = ttk.Button(actions, text=tr("Undo [Ctrl+Z]", "Deshacer [Ctrl+Z]"), style="Review.TButton", command=self.undo)
        self.undo_button.pack(side="left", padx=(gap, 0))
        self.redo_button = ttk.Button(actions, text=tr("Redo [Ctrl+Y]", "Rehacer [Ctrl+Y]"), style="Review.TButton", command=self.redo)
        self.redo_button.pack(side="left", padx=(gap // 2, 0))
        self.link_button = ttk.Button(actions, text=tr("Open page [O]", "Abrir página [O]"),
                                      style="Review.TButton", command=self.open_product)
        self.link_button.pack(side="left", padx=(gap, 0))
        self.apply_button = ttk.Button(actions, text=tr("Apply new price", "Aplicar nuevo precio"),
                                       style="ReviewAccent.TButton", command=self.apply)
        self.apply_button.pack(side="right")
        ttk.Button(actions, text=tr("Cancel", "Cancelar"), style="Review.TButton", command=self.destroy).pack(side="right", padx=gap // 2)
        ttk.Button(actions, text=tr("Restore robot's choices", "Restaurar selección del robot"),
                   style="Review.TButton", command=self.reset).pack(side="right", padx=(0, gap))

        # 5. The selected listing, in two short lines
        details = card(4, pady=(gap // 2, gap))
        details.columnconfigure(0, weight=1)
        self.selection_title = tk.Label(details, bg=C_CARD, fg=C_HEADER, font=heading_font, anchor="w", justify="left")
        self.selection_title.grid(row=0, column=0, sticky="ew", padx=gap, pady=(gap // 2, 0))
        self.selection_label = tk.Label(details, bg=C_CARD, fg=C_TEXT, font=(FONT, 9), anchor="w", justify="left")
        self.selection_label.grid(row=1, column=0, sticky="ew", padx=gap, pady=(0, gap // 2))
        for label in (self.selection_title, self.selection_label):
            label.bind("<Configure>", lambda e: e.widget.configure(wraplength=max(200, e.width)))

        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<Control-f>", self.focus_search)
        self.bind("<Control-Return>", lambda _: self.apply() or "break")
        for sequence, handler in (("<Control-z>", self.undo), ("<Control-Z>", self.undo),
                                  ("<Control-y>", self.redo), ("<Control-Y>", self.redo)):
            self.bind(sequence, lambda _e, h=handler: h() or "break")
        for variable in (self.search, self.filter, self.original_filter):
            variable.trace_add("write", lambda *_: self.refresh())
        self.refresh()
        self._focus_job = self.after_idle(self.focus_list)
        self.grab_set()

    # -- helpers ---------------------------------------------------------------
    def active_tree(self):
        tab = self.notebook.select()
        return next((self.trees[s] for s, frame in self.tabs.items() if str(frame) == tab), None)

    def store_of(self, candidate):
        return str(candidate.get("Store") or candidate.get("Store Name") or "Unknown")

    def money(self, value):
        value = number(value)
        return "—" if value is None else f"${value:,.2f}"

    # -- list ------------------------------------------------------------------
    def refresh(self, keep=False):
        """Redraw every store's list. With keep=True the rows already on screen stay even if they no longer
        match the filters (after a decision), until the list is refreshed."""
        self.drag_end()
        tr = self.tr
        for store, tree in self.trees.items():
            selected = tree.selection()
            shown = set(tree.get_children()) if keep else set()
            visible = []
            count = total = 0
            for index, candidate in enumerate(self.candidates):
                if self.store_of(candidate) != store:
                    continue
                included = self.session.candidate_accepted(self.key, index, self.overrides)
                count += int(included)
                total += 1
                iid = str(index)
                if iid not in shown and not self.matches(index):
                    if tree.exists(iid):
                        tree.delete(iid)
                    continue
                visible.append(iid)
                changed = included != (candidate.get("Status") == "ACCEPTED")
                used = (tr("Included", "Incluido") if included else tr("Excluded", "Excluido")) + \
                    (tr(" · changed", " · cambiado") if changed else "")
                original = tr("Accepted", "Aceptó") if candidate.get("Status") == "ACCEPTED" else tr("Rejected", "Rechazó")
                pad = "    "   # keeps right-aligned numbers off the next column
                values = (used, original, candidate.get("Candidate Product") or "",
                          self.money(candidate.get("Chosen Price")) + pad, _size_text(candidate.get("Normalized kg")) + pad,
                          self.money(self.session.candidate_unit_price(candidate)) + pad,
                          friendly_reason(candidate.get("Reason"), self.lang, short=True))
                tags = ("included" if included else "excluded",) + (("changed",) if changed else ())
                if tree.exists(iid):
                    tree.item(iid, values=values, tags=tags)
                else:
                    tree.insert("", "end", iid=iid, values=values, tags=tags)
            column, reverse = self.sorts[store]
            if column:
                present = [i for i in visible if self.sort_value(i, column) is not None]
                missing = [i for i in visible if self.sort_value(i, column) is None]
                visible = sorted(present, key=lambda i: self.sort_value(i, column), reverse=reverse) + missing
            tree.set_children("", *visible)
            tree.selection_set([i for i in selected if i in visible])
            self.notebook.tab(self.tabs[store], text=tr(f"{self.store_names[store]}  ·  {count} of {total} used",
                                                        f"{self.store_names[store]}  ·  {count} de {total} usados"))
        self.update_preview()
        self.show_selection()
        self.undo_button.configure(state="normal" if self.undo_stack else "disabled")
        self.redo_button.configure(state="normal" if self.redo_stack else "disabled")

    def refresh_list(self):
        """Apply the filters again and give the keyboard back to the list."""
        self.refresh()
        self.focus_list()

    def focus_list(self):
        self._focus_job = None
        tree = self.active_tree()
        if tree is None or not self.winfo_exists():
            return
        rows = tree.get_children()
        if not tree.selection() and rows:
            tree.selection_set(rows[0])
        if tree.selection():
            tree.focus(tree.selection()[0])
            tree.see(tree.selection()[0])
        tree.focus_set()
        self.show_selection()

    def update_preview(self):
        tr = self.tr
        item = self.session.items[self.key]
        current, before = item["current"], number(item["row"].get(PRICE))
        value, note = self.metrics["current"]
        value.configure(text=self.money(current))
        value, note = self.metrics["before"]
        value.configure(text=self.money(before))
        after_value, after_note = self.metrics["after"]
        try:
            reviewed = self.session.preview_candidates(self.key, self.overrides)
        except ValueError as exc:
            after_value.configure(text="—")
            after_note.configure(text="")
            self.preview_label.configure(text=str(exc), fg="#B42318")
            self.apply_button.configure(state="disabled")
            return
        row = reviewed["row"]
        after = number(row.get(PRICE))
        after_value.configure(text=self.money(after))
        change = (after - current) / current if after is not None and current else None
        after_note.configure(text="" if change is None else tr(f"{change:+.1%} vs current", f"{change:+.1%} vs actual"),
                             fg="#B45309" if change is not None and abs(change) > self.session.settings.get(
                                 "PRICE_CHANGE_REVIEW_THRESHOLD", 0.2) else self.colors["muted"])
        if after is None:
            self.preview_label.configure(fg="#B45309", text=tr(
                "No listings included — applying will clear the proposed price.",
                "No hay productos incluidos; aplicar quitará el precio propuesto."))
        else:
            self.preview_label.configure(fg=self.colors["muted"], text=tr(
                f"Proposal: {self.money(before)} → {self.money(after)} · {row['Accepted Count']} listings · "
                f"{row['Store Count']} supermarkets",
                f"Propuesta: {self.money(before)} → {self.money(after)} · {row['Accepted Count']} productos · "
                f"{row['Store Count']} supermercados"))
        self.apply_button.configure(state="normal")

    def show_selection(self, event=None):
        tr = self.tr
        tree = self.active_tree()
        selected = tree.selection() if tree is not None else ()
        shown = len(tree.get_children()) if tree is not None else 0
        self.visible_label.configure(text=tr(f"Showing {shown} · {len(selected)} selected",
                                             f"Visibles: {shown} · Seleccionados: {len(selected)}"))
        for button in (self.include_button, self.exclude_button):
            button.configure(state="normal" if selected else "disabled")
        self.link_button.configure(state="disabled")
        if len(selected) == 1:
            index = int(selected[0])
            candidate = self.candidates[index]
            included = self.session.candidate_accepted(self.key, index, self.overrides)
            size, per_unit = number(candidate.get("Normalized kg")), self.session.candidate_unit_price(candidate)
            facts = [self.store_names.get(self.store_of(candidate), self.store_of(candidate)),
                     f"SKU {candidate.get('SKU') or '—'}", self.money(candidate.get("Chosen Price")),
                     tr(f"size {_size_text(size)}", f"tamaño {_size_text(size)}") if size is not None
                     else tr("size unknown", "tamaño desconocido")]
            if per_unit is not None:
                facts.append(tr(f"{self.money(per_unit)} per kg / u", f"{self.money(per_unit)} por kg / u"))
            if candidate.get("Search Query"):
                facts.append(tr(f"found searching “{candidate.get('Search Query')}”",
                                f"encontrado buscando «{candidate.get('Search Query')}»"))
            robot = tr("The robot accepted it", "El robot lo aceptó") if candidate.get("Status") == "ACCEPTED" \
                else tr("The robot rejected it", "El robot lo rechazó")
            state = tr("Included in the price", "Incluido en el precio") if included else tr("Not used", "No se usa")
            self.selection_title.configure(text=f"{candidate.get('Candidate Product') or ''}  —  " + " · ".join(facts))
            text = f"{state}. {robot}: {friendly_reason(candidate.get('Reason'), self.lang)}"
            if self.session.candidate_unit_price(candidate) is None:
                text += tr("\nCan't be included: the price or package size is missing.",
                           "\nNo se puede incluir: falta el precio o el tamaño del paquete.")
            self.selection_label.configure(text=text)
            if product_url(candidate):
                self.link_button.configure(state="normal")
        elif tree is not None and not tree.get_children():
            self.selection_title.configure(text=tr("Nothing to show", "Nada que mostrar"))
            self.selection_label.configure(text=tr(
                "No listings match these filters, or the robot saved no listings for this supermarket.",
                "Ningún producto coincide con los filtros, o el robot no guardó productos de este supermercado."))
        elif selected:
            self.selection_title.configure(text=tr(f"{len(selected)} listings selected", f"{len(selected)} productos seleccionados"))
            self.selection_label.configure(text=tr("A includes them all, R excludes them all.",
                                                   "A los incluye a todos, R los excluye a todos."))
        else:
            self.selection_title.configure(text=tr("Select a listing", "Seleccione un producto"))
            self.selection_label.configure(text=tr(
                "Click a listing to see why the robot used it or not. Ctrl / Shift or dragging selects several.",
                "Haga clic en un producto para ver por qué el robot lo usó o no. Ctrl / Mayús o arrastrar selecciona varios."))

    # -- decisions -------------------------------------------------------------
    def _remember(self):
        self.undo_stack.append(dict(self.overrides))
        self.redo_stack.clear()

    def choose(self, included, advance=False):
        tree = self.active_tree()
        selected = tree.selection() if tree is not None else ()
        if not selected:
            return
        order = list(tree.get_children())
        if included and any(self.session.candidate_unit_price(self.candidates[int(i)]) is None for i in selected):
            messagebox.showerror(self.title(), self.tr("Some selected listings have no usable price or package size.",
                                                     "Algunos productos seleccionados no tienen precio o tamaño válido."), parent=self)
            return
        changes = {i: included for i in selected if self.session.candidate_accepted(self.key, int(i), self.overrides) != included}
        if changes:
            self._remember()
            self.overrides.update(changes)
        self.refresh(keep=True)
        if advance:
            last = max(order.index(i) for i in selected)
            next_key = next((i for i in order[last + 1:] if tree.exists(i)), None)
            tree.selection_set([next_key] if next_key else [])
            if next_key:
                tree.focus(next_key)
                tree.see(next_key)
            tree.focus_set()
            self.show_selection()

    def choose_toggle(self):
        tree = self.active_tree()
        selected = tree.selection() if tree is not None else ()
        if selected:
            self.choose(not all(self.session.candidate_accepted(self.key, int(i), self.overrides) for i in selected))

    def reset(self):
        if self.overrides:
            self._remember()
        self.overrides = {}
        self.refresh(keep=True)

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(dict(self.overrides))
            self.overrides = self.undo_stack.pop()
            self.refresh(keep=True)

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(dict(self.overrides))
            self.overrides = self.redo_stack.pop()
            self.refresh(keep=True)

    # -- filters and sorting ---------------------------------------------------
    def matches(self, index):
        candidate = self.candidates[index]
        included = self.session.candidate_accepted(self.key, index, self.overrides)
        original = candidate.get("Status") == "ACCEPTED"
        status = self.filter_values.index(self.filter.get())
        matcher = self.original_values.index(self.original_filter.get())
        if status == 1 and not included or status == 2 and included or status == 3 and included == original:
            return False
        if matcher == 1 and not original or matcher == 2 and original:
            return False
        text = " ".join(str(candidate.get(field) or "") for field in ("Candidate Product", "SKU", "Reason", "Search Query"))
        text += " " + friendly_reason(candidate.get("Reason"), self.lang)
        return normalize(self.search.get()) in normalize(text)

    def clear_filters(self):
        self.search.set("")
        self.filter.set(self.filter_values[0])
        self.original_filter.set(self.original_values[0])
        self.focus_list()

    def sort_value(self, index, column):
        candidate = self.candidates[int(index)]
        if column == "used":
            return self.session.candidate_accepted(self.key, int(index), self.overrides)
        if column == "original":
            return candidate.get("Status") == "ACCEPTED"
        if column == "unit":
            return self.session.candidate_unit_price(candidate)
        if column == "reason":
            return normalize(friendly_reason(candidate.get("Reason"), self.lang))
        field = {"name": "Candidate Product", "price": "Chosen Price", "size": "Normalized kg"}[column]
        return number(candidate.get(field)) if column in ("price", "size") else normalize(candidate.get(field) or "")

    def sort_by(self, store, column):
        old, reverse = self.sorts[store]
        self.sorts[store] = (column, not reverse if old == column else False)
        for key, label in self.column_labels.items():
            arrow = (" ↓" if self.sorts[store][1] else " ↑") if key == column else ""
            self.trees[store].heading(key, text=label + arrow)
        self.refresh()

    # -- keyboard --------------------------------------------------------------
    def focus_search(self, event=None):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, "end")
        return "break"

    def tree_key(self, event):
        key = event.keysym.lower()
        tree = event.widget
        if event.state & 4:
            if key == "a":
                tree.selection_set(tree.get_children())
                self.show_selection()
            elif key == "z":
                self.undo()
            elif key == "y":
                self.redo()
            elif key == "f":
                self.focus_search()
            elif key == "return":
                self.apply()
            else:
                return
            return "break"
        if event.state & 8:  # Leave Alt navigation to Tk.
            return
        if key in ("a", "return", "r", "delete"):
            self.choose(key in ("a", "return"), advance=True)
        elif key == "space":
            self.choose_toggle()
        elif key == "o":
            self.open_product()
        else:
            return
        return "break"

    def tab_changed(self, event=None):
        self.drag_end()
        if event is not None:
            self.focus_list()
        else:
            self.show_selection()

    # -- drag to select --------------------------------------------------------
    def drag_start(self, event):
        self.drag_end()
        tree = event.widget
        if tree.identify_region(event.x, event.y) in ("cell", "tree"):
            self._drag_tree = tree
            self._drag_anchor = tree.identify_row(event.y)
            self._drag_base = set(tree.selection()) if event.state & 4 else set()

    def drag_move(self, event):
        if not self._drag_anchor:
            return
        self._drag_y = event.y
        self.drag_range()
        return "break"

    def drag_range(self):
        if self._drag_timer:
            self.after_cancel(self._drag_timer)
            self._drag_timer = None
        tree = self._drag_tree
        if tree is None or not self._drag_anchor:
            return
        y = self._drag_y
        unit = self.review.unit
        direction = -1 if y < unit * 2 else 1 if y > tree.winfo_height() - unit else 0
        if direction:
            tree.yview_scroll(direction, "units")
            y = unit * 2 if direction < 0 else tree.winfo_height() - unit
            self._drag_timer = self.after(70, self.drag_range)
        rows = list(tree.get_children())
        target = tree.identify_row(y)
        if not target and direction and rows:
            target = rows[-1] if direction > 0 else rows[0]
        if target in rows and self._drag_anchor in rows:
            first, last = sorted((rows.index(self._drag_anchor), rows.index(target)))
            tree.selection_set(list(self._drag_base | set(rows[first:last + 1])))
            tree.focus(target)

    def drag_end(self, event=None):
        if self._drag_timer:
            self.after_cancel(self._drag_timer)
            self._drag_timer = None
        self._drag_anchor = self._drag_tree = None

    # -- closing ---------------------------------------------------------------
    def destroy(self):
        from price_robot_ui import _SCROLL_VIEWS, _SCROLL_REMAINDER
        self.drag_end()
        try:
            self.after_cancel(self._focus_job)
        except (AttributeError, tk.TclError, ValueError):
            pass
        for tree in self.trees.values():
            _SCROLL_VIEWS.pop(str(tree), None)
            _SCROLL_REMAINDER.pop(str(tree), None)
        super().destroy()

    def open_product(self):
        tree = self.active_tree()
        if tree is not None and len(tree.selection()) == 1:
            url = product_url(self.candidates[int(tree.selection()[0])])
            if url and not open_in_browser(url):
                messagebox.showerror(self.title(), self.tr(f"The page couldn't be opened:\n{url}",
                                                         f"No se pudo abrir la página:\n{url}"), parent=self)

    def apply(self):
        try:
            self.session.apply_candidates(self.key, self.overrides)
        except Exception as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)
            return
        self.review._detail_signature = None
        self.review.refresh(keep=self.review.tree.get_children())
        self.destroy()
