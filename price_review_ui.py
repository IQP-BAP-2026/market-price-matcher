"""Human verification step following the scraper/matcher desktop workflow."""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk, messagebox, filedialog

from price_review import ReviewSession, PRICE, NAME, number, valid_price
from review_config import PRICE_CHANGE_REVIEW_THRESHOLD, REVIEW_PRICE_DECIMALS
from matcher_core import normalize


class PriceCalculator(tk.Toplevel):
    """Fast manual store entry; blank stores never contribute to the average."""

    def __init__(self, parent, product, apply):
        super().__init__(parent)
        from price_robot_ui import C_BORDER, C_HEADER
        self.tr = parent.tr
        self.apply_price = apply
        self.title(self.tr("Price calculator", "Calculadora de precios"))
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        body = ttk.Frame(self, padding=16, style="Review.TFrame")
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=product, wraplength=480, style="Review.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(body, text=self.tr("Space → next store · Enter → use average · Blank = no price",
                                   "Espacio → siguiente tienda · Enter → usar promedio · Vacío = sin precio"),
                  wraplength=480, style="ReviewMuted.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
        sheet = tk.Frame(body, bg=C_BORDER, padx=1, pady=1)
        sheet.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.values, self.entries = [], []
        for index in range(4):
            sheet.columnconfigure(index, weight=1, uniform="stores")
            tk.Label(sheet, text=self.tr(f"Store {index + 1}", f"Tienda {index + 1}"),
                     bg="#EAF0EA", fg=C_HEADER, font=parent.heading_font, pady=6).grid(
                row=0, column=index, sticky="ew", padx=1, pady=1)
            value = tk.StringVar(self)
            entry = ttk.Entry(sheet, textvariable=value, width=10, justify="right", font=parent.body_font)
            entry.grid(row=1, column=index, sticky="ew", padx=1, pady=1, ipady=6)
            entry.bind("<space>", lambda event, i=index: self.advance(i))
            entry.bind("<Return>", lambda _: self.submit())
            self.values.append(value)
            self.entries.append(entry)
            value.trace_add("write", lambda *_: self.update_average())
        self.summary = ttk.Label(body, style="Review.TLabel", wraplength=480)
        self.summary.grid(row=3, column=0, columnspan=2, sticky="w", pady=12)
        buttons = ttk.Frame(body, style="Review.TFrame")
        buttons.grid(row=4, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text=self.tr("Cancel", "Cancelar"), command=self.destroy).pack(side="left", padx=6)
        self.use_button = ttk.Button(buttons, text=self.tr("Use average", "Usar promedio"),
                                     style="ReviewAccent.TButton", command=self.submit)
        self.use_button.pack(side="left")
        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<Control-Return>", lambda _: self.submit())
        self.update_average()
        self.update_idletasks()
        owner = parent.winfo_toplevel()
        self.geometry(f"+{owner.winfo_rootx() + max(0, (owner.winfo_width() - self.winfo_reqwidth()) // 2)}"
                      f"+{owner.winfo_rooty() + max(0, (owner.winfo_height() - self.winfo_reqheight()) // 2)}")
        self.grab_set()
        self.entries[0].focus_set()

    def update_average(self):
        prices = []
        self.average = None
        for value in self.values:
            text = value.get().strip()
            if not text:
                continue
            price = number(text.replace(",", "."))
            if not valid_price(price):
                self.summary.configure(text=self.tr("Enter a positive price or leave the store blank.",
                                                    "Ingrese un precio positivo o deje la tienda vacía."))
                self.use_button.state(["disabled"])
                return
            prices.append(price)
        if prices:
            self.average = round(sum(p / len(prices) for p in prices), REVIEW_PRICE_DECIMALS)
            self.summary.configure(text=self.tr(
                f"Average: ${self.average:.{REVIEW_PRICE_DECIMALS}f} · {len(prices)} stores",
                f"Promedio: ${self.average:.{REVIEW_PRICE_DECIMALS}f} · {len(prices)} tiendas"))
        else:
            self.summary.configure(text=self.tr("Enter at least one store price.", "Ingrese el precio de al menos una tienda."))
        self.use_button.state(["!disabled"] if self.average is not None else ["disabled"])

    def advance(self, index):
        text = self.values[index].get().strip()
        if text and not valid_price(number(text.replace(",", "."))):
            self.entries[index].focus_set()
            self.entries[index].selection_range(0, "end")
        else:
            following = self.entries[(index + 1) % len(self.entries)]
            following.focus_set()
            following.selection_range(0, "end")
        return "break"

    def submit(self):
        if self.average is not None:
            self.apply_price(self.average)
            self.destroy()
        return "break"


class _ReviewView:
    """The review screen. Used as its own window (ReviewWindow) or as a tab inside the main window (ReviewPanel)."""
    embedded = False

    def __init__(self, parent, results, template, settings=None, products=None, lang="es", session=None):
        # Load before constructing a window so a bad workbook cannot leave an empty window.
        self.session = session if session is not None else ReviewSession(results, template, settings, products, lang)
        super().__init__(parent)
        self._build()
        if self.session.archived_review:
            messagebox.showinfo(self.window_title(), self.tr("The input files changed. Previous decisions were archived; this review starts pending.\n",
                                                "Los archivos cambiaron. Se archivaron las decisiones anteriores; esta revisión empieza pendiente.\n") +
                                str(self.session.archived_review), parent=self)

    def window_title(self):
        return self.tr("Review prices · Human verification", "Revisar precios · Verificación humana")

    def _build(self):
        self.tr = lambda en, es: es if self.session.lang == "es" else en
        tr = self.tr
        self.sort_key, self.sort_reverse = "score", False
        self._rendered = {}
        self._detail_signature = None
        self._drag_anchor = None
        self._drag_timer = None
        self._percent_labels = []
        self._paint_job = None
        self.price = tk.StringVar()
        self.note = tk.StringVar()
        from price_robot_ui import C_BG, C_CARD, C_TEXT, C_MUTED, C_ACCENT, C_HEADER, C_BORDER, FONT, register_scroll, on_mouse_wheel, fit_window, work_area
        self.configure(background=C_BG)
        self.body_font = tkfont.Font(self, family=FONT, size=10)
        self.heading_font = tkfont.Font(self, family=FONT, size=10, weight="bold")
        # Tk fonts scale with Windows DPI; Treeview row heights and widths do not.
        # Derive geometry from the actual rendered font, rather than fixed pixels.
        self.unit = self.body_font.metrics("linespace")
        gap = max(8, self.unit // 2)
        style = ttk.Style(self)
        style.configure("Review.Treeview", font=self.body_font, rowheight=self.unit + gap,
                        background=C_CARD, fieldbackground=C_CARD, foreground=C_TEXT,
                        borderwidth=0, relief="flat")
        style.configure("Review.Treeview.Heading", font=self.heading_font, padding=(gap, gap // 3),
                        background="#EAF0EA", foreground=C_HEADER, relief="flat")
        style.map("Review.Treeview", background=[("selected", C_HEADER)], foreground=[("selected", "white")])
        style.configure("Review.TLabel", background=C_CARD, foreground=C_TEXT, font=self.body_font)
        style.configure("ReviewMuted.TLabel", background=C_CARD, foreground=C_MUTED, font=self.body_font)
        style.configure("Review.TFrame", background=C_CARD)
        style.configure("Review.TButton", font=self.body_font, padding=(gap, gap // 2))
        style.configure("ReviewAccent.TButton", font=self.heading_font, padding=(gap, gap // 2),
                        background=C_ACCENT, foreground="white")
        style.map("ReviewAccent.TButton", background=[("active", C_HEADER), ("disabled", "#A5C8A7")],
                  foreground=[("disabled", "white")])
        style.configure("ReviewScore.TRadiobutton", background=C_CARD, foreground=C_MUTED,
                        font=self.body_font, padding=(gap, gap // 2), indicatorrelief="flat")
        style.map("ReviewScore.TRadiobutton", foreground=[("selected", C_ACCENT)],
                  background=[("selected", "#E8F3E8"), ("active", "#F4F6F4")])
        self.option_add("*TCombobox*Listbox.font", self.body_font)
        if not self.embedded:
            self.title(self.window_title())
        scale = self.unit / 17
        _, _, available_width, available_height = work_area(self)
        width = min(round(1250 * scale), available_width - 60)
        height = min(round(850 * scale), available_height - 100)
        self.compact = height / scale < 700
        if not getattr(self, "_built", False) and not self.embedded:
            fit_window(self, 1250, 850, 760, 560)
        self._built = True
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=3)
        self.status_names = {"pending": tr("Pending", "Pendiente"), "accepted": tr("Accepted", "Aceptado"),
                             "manual": tr("Manual price", "Precio manual"), "rejected": tr("Rejected", "Rechazado")}
        top = ttk.Frame(self, padding=gap if self.compact else gap * 2, style="Review.TFrame")
        top.grid(row=0, column=0, sticky="ew", padx=gap * 2, pady=(gap // 2, gap // 2) if self.compact else (gap * 2, gap))
        from price_robot_ui import LangToggle
        if not self.embedded:  # inside the main window, its own ES / EN switch is used
            self.language_toggle = LangToggle(top, C_HEADER, self.set_language, lang=self.session.lang)
            self.language_toggle.pack(side="right", anchor="ne", padx=(gap, 0))
        ttk.Label(top, text=tr("Review prices", "Revisar precios") if self.compact else tr("2 · Verify proposed prices", "2 · Verificar precios propuestos"),
                  font=(FONT, 12 if self.compact else 16, "bold"), foreground=C_HEADER, background=C_CARD).pack(anchor="w", side="left" if self.compact else "top")
        intro = ttk.Label(top, style="ReviewMuted.TLabel", text=tr("Confidence: 1 = low · 5 = high. Check the evidence and approve a price. Decisions save automatically.",
                              "Confianza: 1 = baja · 5 = alta. Revise la evidencia y apruebe un precio. Las decisiones se guardan automáticamente."))
        if not self.compact:
            intro.pack(anchor="w", fill="x", pady=(gap // 2, gap))
        intro.bind("<Configure>", lambda e: intro.configure(wraplength=max(100, e.width)))
        self.progress_label = ttk.Label(top, style="Review.TLabel")
        self.progress_label.pack(anchor="w", fill="x", expand=True, side="left" if self.compact else "top", padx=gap if self.compact else 0)
        self.progress_label.bind("<Configure>", lambda e: self.progress_label.configure(wraplength=max(100, e.width)))
        scores = ttk.Frame(self, padding=(gap, 0 if self.compact else gap // 2), style="Review.TFrame")
        scores.grid(row=1, column=0, sticky="ew", padx=gap * 2)
        ttk.Label(scores, text=tr("Confidence", "Confianza"), style="ReviewMuted.TLabel").pack(side="left", padx=gap)
        self.score = tk.StringVar(value="all")
        for value in ("all", "1", "2", "3", "4", "5"):
            count = sum(str(i["score"]) == value for i in self.session.items.values())
            text = tr("All scores", "Todos") if value == "all" else f"{value}/5 ({count})"
            ttk.Radiobutton(scores, text=text, style="ReviewScore.TRadiobutton", variable=self.score, value=value, command=self.refresh_list).pack(side="left", padx=2)
        filter_card = ttk.Frame(self, padding=(gap, gap // 3 if self.compact else gap), style="Review.TFrame")
        filter_card.grid(row=2, column=0, sticky="ew", padx=gap * 2, pady=(0, gap))
        filters = ttk.Frame(filter_card, style="Review.TFrame")
        filters.pack(fill="x")
        self.filter_values = [tr("All decisions", "Todas las decisiones"), tr("Pending", "Pendientes"),
                              tr("Accepted / manual", "Aceptados / manuales"), tr("Rejected", "Rechazados"),
                              tr("Rejected / no price — enter prices", "Rechazados / sin precio — ingresar precios")]
        self.filter = tk.StringVar(value=self.filter_values[0])
        filters.columnconfigure(2, weight=1)
        selector = ttk.Combobox(filters, textvariable=self.filter, values=self.filter_values, state="readonly", width=22, font=self.body_font)
        selector.grid(row=0, column=0, sticky="ew")
        selector.bind("<<ComboboxSelected>>", lambda _: self.refresh_list())
        ttk.Label(filters, text=tr("Search:", "Buscar:")).grid(row=0, column=1, padx=(gap, 4))
        self.search = tk.StringVar()
        ttk.Entry(filters, textvariable=self.search, width=1, font=self.body_font).grid(row=0, column=2, sticky="ew", padx=(0, gap))
        self.search.trace_add("write", lambda *_: self.refresh())
        self.categories_button = ttk.Button(filters, text=tr("Categories ▾", "Categorías ▾"), style="Review.TButton", command=self.toggle_categories)
        self.categories_button.grid(row=0, column=3, sticky="e")
        ttk.Button(filters, text=tr("Refresh list", "Actualizar lista"), style="Review.TButton",
                   command=self.refresh_list).grid(row=0, column=4, sticky="e", padx=(gap, 0))
        self.filter_card = filter_card
        self.category_box = ttk.Frame(self, padding=gap, style="Review.TFrame", relief="solid", borderwidth=1)
        self.category_fields = {tr("Match group", "Grupo de búsqueda"): "Match group",
                                tr("Product type", "Tipo de producto"): "Sub-familia de Productos",
                                tr("Family", "Familia"): "Familia de productos",
                                tr("Product line", "Línea de producto"): "Linea de producto",
                                "Categoria RepTrim": "Categoria RepTrim", "Tipo GFN": "Tipo GFN"}
        self.category_field = tk.StringVar(value=next(iter(self.category_fields)))
        self.category_value = tk.StringVar(value=tr("All", "Todos"))
        self.product_type = tk.StringVar(value=tr("All types", "Todos los tipos"))
        self.category_box.columnconfigure(1, weight=1)
        category_field = ttk.Combobox(self.category_box, textvariable=self.category_field,
                                      values=list(self.category_fields), state="readonly", width=20)
        category_field.grid(row=0, column=0, sticky="ew", padx=(0, gap))
        category_field.bind("<<ComboboxSelected>>", self.category_changed)
        self.category_combo = ttk.Combobox(self.category_box, textvariable=self.category_value, state="readonly", width=1, height=8)
        self.category_combo.grid(row=0, column=1, sticky="ew")
        self.category_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh_list())
        ttk.Button(self.category_box, text=tr("Sort by category ↕", "Ordenar por categoría ↕"),
                   command=lambda: self.sort_by("category")).grid(row=2, column=0, sticky="w", pady=(gap, 0))
        ttk.Label(self.category_box, text=tr("Product type", "Tipo de producto")).grid(row=1, column=0, sticky="w", pady=(gap, 0))
        types = sorted({i["categories"]["Sub-familia de Productos"] for i in self.session.items.values()} - {""})
        self.type_filter = ttk.Combobox(self.category_box, textvariable=self.product_type,
                                       values=[tr("All types", "Todos los tipos")] + types, state="readonly", width=1, height=8)
        self.type_filter.grid(row=1, column=1, sticky="ew", pady=(gap, 0))
        self.type_filter.bind("<<ComboboxSelected>>", lambda _: self.refresh_list())
        ttk.Button(self.category_box, text=tr("Clear categories", "Limpiar categorías"), command=self.clear_categories).grid(row=2, column=1, sticky="e", pady=(gap, 0))
        self.bind("<Configure>", lambda e: self.position_categories() if e.widget is self and self.category_box.winfo_manager() else None)
        self.category_changed(refresh=False)
        # The product list takes all the spare height; the price boxes sit below it.
        frame = ttk.Frame(self, padding=1, style="Review.TFrame")
        frame.grid(row=3, column=0, sticky="nsew", padx=gap * 2)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = ("score", "code", "name", "current", "new", "percent", "status")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended", height=7, style="Review.Treeview")
        labels = (tr("Confidence", "Confianza"), tr("Code", "Código"), tr("Product", "Producto"),
                  tr("Current", "Actual"), tr("New", "Nuevo"),
                  tr("Change %", "Cambio %"), tr("Decision", "Decisión"))
        self._column_labels = dict(zip(columns, labels))
        for col, label in zip(columns, labels):
            self.tree.heading(col, text=label, command=lambda c=col: self.sort_by(c))
            samples = [label]
            if col == "code":
                samples.extend(self.session.items)
            elif col == "status":
                samples.extend(self.status_names.values())
            elif col in ("current", "new", "percent"):
                samples.append("$99,999.99" if col != "percent" else "+999.9%")
            width = max(self.heading_font.measure(str(text)) for text in samples) + gap * 3
            if col == "name":
                width = self.body_font.measure("M") * 30
            self.tree.column(col, width=width, minwidth=width, stretch=col == "name",
                             anchor="w" if col in ("name", "code", "status") else "e")
            self.tree.heading(col, anchor="w" if col in ("name", "code", "status") else "e")
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=lambda *a: (yscroll.set(*a), self.queue_percent_cells()),
                            xscrollcommand=lambda *a: (xscroll.set(*a), self.queue_percent_cells()))
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Configure>", lambda _: self.queue_percent_cells())
        self.tree.bind("<KeyPress>", self.tree_key)
        self.tree.bind("<ButtonPress-1>", self.drag_start)
        self.tree.bind("<B1-Motion>", self.drag_move)
        self.tree.bind("<ButtonRelease-1>", self.drag_end)
        register_scroll(self.tree, text_lines=True)
        self.tree.bind("<MouseWheel>", on_mouse_wheel)
        self.tree.tag_configure("pending", background="#FFFFFF")
        self.tree.tag_configure("accepted", background="#edf7ee")
        self.tree.tag_configure("manual", background="#eaf2fc")
        self.tree.tag_configure("rejected", background="#fceeee")
        detail_frame = ttk.Frame(self, padding=(gap, gap // 2 if self.compact else gap), style="Review.TFrame")
        detail_frame.grid(row=4, column=0, sticky="ew", padx=gap * 2, pady=(gap, 0))
        evidence_header = ttk.Frame(detail_frame, style="Review.TFrame")
        evidence_header.pack(fill="x", pady=(0, gap // 2))
        self.candidates_button = ttk.Button(evidence_header, text=tr("Choose candidates…", "Elegir candidatos…"),
                                            command=self.open_candidates)
        self.candidates_button.pack(side="right")
        self.selected_label = ttk.Label(evidence_header, text="", font=self.heading_font,
                                        foreground=C_HEADER, background=C_CARD, anchor="w")
        self.selected_label.pack(side="left", fill="x", expand=True)
        comparison = ttk.Frame(detail_frame, style="Review.TFrame")
        comparison.pack(fill="x")
        self.metrics = {}
        for index, (key, label) in enumerate((("current", tr("CURRENT PRICE", "PRECIO ACTUAL")),
                                               ("new", tr("NEW PRICE · ENTER ↵", "PRECIO NUEVO · ENTER ↵")),
                                               ("percent", tr("CHANGE %", "CAMBIO %")))):
            comparison.columnconfigure(index, weight=1, uniform="prices")
            box = tk.Frame(comparison, bg="#F0F5F0", highlightbackground=C_BORDER, highlightthickness=1, padx=gap, pady=gap // 2)
            box.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else gap, 0))
            tk.Label(box, text=label, font=(FONT, 8, "bold"), bg="#F0F5F0", fg=C_MUTED).pack(anchor="w")
            if key == "new":
                price_row = tk.Frame(box, bg="#F0F5F0")
                price_row.pack(fill="x")
                self.price_entry = ttk.Entry(price_row, textvariable=self.price, font=(FONT, 13 if self.compact else 16, "bold"), width=6, justify="right")
                self.price_entry.pack(side="left", fill="x", expand=True)
                self.price_entry.bind("<Return>", lambda _: self.manual())
                self.price_entry.bind("<Escape>", self.cancel_edit)
                self.calculator_button = ttk.Button(price_row, text=tr("Calculator [C]", "Calculadora [C]"),
                                                    command=self.open_calculator)
                self.calculator_button.pack(side="right", padx=(4, 0))
            else:
                value = tk.Label(box, text="—", font=(FONT, 14 if self.compact else 18, "bold"), bg="#F0F5F0", fg=C_HEADER, anchor="e")
                value.pack(fill="x")
                self.metrics[key] = value
        self.price.trace_add("write", lambda *_: self.update_metrics())
        actions = ttk.Frame(frame, padding=(gap, 0 if self.compact else gap), style="Review.TFrame")
        actions.grid(row=2, column=0, columnspan=2, sticky="ew")
        selected_actions = ttk.Frame(actions)
        selected_actions.pack(anchor="w")
        for label, decision in ((tr("Accept [A]", "Aceptar [A]"), "accepted"),
                                (tr("Reject [R]", "Rechazar [R]"), "rejected")):
            ttk.Button(selected_actions, text=label, style="ReviewAccent.TButton" if decision == "accepted" else "Review.TButton", command=lambda d=decision: self.decide(d)).pack(side="left", padx=3)
        self.undo_button = ttk.Button(selected_actions, text=tr("Undo [Ctrl+Z]", "Deshacer [Ctrl+Z]"), style="Review.TButton", command=self.undo)
        self.undo_button.pack(side="left", padx=3)
        self.redo_button = ttk.Button(selected_actions, text=tr("Redo [Ctrl+Y]", "Rehacer [Ctrl+Y]"), style="Review.TButton", command=self.redo)
        self.redo_button.pack(side="left", padx=3)
        # Ctrl+Z / Ctrl+Y work anywhere in the review, not only in the list.
        top = self.winfo_toplevel()
        for sequence, handler in (("<Control-z>", self._undo_key), ("<Control-Z>", self._undo_key),
                                  ("<Control-y>", self._redo_key), ("<Control-Y>", self._redo_key)):
            top.bind(sequence, handler)
        shortcuts = ttk.Label(actions, text=tr("A accept · R reject · C calculator · Type a price + Enter · Ctrl+Z undo · Ctrl+Y redo · Drag to select · Click a heading to sort",
                                   "A aceptar · R rechazar · C calculadora · Escriba precio + Enter · Ctrl+Z deshacer · Ctrl+Y rehacer · Arrastre para seleccionar · Encabezado para ordenar"),
                  style="ReviewMuted.TLabel")
        if not self.compact:
            shortcuts.pack(anchor="w", fill="x", pady=(gap // 2, 0))
        shortcuts.bind("<Configure>", lambda e: shortcuts.configure(wraplength=max(100, e.width)))
        footer = ttk.Frame(self, padding=(gap, gap // 3 if self.compact else gap), style="Review.TFrame")
        footer.grid(row=7, column=0, sticky="ew", padx=gap * 2, pady=(0, gap * 2))
        ttk.Button(footer, text=tr("Export CSV…", "Exportar CSV…"), style="ReviewAccent.TButton", command=self.export).pack(side="right")
        self.refresh()

    def set_language(self, lang):
        if lang not in ("es", "en") or lang == self.session.lang:
            return
        selected, focus = self.tree.selection(), self.tree.focus()
        scroll = self.tree.yview()[0]
        price, note = self.price.get(), self.note.get()
        score, search = self.score.get(), self.search.get()
        decision = self.filter_values.index(self.filter.get())
        field = self.category_fields[self.category_field.get()]
        category = self.category_value.get()
        all_categories = category == self.tr("All", "Todos")
        product_type = self.product_type.get()
        all_types = product_type == self.tr("All types", "Todos los tipos")
        categories_open = bool(self.category_box.winfo_manager())
        sort_key, sort_reverse = self.sort_key, self.sort_reverse
        self._cleanup_views()
        for child in self.winfo_children():
            child.destroy()
        self.session.lang = lang
        self.session.rescore()
        self._build()
        self.score.set(score)
        self.filter.set(self.filter_values[decision])
        self.category_field.set(next(label for label, value in self.category_fields.items() if value == field))
        self.category_changed(refresh=False)
        if not all_categories:
            self.category_value.set(category)
        if not all_types:
            self.product_type.set(product_type)
        self.sort_key, self.sort_reverse = sort_key, not sort_reverse
        self.search.set(search)
        self.sort_by(sort_key)
        self.tree.selection_set(selected)
        if focus:
            self.tree.focus(focus)
        self.show_details()
        self.price.set(price)
        self.note.set(note)
        self.tree.yview_moveto(scroll)
        if categories_open:
            self.update_idletasks()
            self.toggle_categories()

    def toggle_categories(self):
        if self.category_box.winfo_manager():
            self.category_box.place_forget()
        else:
            # Settle the filter row's layout before measuring the popup width.
            self.update_idletasks()
            self.position_categories()
            self.category_box.lift()

    def position_categories(self):
        width = min(self.filter_card.winfo_width(), self.body_font.measure("M") * 60)
        self.category_box.place(x=self.filter_card.winfo_x() + self.filter_card.winfo_width() - width,
                                y=self.filter_card.winfo_y() + self.filter_card.winfo_height(), width=width)

    def category_changed(self, event=None, refresh=True):
        field = self.category_fields[self.category_field.get()]
        values = sorted({i["categories"].get(field, "") for i in self.session.items.values()} - {""}, key=normalize)
        self.category_combo.configure(values=[self.tr("All", "Todos")] + values)
        self.category_value.set(self.tr("All", "Todos"))
        if refresh:
            self.refresh()

    def clear_categories(self):
        self.category_value.set(self.tr("All", "Todos"))
        self.product_type.set(self.tr("All types", "Todos los tipos"))
        self.refresh_list()

    def sort_by(self, column):
        self.sort_reverse = not self.sort_reverse if self.sort_key == column else False
        self.sort_key = column
        for key, label in self._column_labels.items():
            self.tree.heading(key, text=label + ((" ↓" if self.sort_reverse else " ↑") if key == column else ""))
        self.refresh()

    def sort_value(self, pair):
        key, item = pair
        proposed = number(item["row"].get(PRICE))
        price = item["price"] if item["price"] is not None else proposed
        current = item["current"]
        delta = price - current if price is not None and current is not None else None
        values = {"score": item["score"], "code": key, "name": item["row"].get(NAME) or "",
                  "current": current, "new": price,
                  "percent": delta / current if delta is not None and current else None,
                  "status": self.status_names[item["decision"]],
                  "category": item["categories"].get(self.category_fields[self.category_field.get()], "")}
        value = values[self.sort_key]
        return (value is None, normalize(value) if isinstance(value, str) else value,
                normalize(item["row"].get(NAME) or ""), key)

    def update_metrics(self):
        keys = self.tree.selection()
        if len(keys) != 1:
            for metric in self.metrics.values():
                metric.configure(text="—")
            return
        current = self.session.items[keys[0]]["current"]
        new = number(self.price.get())
        self.metrics["current"].configure(text="—" if current is None else f"${current:,.2f}")
        difference = (new - current) / current if new is not None and current and current > 0 else None
        threshold = self.session.settings.get("PRICE_CHANGE_REVIEW_THRESHOLD", PRICE_CHANGE_REVIEW_THRESHOLD)
        self.metrics["percent"].configure(text="—" if difference is None else f"{difference:+.1%}",
                                           fg="#B45309" if difference is not None and abs(difference) > threshold + 1e-12 else "#1F4D2B")

    def cancel_edit(self, event=None):
        self._detail_signature = None
        self.show_details()
        self.tree.focus_set()
        return "break"

    def tree_key(self, event):
        if event.state & 4:  # Ctrl shortcuts (undo/redo) are handled by the window, not price editing.
            return
        if event.keysym.lower() == "c":
            self.open_calculator()
            return "break"
        if event.keysym.lower() in ("a", "r", "return"):
            self.decide("rejected" if event.keysym.lower() == "r" else "accepted")
            return "break"
        if event.char and event.char in "0123456789.," and len(self.tree.selection()) == 1:
            self.price.set(event.char.replace(",", "."))
            self.price_entry.focus_set()
            self.price_entry.icursor("end")
            return "break"

    def drag_start(self, event):
        self.drag_end()
        self._drag_anchor = self.tree.identify_row(event.y) if self.tree.identify_region(event.x, event.y) in ("cell", "tree") else None
        self._drag_base = set(self.tree.selection()) if event.state & 4 else set()

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
        y = self._drag_y
        edge = self.unit * 2
        direction = -1 if y < edge else 1 if y > self.tree.winfo_height() - self.unit else 0
        if direction:
            self.tree.yview_scroll(direction, "units")
            y = edge if direction < 0 else self.tree.winfo_height() - self.unit
            self._drag_timer = self.after(70, self.drag_range)
        target = self.tree.identify_row(y)
        rows = list(self.tree.get_children())
        if not target and direction and rows:
            target = rows[-1] if direction > 0 else rows[0]
        if target in rows and self._drag_anchor in rows:
            first, last = sorted((rows.index(self._drag_anchor), rows.index(target)))
            self.tree.selection_set(list(self._drag_base | set(rows[first:last + 1])))
            self.tree.focus(target)

    def drag_end(self, event=None):
        if self._drag_timer:
            self.after_cancel(self._drag_timer)
            self._drag_timer = None
        self._drag_anchor = None

    def queue_percent_cells(self):
        if not self._paint_job:
            self._paint_job = self.after_idle(self.paint_percent_cells)

    def paint_percent_cells(self):
        """Treeview has row-only fonts; overlay just the visible percentage cells."""
        self._paint_job = None
        visible = []
        rows = set()
        rowheight = int(ttk.Style(self).lookup("Review.Treeview", "rowheight"))
        for y in range(0, self.tree.winfo_height(), max(1, rowheight // 2)):
            key = self.tree.identify_row(y)
            if not key or key in rows:
                continue
            rows.add(key)
            bounds = self.tree.bbox(key, "percent")
            if bounds and bounds[0] >= 0 and bounds[0] + bounds[2] <= self.tree.winfo_width():
                visible.append((key, bounds))
        while len(self._percent_labels) < len(visible):
            label = tk.Label(self.tree, font=self.heading_font, anchor="e", padx=8, borderwidth=0)
            for sequence in ("<ButtonPress-1>", "<ButtonRelease-1>", "<B1-Motion>", "<MouseWheel>"):
                def forward(event, seq=sequence):
                    self.tree.focus_set()
                    args = dict(x=event.x_root - self.tree.winfo_rootx(), y=event.y_root - self.tree.winfo_rooty(), state=event.state)
                    if seq == "<MouseWheel>":
                        args["delta"] = event.delta
                    self.tree.event_generate(seq, **args)
                    return "break"
                label.bind(sequence, forward)
            self._percent_labels.append(label)
        selected = set(self.tree.selection())
        for label, (key, (x, y, width, height)) in zip(self._percent_labels, visible):
            item = self.session.items[key]
            background = "#1F4D2B" if key in selected else {"pending": "#FFFFFF", "accepted": "#edf7ee", "manual": "#eaf2fc", "rejected": "#fceeee"}[item["decision"]]
            label.configure(text=self.tree.set(key, "percent"), bg=background, fg="white" if key in selected else "#1F2A22")
            label.place(x=x, y=y, width=width, height=height)
        for label in self._percent_labels[len(visible):]:
            label.place_forget()

    def _cleanup_views(self):
        from price_robot_ui import _SCROLL_VIEWS, _SCROLL_REMAINDER
        for widget in (self.tree,):
            _SCROLL_VIEWS.pop(str(widget), None)
            _SCROLL_REMAINDER.pop(str(widget), None)
        for job in (self._paint_job, self._drag_timer):
            if job:
                self.after_cancel(job)

    def destroy(self):
        self._cleanup_views()
        super().destroy()

    def run(self, action, advance=None):
        before = list(self.tree.get_children())
        following = []
        if advance:
            positions = [before.index(k) for k in advance if k in before]
            if positions:
                following = before[max(positions) + 1:]
                if self.filter_values.index(self.filter.get()) in (1, 4):
                    following += [k for k in before[:min(positions)] if k not in advance]
        try:
            action()
            # Products already on screen stay listed until the filters are changed or refreshed,
            # so accepting a product under "Pending" doesn't make it vanish.
            self.refresh(keep=before)
            if advance:
                # go to the next product that still needs attention under the current filter
                following = [k for k in following if self.matches_decision_filter(k)]
                next_key = next((key for key in following if self.tree.exists(key)), None)
                self.tree.selection_set([next_key] if next_key else [])
                if next_key:
                    self.tree.focus(next_key)
                    self.tree.see(next_key)
                self.tree.focus_set()
                self.show_details()
        except Exception as exc:
            messagebox.showerror(self.window_title(), str(exc), parent=self)

    def refresh_list(self):
        """Apply the filters again (filter menus, score buttons, "Refresh list") and give the keyboard back
        to the list, so A / R / Enter act on the highlighted product right away."""
        self.refresh()
        rows = self.tree.get_children()
        selected = self.tree.selection()
        if not selected and rows:
            self.tree.selection_set(rows[0])
            selected = (rows[0],)
        if selected:
            self.tree.focus(selected[0])
            self.tree.see(selected[0])
        self.tree.focus_set()
        self.on_select()

    def undo(self):
        self.run(self.session.undo)

    def redo(self):
        self.run(self.session.redo)

    def _undo_key(self, event=None):
        if self.winfo_exists() and self.winfo_viewable():
            self.undo()
            return "break"

    def _redo_key(self, event=None):
        if self.winfo_exists() and self.winfo_viewable():
            self.redo()
            return "break"

    def matches_decision_filter(self, key):
        status = self.session.items[key]["decision"]
        filter_id = self.filter_values.index(self.filter.get())
        if filter_id == 1:
            return status == "pending"
        if filter_id == 2:
            return status in ("accepted", "manual")
        if filter_id == 3:
            return status == "rejected"
        if filter_id == 4:
            return status == "rejected" or not valid_price(self.session.items[key]["row"].get(PRICE)) and status not in ("accepted", "manual")
        return True

    def _passes_filters(self, key, item, field):
        if self.score.get() != "all" and str(item["score"]) != self.score.get():
            return False
        if not self.matches_decision_filter(key):
            return False
        if self.category_value.get() != self.tr("All", "Todos") and item["categories"].get(field) != self.category_value.get():
            return False
        if self.product_type.get() != self.tr("All types", "Todos los tipos") and item["categories"].get("Sub-familia de Productos") != self.product_type.get():
            return False
        name = str(item["row"].get(NAME) or "")
        return normalize(self.search.get()) in normalize(key + " " + name + " " + " ".join(item["categories"].values()))

    def refresh(self, keep=()):
        """Redraw the list. Products in `keep` stay listed even if they no longer match the filters."""
        keep = set(keep)
        selected = self.tree.selection()
        old_order = self.tree.get_children()
        desired = []
        field = self.category_fields[self.category_field.get()]
        for key, item in sorted(self.session.items.items(), key=self.sort_value, reverse=self.sort_reverse):
            status = item["decision"]
            name = str(item["row"].get(NAME) or "")
            if key not in keep and not self._passes_filters(key, item, field):
                continue
            proposed, current = number(item["row"].get(PRICE)), item["current"]
            final = item["price"]
            compare = final if final is not None else proposed
            delta = compare - current if compare is not None and current is not None else None
            money = lambda v: "—" if v is None else f"${v:,.2f}"
            # "New" = the approved price once decided, otherwise the robot's proposal
            values = (f'{item["score"]}/5', key, name, money(current), money(compare),
                      "—" if delta is None or not current else f"{delta/current:+.1%}", self.status_names[status])
            desired.append(key)
            if key not in self._rendered:
                self.tree.insert("", "end", iid=key, values=values, tags=(status,))
            elif self._rendered[key] != values:
                self.tree.item(key, values=values, tags=(status,))
            self._rendered[key] = values
        removed = set(old_order) - set(desired)
        for key in removed:
            self.tree.delete(key)
            self._rendered.pop(key, None)
        if list(self.tree.get_children()) != desired:
            self.tree.set_children("", *desired)
        self.tree.selection_set([k for k in selected if self.tree.exists(k)])
        counts = {s: sum(i["decision"] == s for i in self.session.items.values()) for s in self.status_names}
        category_count = int(self.category_value.get() != self.tr("All", "Todos")) + int(self.product_type.get() != self.tr("All types", "Todos los tipos"))
        self.categories_button.configure(text=self.tr("Categories", "Categorías") + (f" ({category_count})" if category_count else "") + " ▾")
        threshold = self.session.settings.get("PRICE_CHANGE_REVIEW_THRESHOLD", PRICE_CHANGE_REVIEW_THRESHOLD)
        self.progress_label.configure(text=" · ".join(f"{self.status_names[s]}: {n}" for s, n in counts.items()) +
                                      self.tr(f" · Showing: {len(desired)} · Change warning: ±{threshold:.0%}", f" · Visibles: {len(desired)} · Alerta de cambio: ±{threshold:.0%}"))
        if self.compact:
            reviewed = len(self.session.items) - counts["pending"]
            self.progress_label.configure(text=self.tr(f"{reviewed}/{len(self.session.items)} reviewed · {len(desired)} shown",
                                                      f"{reviewed}/{len(self.session.items)} revisados · {len(desired)} visibles"))
        self.undo_button.configure(state="normal" if self.session.undo_stack else "disabled")
        self.redo_button.configure(state="normal" if getattr(self.session, "redo_stack", None) else "disabled")
        self.show_details()
        self.queue_percent_cells()

    def show_details(self, event=None):
        keys = self.tree.selection()
        self.candidates_button.configure(state="normal" if len(keys) == 1 else "disabled")
        self.queue_percent_cells()
        signature = tuple((k, self.session.items[k]["decision"], self.session.items[k]["price"], self.session.items[k]["note"],
                           self.session.items[k]["row"].get(PRICE), tuple(self.session.items[k]["candidate_overrides"].items())) for k in keys)
        if signature == self._detail_signature:
            return
        self._detail_signature = signature
        if len(keys) == 1:
            key = keys[0]
            item = self.session.items[key]
            value = item["price"] if item["price"] is not None else number(self.session.accept_price(key))
            self.price.set("" if value is None else f"{value:.2f}")
            self.note.set(item["note"])
            self._loaded_price = (key, self.price.get())
            self.selected_label.configure(text=f'{item["row"].get(NAME)} · {key} · {item["score"]}/5', foreground="#1F4D2B")
        else:
            self.price.set("")
            self.note.set("")
            self._loaded_price = None
            text = (self.tr(f"{len(keys)} products selected", f"{len(keys)} productos seleccionados") if keys else
                    self.tr("Select a product to enter a price.", "Seleccione un producto para ingresar un precio."))
            self.selected_label.configure(text=text, foreground="#667085")

    def on_select(self, event=None):
        """Selecting another product saves a price typed for the previous one, just like pressing Enter."""
        self.commit_typed_price()
        self.show_details(event)

    def commit_typed_price(self):
        loaded = getattr(self, "_loaded_price", None)
        if not loaded:
            return
        key, shown = loaded
        if self.tree.selection() == (key,):
            return  # still on the same product (e.g. the list was only redrawn)
        typed = self.price.get().strip()
        if typed == shown.strip() or key not in self.session.items:
            return
        self._loaded_price = None
        value = number(typed.replace(",", "."))
        if value is None or not valid_price(value):
            return  # nothing usable typed: leave the product as it was
        self._detail_signature = None
        self.run(lambda: self.session.decide([key], "manual", typed.replace(",", "."), self.note.get()))

    def open_candidates(self):
        keys = self.tree.selection()
        if len(keys) != 1:
            return
        if not self.session.candidates[keys[0]]:
            messagebox.showinfo(self.window_title(), self.tr("No candidate details were saved for this product. Open an Excel results file with a Candidates sheet.",
                                                      "No se guardaron candidatos para este producto. Abra un archivo Excel de resultados con la hoja Candidates."), parent=self)
            return
        from candidate_review_ui import CandidateReviewWindow
        self._candidate_window = CandidateReviewWindow(self, keys[0])

    def open_calculator(self):
        keys = self.tree.selection()
        if len(keys) != 1:
            messagebox.showinfo(self.window_title(), self.tr("Select one product to calculate its price.",
                                                           "Seleccione un producto para calcular su precio."), parent=self)
            return
        key = keys[0]

        def apply(value):
            self.run(lambda: self.session.decide([key], "manual", value, self.note.get()))

        self._calculator = PriceCalculator(self, self.session.items[key]["row"].get(NAME, key), apply)

    def decide(self, decision, visible=False):
        keys = self.tree.get_children() if visible else self.tree.selection()
        if not keys:
            return
        if decision == "accepted" and len(keys) == 1 and not visible:
            # what "Accept" approves: the proposal, or the current BAP price when there is no proposal
            proposal = number(self.session.accept_price(keys[0]))
            typed = number(self.price.get().replace(",", "."))
            if typed is not None and typed != (round(proposal, REVIEW_PRICE_DECIMALS) if proposal is not None else None):
                return self.manual()
        if len(keys) > 1 and not messagebox.askyesno(self.window_title(), self.tr(
                f"Apply '{self.status_names[decision]}' to these {len(keys)} visible/selected products? Existing decisions in this group will be replaced.",
                f"¿Aplicar '{self.status_names[decision]}' a estos {len(keys)} productos visibles/seleccionados? Se reemplazarán sus decisiones anteriores."), parent=self):
            return
        self.run(lambda: self.session.decide(keys, decision), advance=keys if decision != "pending" else None)

    def manual(self):
        keys = self.tree.selection()
        self.run(lambda: self.session.decide(keys, "manual", self.price.get().replace(",", "."), self.note.get()), advance=keys)
        return "break"

    def export(self):
        pending = sum(i["decision"] == "pending" for i in self.session.items.values())
        description = self.tr("Only accepted and manually approved prices will be exported.", "Solo se exportarán precios aceptados o aprobados manualmente.")
        if not messagebox.askyesno(self.window_title(), description + self.tr(f"\nPending products: {pending}. Continue?", f"\nProductos pendientes: {pending}. ¿Continuar?"), parent=self):
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="salesforce_reviewed_prices.csv")
        if path:
            def save():
                count = self.session.export(path)
                messagebox.showinfo(self.window_title(), self.tr(f"Exported {count} products to:\n{path}", f"Se exportaron {count} productos a:\n{path}"), parent=self)
            self.run(save)


class ReviewWindow(_ReviewView, tk.Toplevel):
    """The review as a separate window."""


class ReviewPanel(_ReviewView, tk.Frame):
    """The review inside the main window's "Review prices" tab."""
    embedded = True
