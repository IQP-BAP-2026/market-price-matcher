"""Hidden-window integration checks; requires a desktop-capable Python/Tk install."""
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_price_review
from price_review_ui import ReviewWindow
import price_robot_ui as app_ui


class RuntimeEstimateTests(unittest.TestCase):
    def test_observed_full_catalog_and_worker_scaling(self):
        self.assertEqual(app_ui.estimate_run_seconds(5440, 100), 360)
        self.assertEqual(app_ui.estimate_run_seconds(2720, 100), 180)
        self.assertEqual(app_ui.estimate_run_seconds(5440, 50), 720)
        self.assertGreater(app_ui.estimate_run_seconds(5440, 8), app_ui.estimate_run_seconds(5440, 100))
        self.assertEqual(app_ui.estimate_run_seconds(0, 100), 0)

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
                              set_status=Mock(), call_ui=callbacks.append)
        with patch.object(app_ui.threading, "Thread") as thread, \
             patch("price_review.ReviewSession") as session, \
             patch("price_review_ui.ReviewWindow") as window:
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


class ReviewUITests(unittest.TestCase):
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
            window.full_evidence.set(True)
            window.include_unchanged.set(True)
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
                self.assertTrue(window.full_evidence.get())
                self.assertTrue(window.include_unchanged.get())
                self.assertEqual(session.items["001"]["decision"], "accepted")
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
            self.assertGreaterEqual(window.details.winfo_height(), window.body_font.metrics("linespace"))
            window.details.configure(state="normal")
            window.details.insert("end", "\n".join(f"Evidence {n}" for n in range(80)))
            window.details.configure(state="disabled")
            root.update()
            before = window.details.yview()[0]
            window.details.event_generate("<MouseWheel>", delta=-120)
            root.update()
            self.assertGreater(window.details.yview()[0], before)
            window.tree.xview_moveto(1)
            root.update()
            window.paint_percent_cells()
            visible = [label for label in window._percent_labels if label.winfo_manager()]
            self.assertTrue(visible, (window.geometry(), window.unit, window.panes.winfo_geometry(), window.panes.sash_coord(0), [(w.winfo_class(), w.winfo_geometry(), w.winfo_reqheight()) for w in window.tree.master.winfo_children()]))
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
                self.assertEqual(len(window.panes.panes()), 2)
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
                self.assertIn("Bath mat", window.details.get("1.0", "end"))
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
            with patch.object(app_ui.App, "load_options"), patch.object(app_ui.App, "load_problems"), \
                 patch.object(app_ui, "warm_products_cache"), patch.object(app_ui.Settings, "load"), \
                 patch.object(app_ui.Settings, "save"):
                app_ui.load_code_defaults()
                app = app_ui.App(root)
                root.update_idletasks()
                self.assertEqual(app.settings.matcher["PRICE_CHANGE_REVIEW_THRESHOLD"], .20)
                self.assertTrue(callable(app.open_review))
                app.products_var.set(str(fixture.template))
                app.settings.run["output_dir"] = str(fixture.root)
                app.mode_var.set("test")
                app.limit_var.set("2")
                app.type_var.set("Tipo A seco")
                app.contains_var.set("ignored in quick test")
                app._opts_state = "ok"
                app._rows = [(str(n), "rice", kind, app_ui.norm(kind)) for n, kind in enumerate(
                    ("Tipo B seco", "Tipo A seco", "Tipo B seco", "Tipo A seco", "Tipo A seco"))]
                self.assertEqual(app.matching_count(), 2)
                cmd = app.build_command()
                self.assertEqual(cmd[cmd.index("--type") + 1], "Tipo A seco")
                self.assertEqual(cmd[cmd.index("--limit") + 1], "2")
                self.assertNotIn("--contains", cmd)
        finally:
            for job in root.tk.call("after", "info"):
                root.after_cancel(job)
            root.destroy()
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
