"""Hidden-window integration checks; requires a desktop-capable Python/Tk install."""
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_price_review
from price_review_ui import ReviewWindow
import price_robot_ui as app_ui


def make_products_sheet(path, drop=()):
    """A products workbook with every required column (minus `drop`)."""
    from openpyxl import Workbook
    from current_prices import PRODUCT_REQUIRED_COLUMNS
    headers = [c for c in ("ERP Id (QBO)",) + PRODUCT_REQUIRED_COLUMNS if c not in drop]
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    ws.append(["x"] * len(headers))
    wb.save(path)
    wb.close()
    return path


class InputColumnTests(unittest.TestCase):
    def test_search_needs_all_required_columns(self):
        import tempfile
        from pathlib import Path
        from current_prices import product_columns_missing, current_prices_columns_missing
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            good = make_products_sheet(tmp / "good.xlsx")
            bad = make_products_sheet(tmp / "bad.xlsx", drop=("Unidad de Peso en KG", "Categoria RepTrim"))
            self.assertEqual(product_columns_missing(good), [])
            self.assertEqual(product_columns_missing(bad), ["Unidad de Peso en KG", "Categoria RepTrim"])
            salesforce = tmp / "sf.csv"
            salesforce.write_text("ProductCode,Id,UnitPrice\n001,01uA,10\n", encoding="utf-8")
            legacy = tmp / "legacy.csv"
            legacy.write_text("Código de producto,Nombre del producto,Precio de lista\n001,Rice,10\n", encoding="utf-8")
            no_price = tmp / "no_price.csv"
            no_price.write_text("ProductCode,Id\n001,01uA\n", encoding="utf-8")
            self.assertEqual(current_prices_columns_missing(salesforce), [])
            self.assertEqual(current_prices_columns_missing(legacy), ["Id"])      # old BAP file: no Salesforce Id
            self.assertEqual(current_prices_columns_missing(no_price), ["UnitPrice / Precio de lista"])
            self.assertIsNone(app_ui.input_files_problem(str(good), str(salesforce)))
            self.assertIn("Id", app_ui.input_files_problem(str(good), str(legacy)))
            blank_ids = tmp / "blank_ids.csv"
            blank_ids.write_text("ProductCode,Id,UnitPrice\n001,,10\n", encoding="utf-8")
            self.assertIn("Id", app_ui.input_files_problem(str(good), str(blank_ids)))
            self.assertIn("Categoria RepTrim", app_ui.input_files_problem(str(bad), str(salesforce)))
            self.assertIn("UnitPrice", app_ui.input_files_problem(str(good), str(no_price)))
            dupes = tmp / "dupes.csv"
            dupes.write_text("ProductCode,Id,UnitPrice\n001,a,1\n001,b,2\n", encoding="utf-8")
            self.assertIsNotNone(app_ui.input_files_problem(str(good), str(dupes)))

    def test_robot_itself_refuses_products_sheet_without_required_columns(self):
        import sys, tempfile
        from pathlib import Path
        import price_robot
        with tempfile.TemporaryDirectory() as tmp:
            bad = make_products_sheet(Path(tmp) / "bad.xlsx", drop=("Familia de productos",))
            with patch.object(sys, "argv", ["price_robot.py", "--products", str(bad), "--limit", "1"]):
                with self.assertRaisesRegex(ValueError, "Familia de productos"):
                    price_robot.main()


class RuntimeEstimateTests(unittest.TestCase):
    def test_observed_full_catalog_and_worker_scaling(self):
        # both measured runs are reproduced
        self.assertEqual(app_ui.estimate_run_seconds(5440, 100), 360)
        self.assertEqual(app_ui.estimate_run_seconds(80, 6), 47)
        self.assertEqual(app_ui.estimate_run_seconds(2720, 100), 180)
        # more workers help, but with diminishing returns (not proportional)
        fifty = app_ui.estimate_run_seconds(5440, 50)
        self.assertTrue(360 < fifty < 720)
        self.assertGreater(app_ui.estimate_run_seconds(5440, 8), fifty)
        self.assertEqual(app_ui.estimate_run_seconds(0, 100), 0)
        # fewer supermarkets = fewer searches
        self.assertEqual(app_ui.estimate_run_seconds(5440, 100, stores=2), 180)

    def test_default_workers_is_100_and_old_default_is_migrated(self):
        self.assertEqual(app_ui.RUN_DEFAULTS["workers"], 100)
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ui_settings.json"
            with patch.object(app_ui, "SETTINGS_FILE", path):
                for saved, version, expected in ((6, None, 100), (6, 2, 6), (40, None, 40)):
                    data = {"run": {"workers": saved}}
                    if version:
                        data["workers_default_version"] = version
                    path.write_text(json.dumps(data), encoding="utf-8")
                    settings = app_ui.Settings()
                    settings.load()
                    self.assertEqual(settings.run["workers"], expected)
                settings.save()
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["workers_default_version"], 2)

    def test_live_countdown_ignores_startup_time(self):
        import time
        app = SimpleNamespace(total=1000, done=0, settings=SimpleNamespace(run={"workers": 100, "stores": ["a", "b", "c", "d"]}))
        before = app_ui.App.remaining_seconds(app, 0)
        self.assertEqual(before, app_ui.estimate_run_seconds(1000, 100))
        # 30 s spent starting up, then 100 products in 10 s → 900 left at 0.1 s each ≈ 90 s
        app.done, app._rate_start = 100, (time.time() - 10, 0)
        self.assertAlmostEqual(app_ui.App.remaining_seconds(app, 40), 90, delta=2)

    def test_large_run_confirmation_uses_benchmark(self):
        app = SimpleNamespace(proc=None, build_command=lambda: ["python", "price_robot.py"],
                              matching_count=lambda: 5440, mode_var=SimpleNamespace(get=lambda: "all"),
                              settings=SimpleNamespace(run={"workers": 100}))
        with patch.object(app_ui.messagebox, "askyesno", return_value=False) as confirm:
            app_ui.App.start(app)
        self.assertIn("6 min 00 s", confirm.call_args.args[1])


class ReviewLoadingTests(unittest.TestCase):
    def test_review_load_is_deferred_and_window_is_created_on_ui_callback(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        callbacks = []
        app = SimpleNamespace(proc=None, output_path=fixture.results,
                              current_var=SimpleNamespace(get=lambda: str(fixture.template)),
                              products_var=SimpleNamespace(get=lambda: ""),
                              settings=SimpleNamespace(matcher={}), root=Mock(),
                              set_status=Mock(), call_ui=callbacks.append,
                              # the review now opens in the main window's "Review prices" tab
                              tabs=Mock(), review_tab=Mock(), review_host=Mock(winfo_children=lambda: []),
                              review_file_lbl=Mock(), review_other_btn=Mock(), _show_review_placeholder=Mock())
        app._load_review = lambda *a, **k: app_ui.App._load_review(app, *a, **k)
        with patch.object(app_ui.threading, "Thread") as thread, \
             patch("price_review.ReviewSession") as session, \
             patch("price_review_ui.ReviewPanel") as window:
            app_ui.App.open_review(app)
            self.assertTrue(app._review_loading)
            session.assert_not_called()
            window.assert_not_called()
            # Repeated clicks do not start another workbook reader.
            app_ui.App.open_review(app)
            thread.assert_called_once()
            thread.call_args.kwargs["target"]()
            session.assert_called_once()
            window.assert_not_called()
            callbacks.pop()()
            self.assertFalse(app._review_loading)
            self.assertIs(window.call_args.kwargs["session"], session.return_value)
            self.assertIs(app._review_window, window.return_value)
            app.tabs.select.assert_called_with(app.review_tab)


class ReviewUITests(unittest.TestCase):
    def test_calculator_partial_prices_keyboard_save_and_undo(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        root = tk.Tk()
        root.withdraw()
        try:
            window = ReviewWindow(root, fixture.results, fixture.template)
            window.tree.selection_set("001")
            window.on_select()
            original = window.session.items["001"]["decision"]
            self.assertEqual(window.tree_key(SimpleNamespace(state=0, keysym="c", char="c")), "break")
            calculator = window._calculator
            self.assertIsNone(calculator.average)
            self.assertIn("disabled", calculator.use_button.state())
            for inputs, expected in ((("2", "4", "", ""), 3),
                                     (("2", "4", "9", ""), 5),
                                     (("2", "4", "9", "5"), 5),
                                     (("", "", "", "2,50"), 2.5)):
                for variable, value in zip(calculator.values, inputs):
                    variable.set(value)
                self.assertEqual(calculator.average, expected)
            for invalid in ("oops", "0", "-1", "nan", "inf"):
                calculator.values[0].set(invalid)
                self.assertIsNone(calculator.average)
                self.assertIn("disabled", calculator.use_button.state())
            calculator.values[0].set("")
            calculator.attributes("-alpha", 0.0)
            calculator.update()
            calculator.entries[0].focus_force()
            calculator.entries[0].event_generate("<space>")
            calculator.update()
            self.assertEqual(calculator.focus_get(), calculator.entries[1])
            self.assertEqual(calculator.values[0].get(), "")
            calculator.entries[1].event_generate("<space>")
            calculator.update()
            self.assertEqual(calculator.focus_get(), calculator.entries[2])
            calculator.entries[2].event_generate("<space>")
            calculator.update()
            self.assertEqual(calculator.focus_get(), calculator.entries[3])
            calculator.entries[3].focus_force()
            calculator.entries[3].event_generate("<space>")
            calculator.update()
            self.assertEqual(calculator.focus_get(), calculator.entries[0])
            self.assertTrue(calculator.winfo_exists())
            calculator.entries[0].event_generate("<Return>")
            root.update()
            self.assertFalse(calculator.winfo_exists())
            item = window.session.items["001"]
            self.assertEqual((item["decision"], item["price"]), ("manual", 2.5))
            self.assertEqual(window.price.get(), "2.50")
            window.undo()
            self.assertEqual(window.session.items["001"]["decision"], original)
            window.open_calculator()
            window._calculator.values[0].set("99")
            window._calculator.destroy()
            self.assertEqual(window.session.items["001"]["decision"], original)
            window.destroy()
        finally:
            root.destroy()
            fixture.tearDown()

    def test_search_count_refreshes_when_scope_limit_and_filters_change(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(app_ui.App, "load_options"), patch.object(app_ui, "warm_products_cache"):
                app = app_ui.App(root)
            app._rows = [(str(i), "rice" if i < 30 else "beans", "Food", "food") for i in range(50)]
            app._opts_state = "ok"
            app._apply_options()
            app.contains_var.set("")
            app.scope_var.set("first")
            app.limit_var.set("20")
            self.assertEqual(app.matching_count(), 20)
            limited = app.count_lbl.cget("text")
            app.total = app.done = 20  # a completed run must not affect the next run's count
            app.scope_var.set("all")
            self.assertEqual(app.matching_count(), 50)
            self.assertNotEqual(app.count_lbl.cget("text"), limited)
            self.assertEqual(str(app.limit_spin.cget("state")), "disabled")
            app.contains_var.set("rice")
            self.assertEqual(app.matching_count(), 30)
            self.assertIn("30", app.count_lbl.cget("text"))
            app.type_var.set("Other")
            self.assertEqual(app.matching_count(), 0)
            app.clear_filters()
            self.assertEqual(app.matching_count(), 50)
        finally:
            for job in root.tk.call("after", "info"):
                root.after_cancel(job)
            root.destroy()

    def test_language_toggle_preserves_review_and_draft(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        root = tk.Tk()
        root.withdraw()
        try:
            window = ReviewWindow(root, fixture.results, fixture.template)
            window.withdraw()
            self.assertEqual(window.session.lang, "es")
            session = window.session
            window.session.decide(["001"], "accepted")
            window.filter.set(window.filter_values[1])
            window.search.set("Bath")
            window.sort_by("code")
            window.tree.selection_set("003")
            window.tree.focus("003")
            window.show_details()
            window.price.set("4.75")
            window.note.set("Draft note")
            window.attributes("-alpha", 0.0)
            window.deiconify()
            root.update()
            for lang, title, heading in (("en", "Review prices", "Decision"),
                                         ("es", "Revisar precios", "Decisión")):
                toggle = next(label for label in window.language_toggle.winfo_children()
                              if label.cget("text") == lang.upper())
                toggle.event_generate("<Button-1>")
                root.update()
                self.assertIs(window.session, session)
                self.assertEqual(session.lang, lang)
                self.assertIn(title, window.title())
                self.assertEqual(window.tree.heading("status", "text"), heading)
                self.assertEqual(window.tree.selection(), ("003",))
                self.assertEqual(window.tree.get_children(), ("003",))
                self.assertEqual(window.filter.get(), window.filter_values[1])
                self.assertEqual(window.search.get(), "Bath")
                self.assertEqual(window.price.get(), "4.75")
                self.assertEqual(window.note.get(), "Draft note")
                self.assertEqual(session.items["001"]["decision"], "accepted")
            window.destroy()
        finally:
            root.destroy()
            fixture.tearDown()

    def test_decided_products_stay_listed_until_filter_refresh(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        root = tk.Tk()
        root.withdraw()
        try:
            window = ReviewWindow(root, fixture.results, fixture.template)
            window.withdraw()
            window.sort_by("code")
            window.filter.set(window.filter_values[1])   # pending
            window.refresh()
            self.assertEqual(window.tree.get_children(), ("001", "002", "003"))
            window.tree.selection_set("001")
            window.on_select()
            window.decide("accepted")
            self.assertEqual(window.tree.get_children(), ("001", "002", "003"))
            self.assertEqual(window.tree.selection(), ("002",))
            window.decide("rejected")
            self.assertEqual(window.tree.get_children(), ("001", "002", "003"))
            self.assertEqual(window.tree.selection(), ("003",))
            window.filter.set(window.filter_values[1])
            window.refresh()   # choosing the filter again (or "Refresh list") applies it
            self.assertEqual(window.tree.get_children(), ("003",))
            window.destroy()
        finally:
            root.destroy()
            fixture.tearDown()

    def test_clicking_another_product_saves_typed_price(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        root = tk.Tk()
        root.withdraw()
        try:
            window = ReviewWindow(root, fixture.results, fixture.template)
            window.withdraw()
            window.sort_by("code")
            self.assertEqual(window.tree["columns"], ("score", "code", "name", "current", "new", "percent", "status"))
            window.tree.selection_set("001")
            window.on_select()
            window.price.set("7.25")
            window.tree.selection_set("002")
            window.on_select()
            item = window.session.items["001"]
            self.assertEqual((item["decision"], item["price"]), ("manual", 7.25))
            self.assertEqual(window.tree.set("001", "new"), "$7.25")
            self.assertEqual(window.tree.selection(), ("002",))
            # untouched or unusable prices are not saved when moving on
            before = dict(window.session.items["002"])
            window.tree.selection_set("003")
            window.on_select()
            self.assertEqual(window.session.items["002"]["decision"], before["decision"])
            window.price.set("abc")
            window.tree.selection_set("001")
            window.on_select()
            self.assertEqual(window.session.items["003"]["decision"], "pending")
            # redrawing the list while staying on a product keeps the draft unsaved
            window.price.set("9.99")
            window.refresh()
            window.on_select()
            self.assertEqual(window.session.items["001"]["price"], 7.25)
            self.assertEqual(window.price.get(), "9.99")
            window.destroy()
        finally:
            root.destroy()
            fixture.tearDown()

    def test_fast_decisions_price_edit_drag_and_categories(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        for row, query, kind in zip(fixture.rows, ("arroz premium", "salsa tomate", "tapete"), ("Tipo A seco", "Tipo A seco", "Tipo B seco")):
            row.update({"Generated Queries": query, "Sub-familia de Productos": kind})
        fixture.write_results()
        root = tk.Tk()
        root.withdraw()
        try:
            window = ReviewWindow(root, fixture.results, fixture.template)
            window.withdraw()
            window.sort_by("code")
            window.tree.selection_set("001")
            window.show_details()
            window.tree_key(SimpleNamespace(state=0, keysym="7", char="7"))
            window.price.set("7.25")
            self.assertEqual(window.metrics["percent"].cget("text"), "-27.5%")
            window.manual()
            self.assertEqual(window.session.items["001"]["price"], 7.25)
            self.assertEqual(window.session.items["001"]["note"], "")
            self.assertEqual(window.tree.selection(), ("002",))
            window.tree_key(SimpleNamespace(state=0, keysym="r", char="r"))
            self.assertEqual(window.tree.selection(), ("003",))
            window.price.set("invalid")
            with patch("price_review_ui.messagebox.showerror") as error:
                window.manual()
                error.assert_called_once()
            self.assertEqual(window.tree.selection(), ("003",))
            window.product_type.set("Tipo A seco")
            window.refresh()
            self.assertEqual(window.tree.get_children(), ("001", "002"))
            window.category_value.set("salsa tomate")
            window.refresh()
            self.assertEqual(window.tree.get_children(), ("002",))
            window.clear_categories()
            window._drag_anchor = "001"
            window._drag_base = set()
            with patch.object(window.tree, "identify_row", return_value="003"), patch.object(window.tree, "winfo_height", return_value=400):
                window.drag_move(SimpleNamespace(y=150))
            self.assertEqual(set(window.tree.selection()), {"001", "002", "003"})
            window.drag_end()
            window.filter.set(window.filter_values[1])
            window.refresh()
            self.assertEqual(window.tree.get_children(), ("003",))
            window.tree.selection_set("003")
            window.show_details()
            window.price.set("2")
            window.manual()
            self.assertEqual(window.tree.selection(), ())
            self.assertEqual(window.tree.get_children(), ("003",))   # stays until the list is refreshed
            window.refresh()
            self.assertEqual(window.tree.get_children(), ())
            window.session.decide(["003"], "pending")
            window.session.items["003"]["row"][test_price_review.PRICE] = 2.345
            window.refresh()
            window.tree.selection_set("003")
            window.show_details()
            window.decide("accepted")
            self.assertEqual(window.session.items["003"]["decision"], "accepted")
            window.destroy()
        finally:
            root.destroy()
            fixture.tearDown()

    def test_visible_percent_cells_and_drag_events(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        root = tk.Tk()
        root.withdraw()
        try:
            window = ReviewWindow(root, fixture.results, fixture.template)
            window.attributes("-alpha", 0.0)
            window.deiconify()
            window.sort_by("code")
            root.after(100, root.quit)
            root.mainloop()
            window.toggle_categories()
            root.update()
            self.assertLessEqual(window.category_box.winfo_x() + window.category_box.winfo_width(), window.winfo_width())
            for child in window.category_box.winfo_children():
                self.assertGreater(child.winfo_width(), 1)
                self.assertLessEqual(child.winfo_x() + child.winfo_width(), window.category_box.winfo_width())
            self.assertLessEqual(window.categories_button.winfo_rootx() + window.categories_button.winfo_width(), window.winfo_rootx() + window.winfo_width())
            window.toggle_categories()
            # the product list gets the spare height; the price boxes stay fully visible below it
            self.assertGreater(window.tree.winfo_height(), window.price_entry.winfo_height() * 3)
            self.assertLessEqual(window.price_entry.winfo_rooty() + window.price_entry.winfo_height(),
                                 window.winfo_rooty() + window.winfo_height())
            window.tree.xview_moveto(1)
            root.update()
            window.paint_percent_cells()
            visible = [label for label in window._percent_labels if label.winfo_manager()]
            self.assertTrue(visible, (window.geometry(), window.unit, [(w.winfo_class(), w.winfo_geometry(), w.winfo_reqheight()) for w in window.tree.master.winfo_children()]))
            self.assertTrue(all(str(label.cget("font")) == str(window.heading_font) for label in visible))
            first = window.tree.bbox("001", "percent")
            last = window.tree.bbox("003", "percent")
            self.assertTrue(first)
            x = first[0] + 5
            window.tree.event_generate("<ButtonPress-1>", x=x, y=first[1] + first[3] // 2)
            target_y = last[1] + last[3] // 2 if last else window.tree.winfo_height() + 5
            window.tree.event_generate("<B1-Motion>", x=x, y=target_y)
            if not last:
                root.after(250, root.quit)
                root.mainloop()
            window.tree.event_generate("<ButtonRelease-1>", x=x, y=target_y)
            self.assertEqual(set(window.tree.selection()), {"001", "002", "003"})
            window.destroy()
        finally:
            for job in root.tk.call("after", "info"):
                root.after_cancel(job)
            root.destroy()
            fixture.tearDown()

    def test_table_geometry_tracks_display_scaling(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        root = tk.Tk()
        root.withdraw()
        try:
            for scaling in (1.333, 2.0, 2.667):
                root.tk.call("tk", "scaling", scaling)
                window = ReviewWindow(root, fixture.results, fixture.template)
                window.withdraw()
                root.update_idletasks()
                style = app_ui.ttk.Style(root)
                self.assertGreater(int(style.lookup("Review.Treeview", "rowheight")), window.body_font.metrics("linespace"))
                for column in window.tree["columns"]:
                    heading = window.tree.heading(column, "text")
                    self.assertGreaterEqual(int(window.tree.column(column, "minwidth")), window.heading_font.measure(heading))
                window.destroy()
        finally:
            for job in root.tk.call("after", "info"):
                root.after_cancel(job)
            root.destroy()
            fixture.tearDown()

    def test_review_controls_in_both_languages(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        root = tk.Tk()
        root.withdraw()
        try:
            for lang in ("en", "es"):
                window = ReviewWindow(root, fixture.results, fixture.template, lang=lang)
                window.withdraw()
                root.update_idletasks()
                self.assertEqual(len(window.tree.get_children()), 3)
                window.tree.selection_set("003")
                window.show_details()
                self.assertIn("Bath mat", window.selected_label.cget("text"))
                window.price.set("4.50")
                window.note.set("Confirmed")
                window.manual()
                self.assertEqual(window.session.items["003"]["decision"], "manual")
                window.filter.set(window.filter_values[2])
                window.refresh()
                self.assertIn("003", window.tree.get_children())
                window.search.set("no such product")
                self.assertFalse(window.tree.get_children())
                window.destroy()
        finally:
            root.destroy()
            fixture.tearDown()

    def test_main_app_constructs_with_review_entry_points(self):
        fixture = test_price_review.SessionTests()
        fixture.setUp()
        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(app_ui.App, "load_options"), \
                 patch.object(app_ui, "warm_products_cache"), patch.object(app_ui.Settings, "load"), \
                 patch.object(app_ui.Settings, "save"):
                app_ui.load_code_defaults()
                app = app_ui.App(root)
                root.update_idletasks()
                self.assertEqual(app.settings.matcher["PRICE_CHANGE_REVIEW_THRESHOLD"], .20)
                self.assertTrue(callable(app.open_review))
                products = make_products_sheet(fixture.root / "products.xlsx")
                app.products_var.set(str(products))
                app.current_var.set(str(fixture.template))   # current prices are now required
                app.settings.run["output_dir"] = str(fixture.root)
                app.scope_var.set("first")
                app.limit_var.set("2")
                app.type_var.set("Tipo A seco")
                app.contains_var.set("rice")   # filters and the amount now combine
                app._opts_state = "ok"
                app._rows = [(str(n), "rice", kind, app_ui.norm(kind)) for n, kind in enumerate(
                    ("Tipo B seco", "Tipo A seco", "Tipo B seco", "Tipo A seco", "Tipo A seco"))]
                self.assertEqual(app.matching_count(), 2)
                cmd = app.build_command()
                self.assertEqual(cmd[cmd.index("--type") + 1], "Tipo A seco")
                self.assertEqual(cmd[cmd.index("--limit") + 1], "2")
                self.assertEqual(cmd[cmd.index("--contains") + 1], "rice")
                app.scope_var.set("all")
                self.assertEqual(app.matching_count(), 3)
                self.assertNotIn("--limit", app.build_command())
        finally:
            for job in root.tk.call("after", "info"):
                root.after_cancel(job)
            root.destroy()
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
