"""Per-supermarket candidate selection with a draft price preview."""
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from price_review import NAME, PRICE, number
from matcher_core import normalize


class CandidateReviewWindow(tk.Toplevel):
    def __init__(self, parent, key):
        super().__init__(parent)
        from price_robot_ui import C_BG, FONT, fit_window, register_scroll, on_mouse_wheel
        self.review = parent
        self.session, self.key, self.tr = parent.session, key, parent.tr
        tr = self.tr
        self.overrides = dict(self.session.items[key]["candidate_overrides"])
        self.candidates = self.session.candidates[key]
        self.undo_stack = []
        self._drag_anchor = self._drag_timer = self._drag_tree = None
        self.sorts = {}
        self.title(tr("Choose supermarket candidates", "Elegir candidatos por supermercado"))
        self.configure(background=C_BG)
        fit_window(self, 1120, 720, 720, 480)
        self.transient(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)
        ttk.Label(self, text=f'{key} · {self.session.items[key]["row"].get(NAME)}',
                  font=(FONT, 13, "bold"), wraplength=850).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 6))
        ttk.Label(self, text=tr(
            "Choose a supermarket, then include or exclude listings. Apply saves the new proposal as Pending for approval.",
            "Elija un supermercado e incluya o excluya productos. Aplicar guarda la nueva propuesta como Pendiente de aprobación."),
            wraplength=850).grid(row=1, column=0, sticky="w", padx=16)
        self.preview_label = ttk.Label(self, font=(FONT, 11, "bold"), wraplength=850)
        self.preview_label.grid(row=2, column=0, sticky="ew", padx=16, pady=12)
        filters = ttk.Frame(self, padding=(16, 0, 16, 8))
        filters.grid(row=3, column=0, sticky="ew")
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text=tr("Search:", "Buscar:")).grid(row=0, column=0, padx=(0, 6))
        self.search = tk.StringVar()
        self.search_entry = ttk.Entry(filters, textvariable=self.search)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(filters, text=tr("Clear filters", "Limpiar filtros"), command=self.clear_filters).grid(row=0, column=2, padx=(8, 0))
        options = ttk.Frame(filters)
        options.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.filter_values = [tr("All selections", "Toda la selección"), tr("Included", "Incluidos"),
                              tr("Excluded", "Excluidos"), tr("Changed by reviewer", "Cambiados por revisor")]
        self.original_values = [tr("All matcher decisions", "Todas las decisiones originales"),
                                tr("Originally accepted", "Aceptados originalmente"), tr("Originally rejected", "Rechazados originalmente")]
        self.filter = tk.StringVar(value=self.filter_values[0])
        self.original_filter = tk.StringVar(value=self.original_values[0])
        for variable, values in ((self.filter, self.filter_values), (self.original_filter, self.original_values)):
            selector = ttk.Combobox(options, textvariable=variable, values=values, state="readonly", width=29)
            selector.pack(side="left", padx=(0, 8))
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=4, column=0, sticky="nsew", padx=16)
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
        for store in stores:
            tab = ttk.Frame(self.notebook, padding=6)
            self.notebook.add(tab, text=self.store_names[store])
            self.tabs[store] = tab
            tab.rowconfigure(0, weight=1)
            tab.columnconfigure(0, weight=1)
            columns = ("used", "original", "name", "price", "size", "unit", "reason")
            tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="extended", style="Review.Treeview")
            labels = (tr("Use in price", "Usar en precio"), tr("Matcher decision", "Decisión original"),
                      tr("Product", "Producto"), tr("Price", "Precio"), tr("kg / units", "kg / unidades"),
                      tr("Price / kg or unit", "Precio / kg o unidad"), tr("Original reason", "Motivo original"))
            self.column_labels = dict(zip(columns, labels))
            self.sorts[store] = (None, False)
            for col, label, width in zip(columns, labels, (130, 145, 310, 95, 110, 160, 300)):
                tree.heading(col, text=label, command=lambda s=store, c=col: self.sort_by(s, c))
                tree.column(col, width=width, minwidth=75, stretch=col in ("name", "reason"))
            tree.grid(row=0, column=0, sticky="nsew")
            yscroll = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            yscroll.grid(row=0, column=1, sticky="ns")
            xscroll = ttk.Scrollbar(tab, orient="horizontal", command=tree.xview)
            xscroll.grid(row=1, column=0, sticky="ew")
            tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
            tree.tag_configure("included", background="#edf7ee")
            tree.tag_configure("excluded", background="#fceeee")
            tree.bind("<<TreeviewSelect>>", self.show_selection)
            tree.bind("<KeyPress>", self.tree_key)
            tree.bind("<ButtonPress-1>", self.drag_start)
            tree.bind("<B1-Motion>", self.drag_move)
            tree.bind("<ButtonRelease-1>", self.drag_end)
            register_scroll(tree, text_lines=True)
            tree.bind("<MouseWheel>", on_mouse_wheel)
            self.trees[store] = tree
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_changed)
        actions = ttk.Frame(self, padding=(16, 8))
        actions.grid(row=5, column=0, sticky="ew")
        self.include_button = ttk.Button(actions, text=tr("Include [A]", "Incluir [A]"), command=lambda: self.choose(True))
        self.include_button.pack(side="left")
        self.exclude_button = ttk.Button(actions, text=tr("Exclude [R]", "Excluir [R]"), command=lambda: self.choose(False))
        self.exclude_button.pack(side="left", padx=6)
        self.link_button = ttk.Button(actions, text=tr("Open product page", "Abrir página del producto"), command=self.open_product)
        self.link_button.pack(side="left")
        self.undo_button = ttk.Button(actions, text=tr("Undo [Ctrl+Z]", "Deshacer [Ctrl+Z]"), command=self.undo)
        self.undo_button.pack(side="left", padx=6)
        self.visible_label = ttk.Label(self)
        self.visible_label.grid(row=6, column=0, sticky="w", padx=16)
        self.selection_label = ttk.Label(self, wraplength=850, justify="left")
        self.selection_label.grid(row=7, column=0, sticky="ew", padx=16, pady=(0, 6))
        shortcuts = ttk.Label(self, wraplength=850, text=tr(
            "A / Enter include · R exclude · Space toggle · Ctrl+A select visible · Ctrl+F search · O open link · Drag to select · Click headings to sort · Ctrl+Enter apply",
            "A / Enter incluir · R excluir · Espacio alternar · Ctrl+A seleccionar visibles · Ctrl+F buscar · O abrir enlace · Arrastrar para seleccionar · Encabezados para ordenar · Ctrl+Enter aplicar"))
        shortcuts.grid(row=8, column=0, sticky="ew", padx=16)
        footer = ttk.Frame(self, padding=16)
        footer.grid(row=9, column=0, sticky="ew")
        ttk.Button(footer, text=tr("Restore matcher choices", "Restaurar selección original"), command=self.reset).pack(side="left")
        self.apply_button = ttk.Button(footer, text=tr("Apply recalculated price", "Aplicar precio recalculado"), command=self.apply)
        self.apply_button.pack(side="right")
        ttk.Button(footer, text=tr("Cancel", "Cancelar"), command=self.destroy).pack(side="right", padx=8)
        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<Control-f>", self.focus_search)
        self.bind("<Control-Return>", lambda _: self.apply() or "break")
        for variable in (self.search, self.filter, self.original_filter):
            variable.trace_add("write", lambda *_: self.refresh())
        for label in (self.selection_label, shortcuts, self.preview_label):
            label.bind("<Configure>", lambda event: event.widget.configure(wraplength=max(100, event.width)))
        self.refresh()
        self.grab_set()

    def active_tree(self):
        tab = self.notebook.select()
        return next((self.trees[s] for s, frame in self.tabs.items() if str(frame) == tab), None)

    def refresh(self):
        self.drag_end()
        tr = self.tr
        money = lambda value: "—" if number(value) is None else f"${number(value):,.2f}"
        for store, tree in self.trees.items():
            selected = tree.selection()
            visible = []
            count = total = 0
            for index, candidate in enumerate(self.candidates):
                if str(candidate.get("Store") or candidate.get("Store Name") or "Unknown") != store:
                    continue
                included = self.session.candidate_accepted(self.key, index, self.overrides)
                count += int(included)
                total += 1
                if not self.matches(index):
                    if tree.exists(str(index)):
                        tree.delete(str(index))
                    continue
                visible.append(str(index))
                original = tr("Accepted", "Aceptado") if candidate.get("Status") == "ACCEPTED" else tr("Rejected", "Rechazado")
                values = (tr("Included", "Incluido") if included else tr("Excluded", "Excluido"), original,
                          candidate.get("Candidate Product") or "", money(candidate.get("Chosen Price")),
                          candidate.get("Normalized kg") or "—", money(self.session.candidate_unit_price(candidate)),
                          candidate.get("Reason") or "")
                kwargs = dict(values=values, tags=("included" if included else "excluded",))
                if tree.exists(str(index)):
                    tree.item(str(index), **kwargs)
                else:
                    tree.insert("", "end", iid=str(index), **kwargs)
            column, reverse = self.sorts[store]
            if column:
                present = [i for i in visible if self.sort_value(i, column) is not None]
                missing = [i for i in visible if self.sort_value(i, column) is None]
                visible = sorted(present, key=lambda i: self.sort_value(i, column), reverse=reverse) + missing
            tree.set_children("", *visible)
            tree.selection_set([i for i in selected if i in visible])
            self.notebook.tab(self.tabs[store], text=f"{self.store_names[store]} ({count}/{total})")
        try:
            reviewed = self.session.preview_candidates(self.key, self.overrides)
            row = reviewed["row"]
            price = money(row.get(PRICE))
            prior = money(self.session.items[self.key]["row"].get(PRICE))
            self.preview_label.configure(text=tr(
                f"Proposal: {prior} → {price} · {row['Accepted Count']} listings · {row['Store Count']} supermarkets",
                f"Propuesta: {prior} → {price} · {row['Accepted Count']} productos · {row['Store Count']} supermercados"))
            if row.get(PRICE) is None:
                self.preview_label.configure(text=tr("No candidates included — applying will clear the proposed price.",
                                                     "No hay candidatos incluidos; aplicar quitará el precio propuesto."))
            self.apply_button.configure(state="normal")
        except ValueError as exc:
            self.preview_label.configure(text=str(exc))
            self.apply_button.configure(state="disabled")
        self.show_selection()
        self.undo_button.configure(state="normal" if self.undo_stack else "disabled")

    def show_selection(self, event=None):
        tree = self.active_tree()
        selected = tree.selection() if tree is not None else ()
        self.visible_label.configure(text=self.tr(
            f"Showing: {len(tree.get_children()) if tree is not None else 0} · Selected: {len(selected)}",
            f"Visibles: {len(tree.get_children()) if tree is not None else 0} · Seleccionados: {len(selected)}"))
        self.include_button.configure(state="normal" if selected else "disabled")
        self.exclude_button.configure(state="normal" if selected else "disabled")
        self.link_button.configure(state="disabled")
        if len(selected) == 1:
            candidate = self.candidates[int(selected[0])]
            detail = f"{candidate.get('Candidate Product')} · SKU: {candidate.get('SKU') or '—'}\n{candidate.get('Reason') or ''}"
            if self.session.candidate_unit_price(candidate) is None:
                detail += self.tr("\nCannot include: usable price or package size is missing.",
                                  "\nNo se puede incluir: falta precio o tamaño de paquete válido.")
            self.selection_label.configure(text=detail)
            if str(candidate.get("Product URL") or "").startswith(("https://", "http://")):
                self.link_button.configure(state="normal")
        elif tree is not None and not tree.get_children():
            self.selection_label.configure(text=self.tr("No listings match these filters, or no candidates were saved for this supermarket.",
                                                       "Ningún producto coincide con los filtros o no se guardaron candidatos de este supermercado."))
        else:
            self.selection_label.configure(text=self.tr(
                "Select listings to include or exclude. Ctrl/Shift selects multiple listings. Only saved search candidates are shown.",
                "Seleccione productos para incluir o excluir. Ctrl/Mayús permite seleccionar varios. Solo se muestran candidatos guardados de la búsqueda."))

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
            self.undo_stack.append(dict(self.overrides))
            self.overrides.update(changes)
        self.refresh()
        if advance:
            last = max(order.index(i) for i in selected)
            following = order[last + 1:] + order[:last + 1]
            next_key = next((i for i in following if i not in selected and tree.exists(i)), None)
            tree.selection_set([next_key] if next_key else [])
            if next_key:
                tree.focus(next_key)
                tree.see(next_key)
            self.show_selection()

    def reset(self):
        if self.overrides:
            self.undo_stack.append(dict(self.overrides))
        self.overrides = {}
        self.refresh()

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
        return normalize(self.search.get()) in normalize(text)

    def clear_filters(self):
        self.search.set("")
        self.filter.set(self.filter_values[0])
        self.original_filter.set(self.original_values[0])

    def sort_value(self, index, column):
        candidate = self.candidates[int(index)]
        if column == "used":
            return self.session.candidate_accepted(self.key, int(index), self.overrides)
        if column == "original":
            return candidate.get("Status") == "ACCEPTED"
        if column == "unit":
            return self.session.candidate_unit_price(candidate)
        field = {"name": "Candidate Product", "price": "Chosen Price", "size": "Normalized kg", "reason": "Reason"}[column]
        return number(candidate.get(field)) if column in ("price", "size") else normalize(candidate.get(field) or "")

    def sort_by(self, store, column):
        old, reverse = self.sorts[store]
        self.sorts[store] = (column, not reverse if old == column else False)
        for key, label in self.column_labels.items():
            arrow = (" ↓" if self.sorts[store][1] else " ↑") if key == column else ""
            self.trees[store].heading(key, text=label + arrow)
        self.refresh()

    def undo(self):
        if self.undo_stack:
            self.overrides = self.undo_stack.pop()
            self.refresh()

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
            selected = tree.selection()
            self.choose(not all(self.session.candidate_accepted(self.key, int(i), self.overrides) for i in selected))
        elif key == "o":
            self.open_product()
        else:
            return
        return "break"

    def tab_changed(self, event=None):
        self.drag_end()
        self.show_selection()

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

    def destroy(self):
        from price_robot_ui import _SCROLL_VIEWS, _SCROLL_REMAINDER
        self.drag_end()
        for tree in self.trees.values():
            _SCROLL_VIEWS.pop(str(tree), None)
            _SCROLL_REMAINDER.pop(str(tree), None)
        super().destroy()

    def open_product(self):
        tree = self.active_tree()
        if tree is not None and len(tree.selection()) == 1:
            url = str(self.candidates[int(tree.selection()[0])].get("Product URL") or "")
            if url.startswith(("https://", "http://")):
                webbrowser.open(url)

    def apply(self):
        try:
            self.session.apply_candidates(self.key, self.overrides)
        except Exception as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)
            return
        self.review._detail_signature = None
        self.review.refresh()
        self.destroy()
