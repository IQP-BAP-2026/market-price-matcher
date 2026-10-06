"""
Robot de Precios / Price Robot — desktop window for Banco de Alimentos Panamá.

Opens a window to run price_robot.py without the command line (Spanish / English).
Does not modify price_robot.py or matcher_core.py: advanced settings are applied
only for each run, through robot_launcher.py.

Open by double-clicking launch.bat, or:
    py price_robot_ui.py
"""
from __future__ import annotations

import csv
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from review_config import PRICE_CHANGE_REVIEW_THRESHOLD

from app_runtime import DATA_DIR, OUTPUT_DIR, cache_file, is_frozen, worker_command

BASE_DIR = DATA_DIR
SETTINGS_FILE = BASE_DIR / "ui_settings.json"
OPTIONS_CACHE = cache_file("ui_products_cache.json")
ERROR_LOG = BASE_DIR / "ui_errors.log"   # remembers product lists so filters load instantly
DEFAULT_PRODUCTS = BASE_DIR / "products.xlsx"
REQUIREMENTS = BASE_DIR / "requirements.txt"


STORES = [
    ("super99", "Super 99"),
    ("superxtra", "Super Xtra"),
    ("rey", "Supermercados Rey"),
    ("ribasmith", "Riba Smith"),
]

# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------
LANG = "es"  # "es" or "en"

STRINGS = {
    # main window
    "app_title": ("Robot de Precios", "Price Robot"),
    "app_subtitle": ("Banco de Alimentos Panamá", "Banco de Alimentos Panamá"),
    "card_products": ("Archivos", "Files"),
    "products_label": ("Productos:", "Products:"),
    "current_label": ("Precios actuales:", "Current prices:"),
    "perf_check": ("Crear el análisis de desempeño", "Create performance analysis"),
    "pick_current_title": ("Elegir archivo de precios actuales", "Choose current prices file"),
    "err_current": ("Elija el archivo de precios actuales de Salesforce con «Buscar…» (Excel o CSV con ProductCode, Id y UnitPrice).",
                    "Choose the Salesforce current-prices file with “Browse…” (Excel or CSV with ProductCode, Id and UnitPrice)."),
    "err_products_columns": ("Al archivo de productos le faltan columnas que el robot necesita:\n\n{cols}\n\n{path}",
                             "The products file is missing columns the robot needs:\n\n{cols}\n\n{path}"),
    "err_current_columns": ("Al archivo de precios actuales le faltan columnas que el robot necesita:\n\n{cols}\n\n"
                            "Use el archivo de precios descargado de Salesforce, "
                            "con las columnas ProductCode, Id y UnitPrice. Sin el Id de Salesforce los precios revisados no se "
                            "pueden exportar.\n\n{path}",
                            "The current-prices file is missing columns the robot needs:\n\n{cols}\n\n"
                            "Use the pricebook file downloaded from Salesforce, "
                            "with the ProductCode, Id and UnitPrice columns. Without the Salesforce Id the reviewed prices "
                            "can't be exported.\n\n{path}"),
    "err_file_read": ("No se pudo leer el archivo:\n{path}\n\n{error}", "The file could not be read:\n{path}\n\n{error}"),
    "browse": ("Buscar…", "Browse…"),
    "all": ("Todos", "All"),
    "card_which": ("¿Qué productos buscar?", "Which products?"),
    "products_word": ("productos", "products"),
    "qty_label": ("Cantidad:", "How many:"),
    "qty_all": ("Todos los productos", "All products"),
    "qty_first": ("Solo los primeros", "Only the first"),
    "filters_label": ("Filtros:", "Filters:"),
    "type_short": ("Tipo:", "Type:"),
    "contains_short": ("Nombre contiene:", "Name contains:"),
    "clear_filters": ("Limpiar filtros", "Clear filters"),
    "will_search": ("Se buscarán {n} de {total} productos", "{n} of {total} products will be searched"),
    "will_search_none": ("Ningún producto coincide con estas opciones.", "No products match these options."),
    "count_waiting": ("Elija el archivo de productos para ver cuántos productos se buscarán.",
                      "Choose the products file to see how many products will be searched."),
    "confirm_many": ("Se van a buscar {n} productos. Puede tardar aproximadamente {t}.\n\n¿Continuar?",
                     "{n} products will be searched. This may take about {t}.\n\nContinue?"),
    "name_hint": ("ej. leche, arroz, agua", "e.g. leche, arroz, agua"),
    "count_bad_limit": ("Escriba cuántos productos buscar (un número mayor que 0).",
                        "Type how many products to search (a number greater than 0)."),
    "count_loading": ("Cargando el archivo de productos…", "Loading the products file…"),
    "count_missing": ("No se encontró el archivo de productos.", "The products file was not found."),
    "count_failed": ("No se pudo leer el archivo de productos.", "The products file could not be read."),
    "count_python": ("Faltan componentes de Python para leer el archivo de productos.",
                     "Python components are missing to read the products file."),
    "all_types": ("(Todos los tipos)", "(All types)"),
    "loading": ("cargando…", "loading…"),
    "file_not_found_short": ("archivo no encontrado", "file not found"),
    "advanced_btn": ("⚙  Configuración avanzada…", "⚙  Advanced settings…"),
    "badge_custom": ("● {n} ajuste(s) personalizado(s)", "● {n} custom setting(s)"),
    "badge_default": ("Valores predeterminados", "Default settings"),
    "start": ("▶  Iniciar", "▶  Start"),
    "title_done": ("✓ Listo — {title}", "✓ Done — {title}"),
    "title_failed": ("✕ Error — {title}", "✕ Error — {title}"),
    "recent": ("Recientes ▾", "Recent ▾"),
    "recent_none": ("(todavía no hay archivos recientes)", "(no recent files yet)"),
    "stop": ("■  Detener", "■  Stop"),
    "card_options": ("Opciones", "Options"),
    "log_title_card": ("Detalles técnicos", "Technical details"),
    "log_empty": ("Aquí aparece lo que hace el robot durante la búsqueda.",
                  "What the robot is doing appears here during the search."),
    "card_run": ("Buscar", "Search"),
    "estimate_short": ("Tiempo estimado: menos de 1 minuto", "Estimated time: under 1 minute"),
    "estimate_line": ("Tiempo estimado: ≈ {t} (menos si ya se buscaron antes)",
                      "Estimated time: ≈ {t} (less if searched recently)"),
    "stores_line": ("Supermercados: {names}", "Supermarkets: {names}"),
    "ready": ("Listo para empezar.", "Ready to start."),
    "open_results": ("Abrir resultados", "Open results"),
    "open_perf": ("Abrir análisis de desempeño", "Open performance analysis"),
    "open_folder": ("Abrir carpeta", "Open folder"),
    "tab_search": ("1 · Buscar precios", "1 · Search prices"),
    "tab_review": ("2 · Revisar precios", "2 · Review prices"),
    "review_empty_title": ("Todavía no hay precios para revisar", "No prices to review yet"),
    "review_empty": ("Haga una búsqueda en la pestaña «Buscar precios». Cuando termine, sus resultados se abren aquí automáticamente. "
                     "También puede abrir el archivo de resultados de una búsqueda anterior.",
                     "Run a search in the “Search prices” tab. When it finishes, its results open here automatically. "
                     "You can also open the results file from an earlier search."),
    "review_open": ("Abrir archivo de resultados…", "Open results file…"),
    "review_other": ("Abrir otro archivo…", "Open another file…"),
    "review_file": ("Revisando: {name}", "Reviewing: {name}"),
    "review_loading": ("Abriendo los resultados…", "Opening the results…"),
    "show_log": ("Mostrar detalles técnicos ▸", "Show technical details ▸"),
    "hide_log": ("Ocultar detalles técnicos", "Hide technical details"),
    "pick_title": ("Elegir archivo de productos", "Choose products file"),
    "all_files": ("Todos los archivos", "All files"),
    "cant_open": ("No se pudo abrir:", "Could not open:"),
    "busy_settings": ("Espere a que termine la búsqueda actual (o deténgala) para cambiar la configuración.",
                      "Wait for the current search to finish (or stop it) before changing settings."),
    "busy_lang": ("Espere a que termine la búsqueda actual para cambiar el idioma.",
                  "Wait for the current search to finish before changing the language."),
    "err_products": ("Primero elija el archivo de productos con «Buscar…».",
                     "First choose the products file with “Browse…”."),
    "err_stores": ("Seleccione al menos un supermercado en Configuración avanzada → Búsqueda en tiendas.",
                   "Select at least one supermarket in Advanced settings → Store search."),
    "err_stores_short": ("seleccione al menos uno", "select at least one"),
    "all_stores": ("Todos los supermercados", "All supermarkets"),
    "badge_stores": ("{n} de {total} supermercados", "{n} of {total} supermarkets"),
    "err_limit": ("La cantidad de productos para la prueba debe ser un número mayor que 0.",
                  "The number of products for the test must be a number greater than 0."),
    "reading": ("Leyendo el archivo de productos…", "Reading the products file…"),
    "cant_start": ("No se pudo iniciar el robot.", "Could not start the robot."),
    "confirm_stop": ("¿Detener la búsqueda? Los resultados de esta ejecución no se guardarán.",
                     "Stop the search? Results from this run will not be saved."),
    "stopping": ("Deteniendo…", "Stopping…"),
    "confirm_close": ("Hay una búsqueda en curso. ¿Detenerla y cerrar?",
                      "A search is running. Stop it and close?"),
    "cache_cleared": ("Caché borrada. Preparando búsqueda…", "Cache cleared. Preparing search…"),
    "no_products_match": ("Ningún producto coincide con los filtros elegidos.", "No products match the chosen filters."),
    "check_filters": ("Revise «Nombre contiene» y «Tipo de producto».", "Check “Name contains” and “Product type”."),
    "searching_n": ("Buscando precios de {n} producto(s)…", "Searching prices for {n} product(s)…"),
    "searching_step": ("Buscando precios… {i} de {n}", "Searching prices… {i} of {n}"),
    "saving": ("Guardando resultados en Excel…", "Saving results to Excel…"),
    "making_perf": ("Creando el análisis de desempeño…", "Creating the performance analysis…"),
    "finishing": ("Terminando…", "Finishing…"),
    "time": ("Tiempo: {t}", "Time: {t}"),
    "remaining": ("quedan ≈ {t}", "≈ {t} left"),
    "last_item": ("último: {name}", "last: {name}"),
    "stopped": ("Búsqueda detenida.", "Search stopped."),
    "stopped_detail": ("Se detuvo después de {t}. No se guardaron resultados.",
                       "Stopped after {t}. No results were saved."),
    "done": ("✓ Listo: {n} producto(s) en {t}", "✓ Done: {n} product(s) in {t}"),
    "results_file": ("Resultados: {name}", "Results: {name}"),
    "summarizing": ("calculando resumen…", "calculating summary…"),
    "loading_review": ("Preparando revisión… Puede seguir usando la ventana.", "Preparing review… The window remains available."),
    "exporting": ("Guardando archivos Excel…", "Saving Excel files…"),
    "summary_change": ("   ·   {n} con cambio de precio mayor a ±{p} %", "   ·   {n} with a price change over ±{p}%"),
    "summary": ("{est} de {n} con precio estimado   ·   {ok} sin alertas   ·   {review} para revisar   ·   {none} sin precio",
                "{est} of {n} with an estimated price   ·   {ok} with no warnings   ·   {review} to review   ·   {none} with no price"),
    "failed": ("✕ La búsqueda terminó con un error.", "✕ The search ended with an error."),
    "missing_python": ("Faltan componentes de Python (requests / openpyxl).", "Missing Python components (requests / openpyxl)."),
    "ask_install": ("Faltan componentes de Python necesarios para el robot.\n\n¿Instalarlos ahora? (requiere internet, tarda ~1 minuto)",
                    "Python components needed by the robot are missing.\n\nInstall them now? (needs internet, takes ~1 minute)"),
    "cant_save": ("No se pudo guardar el archivo de resultados.", "Could not save the results file."),
    "cant_save_long": ("No se pudo guardar el archivo de resultados.\n\nProbablemente está abierto en Excel. Ciérrelo y vuelva a intentarlo.",
                       "Could not save the results file.\n\nIt is probably open in Excel. Close it and try again."),
    "file_missing_detail": ("No se encontró un archivo necesario. Vea los detalles técnicos.",
                            "A required file was not found. See the technical details."),
    "detail": ("Detalle: {text}", "Detail: {text}"),
    "installing": ("Instalando componentes de Python…", "Installing Python components…"),
    "installed": ("✓ Componentes instalados. Ya puede iniciar la búsqueda.", "✓ Components installed. You can start the search now."),
    "install_failed": ("✕ No se pudieron instalar los componentes.", "✕ Could not install the components."),
    # advanced window
    "adv_title": ("Configuración avanzada", "Advanced settings"),
    "adv_intro": ("Los ajustes están ordenados según los pasos que sigue el robot. Cada uno explica qué hace y muestra "
                  "un ejemplo que cambia con el valor. Se guardan en ui_settings.json, solo se usan al buscar desde "
                  "esta ventana y no cambian el código original.",
                  "Settings are grouped by the steps the robot follows. Each one explains what it does and shows an "
                  "example that changes with the value. They are saved in ui_settings.json, only apply to searches "
                  "started from this window, and don't change the original code."),
    "nav_heading": ("EL ROBOT TRABAJA EN ESTE ORDEN", "THE ROBOT WORKS IN THIS ORDER"),
    "expert_show": ("▸ Ajustes para expertos ({n})", "▸ Expert settings ({n})"),
    "expert_hide": ("▾ Ajustes para expertos ({n})", "▾ Expert settings ({n})"),
    "expert_hint": ("Normalmente no hace falta cambiarlos.", "Usually there's no need to change these."),
    "reset_one": ("↺ Restaurar", "↺ Reset"),
    "reset_section": ("↺ Restaurar esta sección", "↺ Reset this section"),
    "reset_all": ("Restaurar todo", "Reset everything"),
    "modified": ("● modificado", "● changed"),
    "n_modified": ("● {n} modificado(s)", "● {n} changed"),
    "save": ("Guardar", "Save"),
    "cancel": ("Cancelar", "Cancel"),
    "default_is": ("Predeterminado: {v}", "Default: {v}"),
    "confirm_reset": ("¿Restaurar todos los valores predeterminados?", "Restore all default values?"),
    "invalid_title": ("Valor no válido", "Invalid value"),
    "err_between": ("debe estar entre {lo} y {hi}", "must be between {lo} and {hi}"),
    "err_integer": ("debe ser un número entero", "must be a whole number"),
    "err_option": ("opción no válida", "invalid option"),
    "err_number": ("debe ser un número", "must be a number"),
    "err_pref_min": ("El mínimo del rango preferido no puede ser menor que el mínimo de tamaño similar.",
                     "The preferred-range minimum cannot be lower than the similar-size minimum."),
    "err_pref_max": ("El máximo del rango preferido no puede ser mayor que el máximo de tamaño similar.",
                     "The preferred-range maximum cannot be higher than the similar-size maximum."),
    "err_output": ("El archivo de resultados debe ser solo un nombre que termine en .xlsx o .csv (por ejemplo: resultados_prueba.xlsx).",
                   "The results file must be just a file name ending in .xlsx or .csv (for example: test_results.xlsx)."),
    "unexpected_error": ("Ocurrió un error inesperado. Los detalles se guardaron en:",
                         "An unexpected error occurred. Details were saved to:"),
    "err_perf_output": ("El análisis de desempeño debe ser solo un nombre que termine en .xlsx.",
                        "The performance analysis must be just a file name ending in .xlsx."),
    "err_same_names": ("Los dos archivos no pueden tener el mismo nombre.", "The two files can't have the same name."),
    "err_folder": ("Esa carpeta no existe. Elíjala con «Buscar…» o deje el campo vacío para usar la carpeta output.",
                   "That folder doesn't exist. Choose it with “Browse…” or leave it empty to use the output folder."),
    "err_folder_run": ("La carpeta de resultados elegida en Configuración avanzada ya no existe:\n{path}",
                       "The results folder chosen in Advanced settings no longer exists:\n{path}"),
    "project_folder": ("la carpeta output", "the output folder"),
    "pick_folder_title": ("Elegir carpeta de resultados", "Choose results folder"),
}


def t(key: str, **kw) -> str:
    pair = STRINGS[key]
    s = pair[1] if LANG == "en" else pair[0]
    return s.format(**kw) if kw else s


def L(pair) -> str:
    """Pick the current language from an (es, en) pair."""
    return pair[1] if LANG == "en" else pair[0]


# ---------------------------------------------------------------------------
# Colours / fonts
# ---------------------------------------------------------------------------
C_BG = "#F4F6F4"
C_CARD = "#FFFFFF"
C_BORDER = "#DDE3DD"
C_TEXT = "#1F2A22"
C_MUTED = "#5F6B62"
C_ACCENT = "#2E7D32"
C_ACCENT_DARK = "#1B5E20"
C_HEADER = "#1F4D2B"
C_WARN = "#B45309"
C_ERROR = "#B91C1C"
C_OK = "#2E7D32"
FONT = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"

# ---------------------------------------------------------------------------
# Run options and matcher parameters
# ---------------------------------------------------------------------------
RUN_DEFAULTS = {
    "stores": [sid for sid, _ in STORES],   # which supermarkets to search
    "workers": 100,
    "cache_mode": "use",          # use | clear | none
    "CACHE_TTL_HOURS": 12,
    "average_mode": "store_balanced",
    "output": "coincidencias_de_precios.xlsx",
    "output_dir": "",              # "" = the output folder
    "perf_output": "analisis_de_desempeno.xlsx",
    "timestamp": "off",            # off | on  (add date and time to the file names)
    "open_when_done": "none",      # none | results | perf | both
}


def output_folder(run: dict) -> Path:
    folder = str(run.get("output_dir") or "").strip()
    return Path(folder) if folder else OUTPUT_DIR


def stamped(name: str, stamp: str | None) -> str:
    if not stamp:
        return name
    path = Path(name)
    return f"{path.stem}_{stamp}{path.suffix}"


def output_paths(run: dict, when: float | None = None) -> tuple[Path, Path]:
    """(results file, performance analysis file) for a search started at `when`."""
    stamp = time.strftime("%Y-%m-%d_%H-%M", time.localtime(when)) if run.get("timestamp") == "on" else None
    folder = output_folder(run)
    return folder / stamped(run["output"], stamp), folder / stamped(run["perf_output"], stamp)


def _output_preview(values: dict, which: int):
    path = output_paths(values)[which]
    return (f"Se guardará como: {path}", f"Will be saved as: {path}")


def _fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def _size(kg: float) -> str:
    if kg < 1:
        return f"{kg * 1000:.0f} g"
    return f"{kg:.2f}".rstrip("0").rstrip(".") + " kg"


# Observed full-catalog run: 5,440 products in about six minutes at 100 workers.
# Search time per product = latency shared across the simultaneous searches + a floor that more searches
# can't remove (store response limits, the robot's own work):   seconds = products × (A / workers + B).
# A and B are fitted to two observed runs with all four stores and no search memory (cache):
#   • 5,440 products at 100 workers in ≈ 6 min (full catalog benchmark)
#   • ≈ 80 products at 6 workers in 47 s (cache timestamps from a test run, Sept 2026)
# Doubling the workers therefore does not halve the time: 50 → ≈ 9 min, 100 → 6 min, 200 → ≈ 4.5 min.
RUNTIME_BASELINE_PRODUCTS = 5440
RUNTIME_BASELINE_WORKERS = 100
RUNTIME_BASELINE_SECONDS = 6 * 60
RUNTIME_SMALL_WORKERS, RUNTIME_SMALL_PRODUCTS_PER_SECOND = 6, 80 / 47
_Y1 = RUNTIME_BASELINE_WORKERS * RUNTIME_BASELINE_SECONDS / RUNTIME_BASELINE_PRODUCTS   # workers / products-per-second
_Y2 = RUNTIME_SMALL_WORKERS / RUNTIME_SMALL_PRODUCTS_PER_SECOND
RUNTIME_FLOOR_SECONDS = (_Y1 - _Y2) / (RUNTIME_BASELINE_WORKERS - RUNTIME_SMALL_WORKERS)          # B ≈ 0.033 s
RUNTIME_WORKER_SECONDS = _Y2 - RUNTIME_SMALL_WORKERS * RUNTIME_FLOOR_SECONDS                     # A ≈ 3.3 s


def estimate_run_seconds(products, workers, stores=4):
    """Pre-run estimate (no search memory). The live countdown during the search uses actual progress."""
    per_product = RUNTIME_WORKER_SECONDS / max(1, workers) + RUNTIME_FLOOR_SECONDS
    return round(max(0, products) * per_product * max(1, stores) / 4)


def _workers_example(v):
    duration = fmt_duration(estimate_run_seconds(RUNTIME_BASELINE_PRODUCTS, v))
    return (f"Lista completa (5,440 productos, 4 supermercados, sin memoria de búsquedas) con {v}: ≈ {duration}. "
            f"Referencias medidas: 100 → ≈ 6 min; 6 → ≈ 53 min. Más búsquedas ayudan cada vez menos.",
            f"Full list (5,440 products, 4 supermarkets, no search memory) at {v}: ≈ {duration}. "
            f"Measured references: 100 → ≈ 6 min; 6 → ≈ 53 min. More searches help less and less.")


def _mad_example(v):
    if v < 2.5:
        es, en = "muy estricto (descarta muchos precios)", "very strict (discards many prices)"
    elif v <= 4.5:
        es, en = "normal", "normal"
    else:
        es, en = "permisivo (descarta pocos precios)", "lenient (discards few prices)"
    return (f"Recomendado: 3.5.  Con {fmt_number(v)}: {es}.", f"Recommended: 3.5.  With {fmt_number(v)}: {en}.")


def _min_matches_example(v):
    return (f"Con {v}: si hay menos de {v} productos comparables, el precio se marca «riesgo alto».",
            f"With {v}: fewer than {v} comparable products and the price is marked “high risk”.")


def _price_change_example(v):
    low, high = max(0.0, 5 * (1 - v)), 5 * (1 + v)
    return (f"Ej.: precio actual $5.00 → se marca si el estimado es menor que {_fmt_money(low)} o mayor que {_fmt_money(high)}.",
            f"E.g. current price $5.00 → marked if the estimate is below {_fmt_money(low)} or above {_fmt_money(high)}.")


def _cv_example(v):
    marked = 0.204 > v
    return (f"Ej.: precios de $3, $4 y $5 por kg varían un 20 % → {'se marcaría' if marked else 'no se marcaría'}.",
            f"E.g. prices of $3, $4 and $5 per kg vary by 20% → {'would be marked' if marked else 'would not be marked'}.")


def _jaccard_example(v):
    dup = 0.8 >= v
    return ("Ej.: «Arroz Diana Premium 5 lb» y «Arroz Diana 5 lb» comparten 4 de 5 palabras (80 %) → "
            f"{'sí' if dup else 'no'} cuentan como duplicado por el nombre.",
            "E.g. “Arroz Diana Premium 5 lb” and “Arroz Diana 5 lb” share 4 of 5 words (80%) → "
            f"{'do' if dup else 'do not'} count as a duplicate by name.")


def _stores_example(value):
    names = [name for sid, name in STORES if sid in (value or [])]
    n = len(names)
    return (f"Se buscará en {n} de {len(STORES)}: " + ", ".join(names),
            f"Will search {n} of {len(STORES)}: " + ", ".join(names))


# Every setting in the Advanced window, in the order the robot uses them.
#   store:   "run"     = how this window runs the robot
#            "matcher" = a rule passed to the robot for this run
#   level:   "basic" (always shown) or "expert" (under "Ajustes para expertos")
#   kind:    int | float | percent (stored as a fraction, shown as %) | choice (radio buttons) | text
#   example: function(value) -> (es, en) — a live example that updates as the value changes
SETTINGS_SPEC = [
    # ---- 1. Store search ----------------------------------------------------
    dict(section="search", store="run", level="basic", key="stores", kind="stores",
         default=[sid for sid, _ in STORES],
         label=("Supermercados", "Supermarkets"),
         help=("En qué supermercados se buscan los precios. Normalmente se usan todos; quite uno solo si su "
               "página no funciona o no se necesita para esta búsqueda.",
               "Which supermarkets prices are searched in. Normally all of them are used; untick one only if "
               "its website is not working or it is not needed for this search."),
         example=_stores_example),
    dict(section="search", store="run", level="basic", key="workers", kind="int", default=100, lo=1, hi=100,
         unit=("a la vez", "at a time"),
         label=("Búsquedas simultáneas", "Simultaneous searches"),
         help=("Cuántos productos se buscan al mismo tiempo. Para la lista completa de 5,440 productos, "
               "100 ha dado buenos resultados: aproximadamente 6 minutos. El tiempo depende de las tiendas, "
               "la conexión y la memoria de búsquedas; el contador se ajusta al progreso real.",
               "How many products are searched at the same time. For the full 5,440-product list, "
               "100 has worked well: approximately 6 minutes. Timing depends on the stores, connection "
               "and search cache; the countdown adjusts to actual progress."),
         example=_workers_example),
    dict(section="search", store="run", level="basic", key="cache_mode", kind="choice", default="use",
         choices=[("use", ("Usar la memoria (recomendado)", "Use the memory (recommended)")),
                  ("clear", ("Borrar la memoria y buscar todo de nuevo — después de cambios grandes o si los precios "
                             "parecen viejos",
                             "Clear the memory and search everything again — after big changes or if prices look old")),
                  ("none", ("No usar la memoria — consultar siempre las tiendas (más lento)",
                            "Don't use the memory — always ask the stores (slower)"))],
         label=("Memoria de búsquedas (caché)", "Search memory (cache)"),
         help=("El robot guarda las respuestas de las tiendas para no repetir la misma búsqueda. Así, buscar otra "
               "vez los mismos productos es mucho más rápido.",
               "The robot saves the stores' answers so it doesn't repeat the same search. Searching the same "
               "products again is much faster this way.")),
    dict(section="search", store="run", level="expert", key="CACHE_TTL_HOURS", kind="int", default=12, lo=1, hi=720,
         unit=("horas", "hours"),
         label=("Duración de la memoria", "Memory duration"),
         help=("Cuánto tiempo se reutiliza una respuesta guardada antes de volver a consultar la tienda.",
               "How long a saved answer is reused before the store is asked again."),
         example=lambda v: (f"Con {v}: los precios guardados tienen como máximo {v} horas de antigüedad.",
                            f"With {v}: saved prices are at most {v} hours old.")),
    dict(section="search", store="matcher", level="expert", key="RAW_MATCH_STOP_COUNT", kind="int", default=10,
         lo=1, hi=100, unit=("productos", "products"),
         label=("Dejar de buscar al encontrar", "Stop searching after finding"),
         help=("Para cada producto el robot prueba varias búsquedas (por ejemplo «arroz integral» y después «arroz»). "
               "Cuando una tienda ya dio suficientes coincidencias, no prueba más. Más alto = más evidencia pero más lento.",
               "For each product the robot tries several searches (e.g. “arroz integral”, then “arroz”). Once a store "
               "has returned enough matches, it stops trying. Higher = more evidence but slower."),
         example=lambda v: (f"Con {v}: cuando una tienda da {v} productos que coinciden, se pasa a la siguiente tienda.",
                            f"With {v}: once a store returns {v} matching products, the robot moves on.")),

    # ---- 2. Package size ----------------------------------------------------
    dict(section="size", store="matcher", level="basic", key="MIN_SIZE_RATIO", kind="percent", default=0.67,
         lo=5, hi=100, unit=("del tamaño BAP", "of the BAP size"),
         label=("Tamaño más pequeño aceptado", "Smallest accepted size"),
         help=("El paquete de tienda más pequeño que todavía se compara con el producto BAP.",
               "The smallest store package that is still compared with the BAP product."),
         example=lambda v: (f"Ej.: para un producto BAP de 1 kg, se aceptan paquetes desde {_size(v)}.",
                            f"E.g. for a 1 kg BAP product, packages from {_size(v)} are accepted.")),
    dict(section="size", store="matcher", level="basic", key="MAX_SIZE_RATIO", kind="percent", default=1.50,
         lo=100, hi=2000, unit=("del tamaño BAP", "of the BAP size"),
         label=("Tamaño más grande aceptado", "Largest accepted size"),
         help=("El paquete de tienda más grande que todavía se compara con el producto BAP.",
               "The largest store package that is still compared with the BAP product."),
         example=lambda v: (f"Ej.: para un producto BAP de 1 kg, se aceptan paquetes hasta {_size(v)}.",
                            f"E.g. for a 1 kg BAP product, packages up to {_size(v)} are accepted.")),
    dict(section="size", store="matcher", level="expert", key="PREFERRED_SIZE_RATIO_MIN", kind="percent",
         default=0.80, lo=5, hi=100, unit=("del tamaño BAP", "of the BAP size"),
         label=("Rango preferido: mínimo", "Preferred range: minimum"),
         help=("Si hay suficientes paquetes todavía más parecidos al producto BAP, el robot usa solo esos. "
               "Este es el límite inferior de ese rango más estrecho.",
               "If there are enough packages even closer in size to the BAP product, the robot uses only those. "
               "This is the lower limit of that narrower range."),
         example=lambda v: (f"Ej.: para 1 kg, el rango preferido empieza en {_size(v)}.",
                            f"E.g. for 1 kg, the preferred range starts at {_size(v)}.")),
    dict(section="size", store="matcher", level="expert", key="PREFERRED_SIZE_RATIO_MAX", kind="percent",
         default=1.25, lo=100, hi=2000, unit=("del tamaño BAP", "of the BAP size"),
         label=("Rango preferido: máximo", "Preferred range: maximum"),
         help=("El límite superior del rango preferido.", "The upper limit of the preferred range."),
         example=lambda v: (f"Ej.: para 1 kg, el rango preferido termina en {_size(v)}.",
                            f"E.g. for 1 kg, the preferred range ends at {_size(v)}.")),
    dict(section="size", store="matcher", level="expert", key="MIN_PREFERRED_SIZE_MATCHES", kind="int", default=3,
         lo=1, hi=30, unit=("productos", "products"),
         label=("Mínimo dentro del rango preferido", "Minimum inside the preferred range"),
         help=("Cuántos paquetes deben caer en el rango preferido para usar solo ese rango.",
               "How many packages must fall in the preferred range to use only that range."),
         example=lambda v: (f"Con {v}: si {v} o más paquetes están en el rango preferido, se ignoran los demás.",
                            f"With {v}: if {v} or more packages are in the preferred range, the rest are ignored.")),
    dict(section="size", store="matcher", level="expert", key="SIZE_CLUSTER_FACTOR", kind="float", default=1.75,
         lo=1.05, hi=10.0, step=0.05, unit=("×", "×"),
         label=("Agrupación de respaldo", "Fallback grouping"),
         help=("Para productos mucho más grandes que lo que venden las tiendas (por ejemplo una caja institucional "
               "de 17 kg) no hay paquetes de tamaño parecido. Entonces el robot agrupa los paquetes de tienda de "
               "tamaño similar entre sí y usa el grupo más cercano.",
               "For products much bigger than what stores sell (e.g. a 17 kg institutional box) there are no "
               "similar-size packages. The robot then groups store packages of similar size together and uses "
               "the closest group."),
         example=lambda v: (f"Ej.: un paquete de 1 kg se agrupa con otros de hasta {_size(v)}.",
                            f"E.g. a 1 kg package is grouped with others up to {_size(v)}.")),
    dict(section="size", store="matcher", level="expert", key="MAX_FALLBACK_SIZE_MATCHES", kind="int", default=10,
         lo=1, hi=100, unit=("productos", "products"),
         label=("Máximo en la agrupación de respaldo", "Maximum in the fallback grouping"),
         help=("Cuántos paquetes se usan como máximo cuando se aplica la agrupación de respaldo.",
               "The most packages used when the fallback grouping is applied."),
         example=lambda v: (f"Con {v}: se usan como máximo {v} paquetes del grupo más cercano.",
                            f"With {v}: at most {v} packages from the closest group are used.")),

    # ---- 3. Price cleanup ---------------------------------------------------
    dict(section="clean", store="matcher", level="basic", key="HARD_OUTLIER_LOW_RATIO", kind="percent", default=0.50,
         lo=1, hi=99, unit=("de la mediana", "of the median"),
         label=("Descartar precios muy bajos", "Discard very low prices"),
         help=("Un precio por kilo menor que este porcentaje de la mediana se considera un error o una oferta rara "
               "y se descarta.",
               "A price per kg below this percentage of the median is treated as an error or an unusual sale "
               "and discarded."),
         example=lambda v: (f"Ej.: si la mediana es $4.00/kg, se descartan precios menores que {_fmt_money(4 * v)}/kg.",
                            f"E.g. if the median is $4.00/kg, prices below {_fmt_money(4 * v)}/kg are discarded.")),
    dict(section="clean", store="matcher", level="basic", key="HARD_OUTLIER_HIGH_RATIO", kind="float", default=2.00,
         lo=1.05, hi=20.0, step=0.05, unit=("× la mediana", "× the median"),
         label=("Descartar precios muy altos", "Discard very high prices"),
         help=("Un precio por kilo mayor que esta cantidad de veces la mediana se descarta.",
               "A price per kg above this many times the median is discarded."),
         example=lambda v: (f"Ej.: si la mediana es $4.00/kg, se descartan precios mayores que {_fmt_money(4 * v)}/kg.",
                            f"E.g. if the median is $4.00/kg, prices above {_fmt_money(4 * v)}/kg are discarded.")),
    dict(section="clean", store="matcher", level="expert", key="LOG_MAD_Z_THRESHOLD", kind="float", default=3.5,
         lo=0.5, hi=20.0, step=0.1,
         label=("Sensibilidad estadística", "Statistical sensitivity"),
         help=("Cuando hay suficientes precios, una prueba estadística busca los que se alejan mucho del resto. "
               "Más bajo = descarta más precios.",
               "When there are enough prices, a statistical test looks for ones far from the rest. "
               "Lower = discards more prices."),
         example=_mad_example),
    dict(section="clean", store="matcher", level="expert", key="DUPLICATE_SIZE_TOLERANCE", kind="percent",
         default=0.10, lo=0, hi=100,
         label=("Duplicados: diferencia de tamaño", "Duplicates: size difference"),
         help=("Dos productos se cuentan una sola vez si se parecen en tamaño, precio y nombre (las tres cosas). "
               "Esta es la diferencia de tamaño permitida.",
               "Two products are counted only once if they match in size, price and name (all three). "
               "This is the size difference allowed."),
         example=lambda v: (f"Ej.: 1 kg y {_size(1 + v)} todavía pueden ser el mismo producto.",
                            f"E.g. 1 kg and {_size(1 + v)} can still be the same product.")),
    dict(section="clean", store="matcher", level="expert", key="DUPLICATE_PRICE_TOLERANCE", kind="percent",
         default=0.15, lo=0, hi=100,
         label=("Duplicados: diferencia de precio", "Duplicates: price difference"),
         help=("La diferencia de precio por kilo permitida entre dos posibles duplicados.",
               "The price-per-kg difference allowed between two possible duplicates."),
         example=lambda v: (f"Ej.: $4.00/kg y {_fmt_money(4 * (1 + v))}/kg todavía pueden ser el mismo producto.",
                            f"E.g. $4.00/kg and {_fmt_money(4 * (1 + v))}/kg can still be the same product.")),
    dict(section="clean", store="matcher", level="expert", key="DUPLICATE_TOKEN_JACCARD", kind="percent",
         default=0.80, lo=1, hi=100, unit=("de palabras iguales", "of words in common"),
         label=("Duplicados: nombres parecidos", "Duplicates: similar names"),
         help=("Qué parte de las palabras del nombre deben coincidir para que dos productos sean duplicados.",
               "How much of the product name must match for two products to be duplicates."),
         example=_jaccard_example),

    # ---- 4. BAP price -------------------------------------------------------
    dict(section="price", store="matcher", level="basic", key="BAP_MARKET_PRICE_PERCENT", kind="percent",
         default=0.20, lo=1, hi=100, unit=("del valor de mercado", "of market value"),
         label=("Porcentaje BAP", "BAP percentage"),
         help=("El precio BAP es este porcentaje del valor de mercado que calcula el robot.",
               "The BAP price is this percentage of the market value the robot calculates."),
         example=lambda v: (f"Ej.: valor de mercado $10.00 → precio BAP {_fmt_money(10 * v)}.",
                            f"E.g. market value $10.00 → BAP price {_fmt_money(10 * v)}.")),
    dict(section="price", store="matcher", level="basic", key="MARKET_PRICE_LEVEL", kind="choice", default="economy",
         choices=[("economy", ("Económico: el extremo más barato de cada tienda (recomendado)",
                               "Economy: the cheaper end of each store (recommended)")),
                  ("median", ("Mediana: el precio del medio", "Median: the middle price")),
                  ("average", ("Promedio de todos los productos encontrados", "Average of all products found"))],
         label=("Nivel del valor de mercado", "Market value level"),
         help=("Las tiendas venden marcas baratas y marcas caras. Esto decide qué parte de esos precios se usa "
               "como valor de mercado. «Económico» usa el precio del primer cuarto (el 25 % más barato) de cada "
               "tienda.",
               "Stores sell cheap and expensive brands. This decides which part of those prices is used as the "
               "market value. \"Economy\" uses the price at the first quarter (the cheapest 25%) of each store."),
         example=lambda v: ("Ej.: una tienda con $2, $3, $4 y $7 por kg → valor de mercado "
                            + {"economy": "$2.75", "median": "$3.50", "average": "$4.00"}.get(v, "$4.00") + "/kg.",
                            "E.g. a store with $2, $3, $4 and $7 per kg → market value "
                            + {"economy": "$2.75", "median": "$3.50", "average": "$4.00"}.get(v, "$4.00") + "/kg.")),
    dict(section="price", store="matcher", level="basic", key="PRICE_BASIS", kind="choice", default="regular",
         choices=[("regular", ("Precio regular, sin ofertas (recomendado)", "Regular price, no sales (recommended)")),
                  ("final", ("Precio en oferta, con descuentos", "Sale price, with discounts"))],
         label=("Precio de tienda a usar", "Store price to use"),
         help=("Qué precio se usa cuando un producto está en oferta.", "Which price is used when a product is on sale."),
         example=lambda v: (f"Ej.: regular $5.00, en oferta $4.00 → se usa {'$5.00' if v == 'regular' else '$4.00'}.",
                            f"E.g. regular $5.00, on sale $4.00 → {'$5.00' if v == 'regular' else '$4.00'} is used.")),
    dict(section="price", store="run", level="basic", key="average_mode", kind="choice", default="store_balanced",
         choices=[("store_balanced", ("Equilibrado: ninguna tienda domina (recomendado)",
                                      "Balanced: no store dominates (recommended)")),
                  ("all_candidates", ("Todos los productos juntos: las tiendas con más productos pesan más",
                                      "All products together: stores with more products weigh more"))],
         label=("Cómo combinar los supermercados", "How to combine supermarkets"),
         help=("Algunas tiendas devuelven muchos productos y otras pocos. Esto decide cuánto pesa cada una en el "
               "valor de mercado. Equilibrado: cada tienda cuenta según su número de productos, hasta 3.",
               "Some stores return many products and others few. This decides how much each one weighs in the "
               "market value. Balanced: each store counts by its number of products, up to 3."),
         example=lambda v: ("Ej.: Super 99 da $4.00/kg con 12 productos y Riba Smith $5.00/kg con 2 → valor de "
                            f"mercado {'$4.40' if v == 'store_balanced' else '$4.14'}/kg.",
                            "E.g. Super 99 gives $4.00/kg from 12 products and Riba Smith $5.00/kg from 2 → market "
                            f"value {'$4.40' if v == 'store_balanced' else '$4.14'}/kg.")),

    # ---- 5. Review warnings -------------------------------------------------
    dict(section="alerts", store="matcher", level="basic", key="MIN_GOOD_MATCHES", kind="int", default=5, lo=1, hi=30,
         unit=("productos", "products"),
         label=("Productos comparables necesarios", "Comparable products needed"),
         help=("Con menos productos comparables que este número, el precio se marca como «riesgo alto» porque "
               "hay poca evidencia.",
               "With fewer comparable products than this, the price is marked “high risk” because there is "
               "little evidence."),
         example=_min_matches_example),
    dict(section="alerts", store="launcher", level="basic", key="PRICE_CHANGE_REVIEW_THRESHOLD", kind="percent",
         default=PRICE_CHANGE_REVIEW_THRESHOLD, lo=1, hi=500, unit=("arriba o abajo", "up or down"),
         label=("Cambio de precio que requiere revisión", "Price change that needs review"),
         help=("En la revisión humana y en los resultados con comparación: se marca el producto si el precio "
               "estimado sube o baja más que este porcentaje respecto al precio actual.",
               "Used by human review and results with price comparison: the product is marked if the estimated price "
               "is higher or lower than the current price by more than this percentage."),
         example=_price_change_example),
    dict(section="alerts", store="matcher", level="expert", key="PRICE_RATIO_WARNING", kind="float", default=1.75,
         lo=1.01, hi=20.0, step=0.05, unit=("× el más barato", "× the cheapest"),
         label=("Alerta: diferencia entre precios", "Warning: gap between prices"),
         help=("Se marca el producto si el precio por kilo más caro es muchas veces el más barato.",
               "The product is marked if the most expensive price per kg is many times the cheapest."),
         example=lambda v: (f"Ej.: si el más barato es $2.00/kg, se marca si el más caro supera {_fmt_money(2 * v)}/kg.",
                            f"E.g. if the cheapest is $2.00/kg, it is marked if the most expensive is above "
                            f"{_fmt_money(2 * v)}/kg.")),
    dict(section="alerts", store="matcher", level="expert", key="PRICE_CV_WARNING", kind="percent", default=0.30,
         lo=1, hi=500,
         label=("Alerta: precios muy dispersos", "Warning: widely spread prices"),
         help=("Mide qué tan distintos son los precios entre sí (coeficiente de variación). Si supera este "
               "porcentaje, se marca el producto.",
               "Measures how different the prices are from each other (coefficient of variation). Above this "
               "percentage, the product is marked."),
         example=_cv_example),

    # ---- 6. Results files ---------------------------------------------------
    dict(section="output", store="run", level="basic", key="output_dir", kind="folder", default="",
         label=("Carpeta de resultados", "Results folder"),
         help=("Dónde se guardan los dos archivos de Excel de cada búsqueda. Déjela vacía para usar la carpeta "
               "output.",
               "Where the two Excel files from each search are saved. Leave it empty to use the output folder."),
         example_all=lambda vals: (f"Los archivos se guardarán en: {output_folder(vals)}",
                                   f"Files will be saved in: {output_folder(vals)}")),
    dict(section="output", store="run", level="basic", key="output", kind="text",
         default="coincidencias_de_precios.xlsx",
         label=("Archivo de resultados", "Results file"),
         help=("Un renglón por producto con el precio estimado, más una hoja con todos los productos de tienda "
               "revisados. Termine el nombre en .xlsx (recomendado) o .csv.",
               "One row per product with the estimated price, plus a sheet with every store product checked. "
               "End the name in .xlsx (recommended) or .csv."),
         example_all=lambda vals: _output_preview(vals, 0)),
    dict(section="output", store="run", level="basic", key="perf_output", kind="text",
         default="analisis_de_desempeno.xlsx",
         label=("Análisis de desempeño", "Performance analysis"),
         help=("El informe para revisar la búsqueda: resumen general, comparación con los precios actuales y qué "
               "productos necesitan revisión manual. Debe terminar en .xlsx.",
               "The report for reviewing the search: overall summary, comparison with current prices and which "
               "products need a manual review. Must end in .xlsx."),
         example_all=lambda vals: _output_preview(vals, 1)),
    dict(section="output", store="run", level="basic", key="timestamp", kind="choice", default="off",
         choices=[("off", ("Reemplazar los archivos anteriores en cada búsqueda",
                           "Replace the previous files on every search")),
                  ("on", ("Guardar cada búsqueda por separado, agregando fecha y hora al nombre",
                          "Keep every search separately, adding the date and time to the name"))],
         label=("Búsquedas anteriores", "Previous searches"),
         help=("Si se agrega la fecha y hora, cada búsqueda crea archivos nuevos y las anteriores se conservan.",
               "With the date and time added, each search creates new files and older ones are kept."),
         example=lambda v: (("Ej.: coincidencias_de_precios_2026-09-25_14-30.xlsx" if v == "on" else
                             "Ej.: siempre coincidencias_de_precios.xlsx (se sobrescribe)"),
                            ("E.g. coincidencias_de_precios_2026-09-25_14-30.xlsx" if v == "on" else
                             "E.g. always coincidencias_de_precios.xlsx (overwritten)"))),
    dict(section="output", store="run", level="basic", key="open_when_done", kind="choice", default="none",
         choices=[("none", ("No abrir nada", "Don't open anything")),
                  ("results", ("Abrir el archivo de resultados", "Open the results file")),
                  ("perf", ("Abrir el análisis de desempeño", "Open the performance analysis")),
                  ("both", ("Abrir los dos", "Open both"))],
         label=("Al terminar la búsqueda", "When the search finishes"),
         help=("Abrir automáticamente los archivos en Excel cuando termina una búsqueda.",
               "Open the files in Excel automatically when a search finishes.")),
]
# Settings passed to the robot (matcher_core / launcher); "run" settings are stored separately.
PARAMS = [p for p in SETTINGS_SPEC if p["store"] in ("matcher", "launcher")]
RUN_PARAMS = [p for p in SETTINGS_SPEC if p["store"] == "run"]
PARAM_BY_KEY = {p["key"]: p for p in PARAMS}
SPEC_BY_KEY = {p["key"]: p for p in SETTINGS_SPEC}

# The Advanced window follows the order in which the robot works.
ADV_SECTIONS = [
    ("search", ("Búsqueda en tiendas", "Store search"),
     ("Velocidad y cuánto se busca", "Speed and how much to search"),
     ("El robot busca cada producto BAP en las páginas web de los supermercados elegidos. Estos ajustes "
      "controlan qué tan rápido busca y cuándo deja de buscar.",
      "The robot looks up each BAP product on the chosen supermarkets' websites. These settings control how "
      "fast it searches and when it stops searching.")),
    ("size", ("Tamaño del paquete", "Package size"),
     ("Qué productos de tienda son comparables", "Which store products are comparable"),
     ("Un paquete pequeño suele costar más por kilo que uno grande. Por eso el robot compara el producto BAP "
      "solo con paquetes de tienda de tamaño parecido. Los porcentajes se miden contra el tamaño del producto "
      "BAP: 100 % = el mismo tamaño.",
      "A small package usually costs more per kg than a big one. So the robot only compares the BAP product "
      "with store packages of a similar size. Percentages are relative to the BAP product's size: "
      "100% = the same size.")),
    ("clean", ("Limpieza de precios", "Price cleanup"),
     ("Quitar duplicados y precios extraños", "Remove duplicates and odd prices"),
     ("Antes de promediar, el robot descarta precios poco confiables: el mismo producto listado dos veces, y "
      "precios por kilo demasiado bajos o altos comparados con la mediana (el precio del medio).",
      "Before averaging, the robot discards unreliable prices: the same product listed twice, and prices per "
      "kg far below or above the median (the middle price).")),
    ("price", ("Precio BAP", "BAP price"),
     ("Cómo se calcula el precio final", "How the final price is calculated"),
     ("Con los precios que quedan, el robot calcula un precio por kilo para cada supermercado, los combina en "
      "un valor de mercado y aplica el porcentaje BAP.",
      "With the remaining prices, the robot calculates a price per kg for each supermarket, combines them "
      "into a market value and applies the BAP percentage.")),
    ("alerts", ("Alertas de revisión", "Review warnings"),
     ("Cuándo marcar un producto para revisar", "When to mark a product for review"),
     ("Estos ajustes no cambian el precio calculado. Solo deciden cuándo un producto se marca con una alerta "
      "para que alguien lo revise a mano.",
      "These settings don't change the calculated price. They only decide when a product gets a warning so "
      "someone checks it by hand.")),
    ("output", ("Resultados", "Results"),
     ("Dónde y cómo se guardan los archivos", "Where and how files are saved"),
     ("Cada búsqueda crea dos archivos de Excel: los resultados (el precio de cada producto) y el análisis "
      "de desempeño (el informe para revisar la búsqueda). Aquí se elige dónde se guardan, cómo se llaman "
      "y qué pasa al terminar.",
      "Each search creates two Excel files: the results (each product's price) and the performance analysis "
      "(the report for reviewing the search). Choose here where they are saved, what they are called and "
      "what happens when the search finishes.")),
]


MC = None  # matcher_core, if it can be imported


def norm(value) -> str:
    """Same text normalisation as the robot (lowercase, no accents), used for the live product count."""
    if MC is not None:
        return MC.normalize(value)
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def load_code_defaults() -> None:
    """Read the real default values from the code so this UI stays in sync with it."""
    global MC
    try:
        import matcher_core as mc  # stdlib-only module, safe to import
        MC = mc
        for p in PARAMS:
            if hasattr(mc, p["key"]):
                p["default"] = getattr(mc, p["key"])
    except Exception:
        pass
    try:
        from price_robot import DEFAULT_WORKERS, CACHE_TTL_HOURS
        RUN_DEFAULTS["workers"] = DEFAULT_WORKERS
        RUN_DEFAULTS["CACHE_TTL_HOURS"] = CACHE_TTL_HOURS
    except Exception:
        pass
    for p in RUN_PARAMS:
        p["default"] = RUN_DEFAULTS[p["key"]]


def fmt_number(value) -> str:
    if isinstance(value, float):
        s = f"{value:.4f}".rstrip("0").rstrip(".")
        return s or "0"
    return str(value)


def display_value(p, value) -> str:
    if p["kind"] == "stores":
        return ",".join(value or [])
    if p["kind"] == "percent":
        return fmt_number(round(float(value) * 100, 4))
    if p["kind"] == "choice":
        for val, pair in p["choices"]:
            if val == value:
                return L(pair)
        return str(value)
    return fmt_number(value)


def parse_param(p, text: str):
    """Convert what the user typed into the value used by the code. Raises ValueError with a readable message."""
    if p["kind"] in ("text", "folder"):
        return str(text).strip()
    if p["kind"] == "stores":
        chosen = {part.strip() for part in str(text).split(",")}
        stores = [sid for sid, _ in STORES if sid in chosen]
        if not stores:
            raise ValueError(t("err_stores_short"))
        return stores
    text = str(text).strip().replace(",", ".").replace("%", "").strip()
    if p["kind"] == "choice":
        for val, pair in p["choices"]:
            if text in (val, pair[0], pair[1]):
                return val
        raise ValueError(t("err_option"))
    try:
        number = float(text)
    except ValueError:
        raise ValueError(t("err_number")) from None
    unit = " %" if p["kind"] == "percent" else ""
    if not p["lo"] <= number <= p["hi"]:
        raise ValueError(t("err_between", lo=f"{fmt_number(p['lo'])}{unit}", hi=f"{fmt_number(p['hi'])}{unit}"))
    if p["kind"] == "int":
        if number != int(number):
            raise ValueError(t("err_integer"))
        return int(number)
    if p["kind"] == "percent":
        return round(number / 100.0, 6)
    return number


def python_for_subprocess() -> str:
    """Use python.exe (not pythonw.exe) for the worker so its output can be read."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        candidate = exe.with_name("python.exe")
        if candidate.exists():
            return str(candidate)
    return str(exe)


def no_window_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0


def open_path(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        messagebox.showerror(t("app_title"), f"{t('cant_open')}\n{path}\n\n{exc}")


def ui_scale(win) -> float:
    """How much bigger than a standard 96-dpi screen the text is drawn (1.0, 1.25, 1.5…)."""
    try:
        return max(1.0, float(win.tk.call("tk", "scaling")) / (96 / 72))
    except Exception:
        return 1.0


def work_area(win) -> tuple[int, int, int, int]:
    """(left, top, width, height) of the screen area not covered by the Windows taskbar."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        except Exception:
            pass
    return 0, 0, win.winfo_screenwidth(), int(win.winfo_screenheight() * 0.93)


def fit_window(win, width: int, height: int, min_w: int, min_h: int) -> None:
    """Size a window for the screen's text scaling, keep it above the taskbar, and center it."""
    s = ui_scale(win)
    left, top, aw, ah = work_area(win)
    title_bar = int(32 * s)  # the window frame is added on top of the size we ask for
    w = min(int(width * s), int(aw * 0.96))
    h = min(int(height * s), ah - title_bar - int(12 * s))
    x = left + max(0, (aw - w) // 2)
    y = top + max(0, (ah - h - title_bar) // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")
    win.minsize(min(int(min_w * s), w), min(int(min_h * s), h))


# ---------------------------------------------------------------------------
# Small drawn images (checkboxes, app icon) — drawn in code so no image files are needed
# ---------------------------------------------------------------------------
def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _rgb(color: str):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _in_round_rect(x, y, x0, y0, x1, y1, r) -> bool:
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _seg_dist(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    t_ = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1)))
    return ((px - ax - t_ * dx) ** 2 + (py - ay - t_ * dy) ** 2) ** 0.5


def paint_image(width, height, sample, background=None, samples=4):
    """Draw an image by asking sample(x, y) for a colour (or None = background) at sub-pixel points.
    Edges are smoothed. With background=None, empty pixels are transparent."""
    img = tk.PhotoImage(width=width, height=height)
    bg = _rgb(background) if background else None
    rows, clear = [], []
    for y in range(height):
        row = []
        for x in range(width):
            hits = []
            for sy in range(samples):
                for sx in range(samples):
                    c = sample(x + (sx + 0.5) / samples, y + (sy + 0.5) / samples)
                    hits.append(_rgb(c) if c else None)
            covered = [h for h in hits if h]
            if not covered:
                row.append(background or "#ffffff")
                if not bg:
                    clear.append((x, y))
                continue
            fill = bg or tuple(sum(h[i] for h in covered) / len(covered) for i in range(3))
            mixed = [h or fill for h in hits]
            row.append(_hex(tuple(sum(h[i] for h in mixed) / len(mixed) for i in range(3))))
        rows.append("{" + " ".join(row) + "}")
    img.put(" ".join(rows))
    for x, y in clear:
        try:
            img.tk.call(img, "transparency", "set", x, y, 1)
        except Exception:
            break
    return img


def checkbox_images(scale: float) -> dict:
    """Checkbox pictures with a real ✓ (the default theme shows an ✕, which reads like "excluded")."""
    box = max(13, int(round(15 * scale)))
    gap = max(5, int(round(7 * scale)))
    r = box * 0.2
    width = box + gap
    tick = [(0.24 * box, 0.52 * box), (0.43 * box, 0.71 * box), (0.77 * box, 0.31 * box)]
    thick = max(1.3, 0.085 * box)

    def make(fill, border, check):
        def sample(x, y):
            if x > box:
                return None
            if not _in_round_rect(x, y, 0.5, 0.5, box - 0.5, box - 0.5, r):
                return None
            if check and (_seg_dist(x, y, *tick[0], *tick[1]) <= thick or _seg_dist(x, y, *tick[1], *tick[2]) <= thick):
                return check
            inner = _in_round_rect(x, y, 1.7, 1.7, box - 1.7, box - 1.7, max(0.5, r - 1.2))
            return fill if inner else border
        return paint_image(width, box, sample, background=C_CARD)

    return {
        "off": make("#FFFFFF", "#8F9C91", None),
        "off_hover": make("#FFFFFF", C_ACCENT, None),
        "on": make(C_ACCENT, C_ACCENT, "#FFFFFF"),
        "on_hover": make(C_ACCENT_DARK, C_ACCENT_DARK, "#FFFFFF"),
        "off_disabled": make("#F1F3F1", "#CDD4CE", None),
        "on_disabled": make("#B7CCB9", "#B7CCB9", "#FFFFFF"),
    }


def app_icon(size: int):
    """The app icon: a white price tag on a dark-green rounded square."""
    import math
    s = size
    ang = math.radians(-35)
    cx, cy = 0.5 * s, 0.5 * s
    tag = [(0.50, 0.12), (0.74, 0.34), (0.74, 0.86), (0.26, 0.86), (0.26, 0.34)]
    pts = []
    for u, v in tag:
        x, y = (u - 0.5) * s, (v - 0.5) * s
        pts.append((cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang)))
    hx, hy = 0.0, (0.33 - 0.5) * s
    hole = (cx + hx * math.cos(ang) - hy * math.sin(ang), cy + hx * math.sin(ang) + hy * math.cos(ang))

    def inside(x, y):
        hit = False
        for i in range(len(pts)):
            (x1, y1), (x2, y2) = pts[i], pts[i - 1]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                hit = not hit
        return hit

    def sample(x, y):
        if not _in_round_rect(x, y, 0, 0, s, s, s * 0.22):
            return None
        if (x - hole[0]) ** 2 + (y - hole[1]) ** 2 <= (0.065 * s) ** 2:
            return C_HEADER
        if inside(x, y):
            return "#FFFFFF"
        return C_HEADER
    return paint_image(s, s, sample, samples=3)


def flash_window(root) -> None:
    """Flash the taskbar button until the user comes back to the window (Windows), and beep."""
    try:
        root.bell()
    except Exception:
        pass
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                        ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]

        hwnd = int(root.wm_frame(), 16)
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x3 | 0xC, 0, 0)  # FLASHW_ALL | FLASHW_TIMERNOFG
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass


def auto_wrap(label) -> None:
    """Make a label's text wrap to whatever width it currently has."""
    label.bind("<Configure>", lambda e: e.widget.configure(wraplength=max(100, e.width - 8)))


def same_path(a: str, b: str) -> bool:
    """True if two path strings point to the same file (C:/x and C:\\x are the same)."""
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return a == b
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def fmt_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


# ---------------------------------------------------------------------------
# Fast readers (run inside this window, no extra Python process)
# ---------------------------------------------------------------------------
_cache_lock = threading.Lock()


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _code(value) -> str:
    """Same as price_robot.normalize_product_code."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _file_key(path: Path) -> str:
    st = path.stat()
    return f"v2|{path.resolve()}|{st.st_size}|{int(st.st_mtime)}"   # v2 = [code, name, type] rows


def read_product_rows(path: Path) -> list[list[str]]:
    """[code, name, type] for every product, using price_robot's sheet/header rules.
    Results are cached per file (path + size + date), so re-opening the same file is instant."""
    key = _file_key(path)
    with _cache_lock:
        try:
            cache = json.loads(OPTIONS_CACHE.read_text(encoding="utf-8"))
            if cache.get("key") == key:
                return cache["rows"]
        except Exception:
            pass

    from openpyxl import load_workbook  # needed by the robot anyway
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        names = [n for n in wb.sheetnames if re.fullmatch(r"MASTER-\d{4}", n, re.I)] + wb.sheetnames
        for name in names:
            it = wb[name].iter_rows(values_only=True)
            header = None
            for i, row in enumerate(it, start=1):
                normed = [norm(v) for v in row]
                if "nombre del producto" in normed and "codigo de producto" in normed:
                    header = normed
                    break
                if i >= 30:
                    break
            if header is None:
                continue
            wanted = ("codigo de producto", "nombre del producto", "sub familia de productos")
            cols = [header.index(k) if k in header else None for k in wanted]
            rows = []
            for row in it:
                vals = [row[c] if c is not None and c < len(row) else None for c in cols]
                name_text = _text(vals[1])
                if name_text:
                    rows.append([_code(vals[0]), name_text, _text(vals[2])])
            break
        else:
            raise ValueError("No worksheet containing 'Nombre del producto' was found.")
    finally:
        wb.close()

    with _cache_lock:
        try:
            OPTIONS_CACHE.write_text(json.dumps({"key": key, "rows": rows}, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return rows


def warm_products_cache() -> None:
    """In the background, pre-read the usual products.xlsx so choosing it later is instant."""
    def work():
        try:
            if DEFAULT_PRODUCTS.is_file():
                read_product_rows(DEFAULT_PRODUCTS)
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------
class Settings:
    def __init__(self):
        self.run = dict(RUN_DEFAULTS)
        self.matcher = {p["key"]: p["default"] for p in PARAMS}
        self.last = {
            "lang": "es",
            "products": "",   # never pre-filled: staff choose the file each time
            "mode": "test",
            "limit": 20,
            "contains": "",
            "type": "",   # "" = all types
            "perf": True,     # create the performance analysis workbook
            "show_log": False,  # technical details shown on the right
            "recent": {"products": [], "current": [], "results": []},
        }

    def load(self):
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        for k, v in (data.get("run") or {}).items():
            if k in self.run:
                self.run[k] = v
        # The supermarkets used to be chosen on the main window (saved under "last"); carry that choice over.
        if "stores" not in (data.get("run") or {}) and isinstance((data.get("last") or {}).get("stores"), list):
            self.run["stores"] = data["last"]["stores"]
        chosen = self.run.get("stores")
        chosen = [sid for sid, _ in STORES if isinstance(chosen, list) and sid in chosen]
        self.run["stores"] = chosen or list(RUN_DEFAULTS["stores"])
        for k, v in (data.get("matcher") or {}).items():
            if k in self.matcher:
                self.matcher[k] = v
        # The default file names became Spanish: move people still on the old English defaults.
        for key, old in (("output", "multi_store_price_matches.xlsx"), ("perf_output", "multi_store_performance_analysis.xlsx")):
            if self.run.get(key) == old:
                self.run[key] = RUN_DEFAULTS[key]
        # The default went from 6 to 100 simultaneous searches: move people still on the old default once.
        if not data.get("workers_default_version") and self.run.get("workers") == 6:
            self.run["workers"] = 100
        # Migrate the previous shipped 30% default once; retain other custom limits.
        if not data.get("review_policy_version") and self.matcher.get("PRICE_CHANGE_REVIEW_THRESHOLD") == 0.30:
            self.matcher["PRICE_CHANGE_REVIEW_THRESHOLD"] = PRICE_CHANGE_REVIEW_THRESHOLD
        for k, v in (data.get("last") or {}).items():
            if k in self.last:
                self.last[k] = v
        if self.last.get("type") in STRINGS["all_types"]:  # older versions stored the label
            self.last["type"] = ""
        self.last["products"] = ""  # always start with no products file selected
        self.last["show_log"] = False  # technical details start hidden each time the app opens
        if self.last.get("lang") not in ("es", "en"):
            self.last["lang"] = "es"

    def save(self):
        try:
            SETTINGS_FILE.write_text(
                json.dumps({"run": self.run, "matcher": self.matcher, "last": self.last, "review_policy_version": 1, "workers_default_version": 2}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def changed_matcher(self) -> dict:
        return {k: v for k, v in self.matcher.items() if v != PARAM_BY_KEY[k]["default"]}

    def changed_run(self) -> dict:
        return {k: v for k, v in self.run.items() if v != RUN_DEFAULTS[k]}


# ---------------------------------------------------------------------------
# Small widgets
# ---------------------------------------------------------------------------
class Card(tk.Frame):
    """White panel with a title."""

    def __init__(self, parent, title: str, step: str | None = None, compact: bool = False, center: bool = False):
        # highlightcolor = the border colour while focused: same as normal, so a card never shows a dark outline
        super().__init__(parent, bg=C_CARD, highlightbackground=C_BORDER, highlightcolor=C_BORDER,
                         highlightthickness=1, takefocus=0)
        holder = self
        if center:  # when the card is stretched taller, keep title and contents together in the middle
            holder = tk.Frame(self, bg=C_CARD)
            holder.pack(fill="x", expand=True)
        head = tk.Frame(holder, bg=C_CARD)
        head.pack(fill="x", padx=14 if compact else 16, pady=(8, 2) if compact else (12, 4))
        if step:
            tk.Label(head, text=step, bg=C_ACCENT, fg="white", font=(FONT, 9, "bold"), width=2).pack(side="left", padx=(0, 8))
        tk.Label(head, text=title, bg=C_CARD, fg=C_TEXT, font=(FONT, 11, "bold")).pack(side="left")
        self.body = tk.Frame(holder, bg=C_CARD)
        self.body.pack(fill="both", expand=not center, padx=14 if compact else 16, pady=(2, 8) if compact else (4, 14))


class LangToggle(tk.Frame):
    """Two-segment ES | EN switch."""

    def __init__(self, parent, bg: str, on_change, lang=None):
        super().__init__(parent, bg=bg, highlightbackground="#8FB597", highlightcolor="#8FB597", highlightthickness=1)
        self.on_change = on_change
        for code in ("es", "en"):
            active = code == (LANG if lang is None else lang)
            lbl = tk.Label(self, text=code.upper(), font=(FONT, 9, "bold"), padx=10, pady=3, cursor="hand2",
                           bg="white" if active else bg, fg=C_HEADER if active else "#CFE3D2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, c=code: self.on_change(c))


# ---------------------------------------------------------------------------
# Scrolling (mouse wheel and touchpad)
# ---------------------------------------------------------------------------
# Every scrollable area registers itself here. One handler decides what to scroll by
# looking at what is under the pointer (not which box has keyboard focus), and moves by
# the amount the touchpad/wheel reports so two-finger scrolling is smooth.
_SCROLL_VIEWS: dict[str, tuple] = {}   # container path -> (view widget, pixels per wheel notch or None for text)
_SCROLL_REMAINDER: dict[str, float] = {}


def register_scroll(container, view=None, text_lines: bool = False) -> None:
    view = view or container
    _SCROLL_VIEWS[str(container)] = (view, text_lines)


def _can_scroll(view) -> bool:
    first, last = view.yview()
    return not (first <= 0.0 and last >= 1.0)


def on_mouse_wheel(event):
    try:
        root = event.widget.winfo_toplevel() if isinstance(event.widget, tk.Misc) else None
        root = root or tk._default_root
        widget = root.winfo_containing(event.x_root, event.y_root)
    except Exception:
        return None
    if widget is None:
        return "break"
    if isinstance(widget, tk.Listbox):
        return None  # e.g. an open dropdown list: let it scroll itself
    if getattr(event, "num", 0) in (4, 5):          # Linux
        delta = 120 if event.num == 4 else -120
    else:
        delta = event.delta
    if sys.platform == "darwin":
        delta *= 30
    node = widget
    while node is not None:
        entry = _SCROLL_VIEWS.get(str(node))
        if entry is not None:
            view, text_lines = entry
            try:
                if not view.winfo_exists() or not _can_scroll(view):
                    return "break"
            except Exception:
                return "break"
            per_notch = 3 if text_lines else max(40, int(50 * ui_scale(view)))   # lines or pixels
            key = str(view)
            amount = _SCROLL_REMAINDER.get(key, 0.0) - delta / 120 * per_notch
            whole = int(amount)
            _SCROLL_REMAINDER[key] = amount - whole
            if whole:
                view.yview_scroll(whole, "units")
            return "break"
        node = getattr(node, "master", None)
    return "break"


def install_scrolling(root) -> None:
    root.bind_all("<MouseWheel>", on_mouse_wheel)
    root.bind_all("<Button-4>", on_mouse_wheel)
    root.bind_all("<Button-5>", on_mouse_wheel)
    # Text boxes, dropdowns and number boxes normally grab the wheel (and change their value);
    # send it to the page instead, so scrolling never edits a setting by accident.
    # Also bind directly on every widget class used in the window, so the page scrolls no matter
    # which part of it Windows sends the wheel/touchpad event to.
    for cls in ("Text", "TCombobox", "TSpinbox", "TEntry", "Canvas", "Frame", "Label", "Tk", "Toplevel",
                "TFrame", "TLabel", "TButton", "TCheckbutton", "TRadiobutton", "TSeparator", "TProgressbar",
                "TScrollbar", "TNotebook", "Entry", "Button"):
        root.bind_class(cls, "<MouseWheel>", on_mouse_wheel)


def slim_scrollbar(parent, command, style="Slim.Vertical.TScrollbar", autohide_pack=None):
    """A thin scrollbar. With autohide_pack, it only shows when there is something to scroll."""
    sb = ttk.Scrollbar(parent, orient="vertical", command=command, style=style)
    if autohide_pack is None:
        return sb, sb.set

    def setter(first, last):
        sb.set(first, last)
        if float(first) <= 0.0 and float(last) >= 1.0:
            if sb.winfo_ismapped():
                sb.pack_forget()
        elif not sb.winfo_ismapped():
            sb.pack(**autohide_pack)
    return sb, setter


class ScrollFrame(ttk.Frame):
    """A vertically scrollable frame (used for the advanced settings tabs)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=C_CARD, highlightthickness=0, bd=0, yscrollincrement=1)
        self.canvas.pack(side="left", fill="both", expand=True)
        pack_opts = dict(side="right", fill="y", padx=(0, 2), before=self.canvas)
        self.vsb, setter = slim_scrollbar(self, self.canvas.yview, "SlimCard.Vertical.TScrollbar", autohide_pack=pack_opts)
        self.inner = tk.Frame(self.canvas, bg=C_CARD)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=setter)
        register_scroll(self.canvas)


# ---------------------------------------------------------------------------
# Advanced settings window
# ---------------------------------------------------------------------------
class AdvancedWindow(tk.Toplevel):
    """Settings grouped by the steps the robot follows, with plain explanations and live examples."""

    def __init__(self, app: "App"):
        super().__init__(app.root)
        self.withdraw()  # build it hidden, then show it in front of the main window
        self.app = app
        self.settings = app.settings
        self.configure(bg=C_BG)
        self.transient(app.root)
        fit_window(self, 1080, 840, 760, 540)
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.vars: dict[str, tk.StringVar] = {}
        self.marks: dict[str, tk.Label] = {}
        self.examples: dict[str, tk.Label] = {}
        self.resets: dict[str, ttk.Button] = {}
        self.nav: dict[str, dict] = {}
        self.pages: dict[str, ScrollFrame] = {}
        self.expert_frames: dict[str, tk.Frame] = {}
        self.expert_toggles: dict[str, ttk.Button] = {}
        self.pending: dict[str, str] = {}   # values for settings whose page has not been built yet
        self.current = None
        self._build()
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)                            # Windows may otherwise open it
        self.after(300, lambda: self.attributes("-topmost", False))  # behind the main window
        self.focus_force()
        self.grab_set()
        self.after(80, self.focus_force)  # once it is on screen, so Esc works right away

    def close(self):
        """Close the window. Uses Tk's own destroy (the same path as the window's X button)."""
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.tk.call("destroy", self._w)
        finally:
            self.master.children.pop(self._name, None)
            self.app.advanced = None
            try:
                self.app.root.focus_force()
            except Exception:
                pass

    # -- values -------------------------------------------------------------
    def _stored(self, p):
        return self.settings.run[p["key"]] if p["store"] == "run" else self.settings.matcher[p["key"]]

    def _shown(self, p, value) -> str:
        return str(value) if p["kind"] in ("choice", "text", "folder") else display_value(p, value)

    def _text_now(self, p) -> str:
        """What is entered for a setting (its page may not have been built yet)."""
        if p["key"] in self.vars:
            return self.vars[p["key"]].get()
        return self.pending.get(p["key"], self._shown(p, self._stored(p)))

    def _parsed(self, p):
        """(value, error) for what is currently entered."""
        try:
            return parse_param(p, self._text_now(p)), None
        except ValueError as exc:
            return None, str(exc)

    # -- layout -------------------------------------------------------------
    def _build(self):
        self.title(t("adv_title"))
        top = tk.Frame(self, bg=C_BG)
        top.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(top, text=t("adv_title"), bg=C_BG, fg=C_TEXT, font=(FONT, 15, "bold")).pack(anchor="w")
        intro = tk.Label(top, text=t("adv_intro"), bg=C_BG, fg=C_MUTED, font=(FONT, 9), justify="left", anchor="w")
        intro.pack(fill="x", pady=(2, 0))
        auto_wrap(intro)

        bar = tk.Frame(self, bg=C_BG)
        bar.pack(side="bottom", fill="x", padx=20, pady=12)
        ttk.Button(bar, text=t("reset_all"), command=self.reset_all).pack(side="left")
        ttk.Button(bar, text=t("save"), style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(bar, text=t("cancel"), command=self.close).pack(side="right", padx=8)

        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True, padx=20, pady=(8, 0))

        # left: the steps, in order
        nav = tk.Frame(body, bg=C_BG, width=int(270 * ui_scale(self)))
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Label(nav, text=t("nav_heading"), bg=C_BG, fg=C_MUTED, font=(FONT, 9, "bold"), anchor="w").pack(fill="x", pady=(0, 6))
        for i, (sid, title, subtitle, _intro) in enumerate(ADV_SECTIONS, start=1):
            self._nav_item(nav, sid, i, L(title), L(subtitle))

        # right: one scrollable page per step, each built the first time it is opened
        self.content = tk.Frame(body, bg=C_CARD, highlightbackground=C_BORDER, highlightcolor=C_BORDER, highlightthickness=1)
        self.content.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self._refresh_counts()
        self.show(ADV_SECTIONS[0][0])

    def _nav_item(self, parent, sid, number, title, subtitle):
        item = tk.Frame(parent, bg=C_BG, cursor="hand2")
        item.pack(fill="x", pady=2)
        accent = tk.Frame(item, bg=C_BG, width=4)
        accent.pack(side="left", fill="y")
        inner = tk.Frame(item, bg=C_BG)
        inner.pack(side="left", fill="both", expand=True, padx=(8, 6), pady=7)
        head = tk.Frame(inner, bg=C_BG)
        head.pack(fill="x")
        badge = tk.Label(head, text=str(number), bg=C_ACCENT, fg="white", font=(FONT, 9, "bold"), width=2)
        badge.pack(side="left")
        name = tk.Label(head, text=title, bg=C_BG, fg=C_TEXT, font=(FONT, 10, "bold"), anchor="w")
        name.pack(side="left", padx=(8, 0))
        sub = tk.Label(inner, text=subtitle, bg=C_BG, fg=C_MUTED, font=(FONT, 9), anchor="w", justify="left")
        sub.pack(fill="x", padx=(30, 0))
        count = tk.Label(inner, text="", bg=C_BG, fg=C_WARN, font=(FONT, 8, "bold"), anchor="w")
        count.pack(fill="x", padx=(30, 0))
        widgets = [item, inner, head, name, sub, count]
        for w in widgets + [badge, accent]:
            w.bind("<Button-1>", lambda e, s=sid: self.show(s))
        self.nav[sid] = {"widgets": widgets, "accent": accent, "count": count}

    def _page(self, sid, number, title, intro_text):
        page = ScrollFrame(self.content)
        self.pages[sid] = page
        body = page.inner

        head = tk.Frame(body, bg=C_CARD)
        head.pack(fill="x", padx=22, pady=(18, 0))
        tk.Label(head, text=f"{number}. {title}", bg=C_CARD, fg=C_TEXT, font=(FONT, 14, "bold")).pack(side="left")
        ttk.Button(head, text=t("reset_section"), style="Link.TButton",
                   command=lambda s=sid: self.reset_section(s)).pack(side="right")
        box = tk.Frame(body, bg="#EEF5EF")
        box.pack(fill="x", padx=22, pady=(8, 4))
        lbl = tk.Label(box, text=intro_text, bg="#EEF5EF", fg=C_TEXT, font=(FONT, 10), justify="left", anchor="w")
        lbl.pack(fill="x", padx=12, pady=10)
        auto_wrap(lbl)

        basics = [p for p in SETTINGS_SPEC if p["section"] == sid and p["level"] == "basic"]
        experts = [p for p in SETTINGS_SPEC if p["section"] == sid and p["level"] == "expert"]
        for p in basics:
            self._row(body, p)
        if experts:
            ex_head = tk.Frame(body, bg=C_CARD)
            ex_head.pack(fill="x", padx=22, pady=(16, 0))
            toggle = ttk.Button(ex_head, text="", style="Link.TButton", command=lambda s=sid: self.toggle_expert(s))
            toggle.pack(side="left")
            tk.Label(ex_head, text=t("expert_hint"), bg=C_CARD, fg=C_MUTED, font=(FONT, 9)).pack(side="left", padx=6)
            frame = tk.Frame(body, bg=C_CARD)
            self.expert_toggles[sid] = toggle
            self.expert_frames[sid] = frame
            for p in experts:
                self._row(frame, p)
            # open automatically when one of them was already changed
            opened = any(self._parsed(p)[0] != p["default"] for p in experts)
            frame._open = False
            if opened:
                self.toggle_expert(sid)
            else:
                self._expert_label(sid)
        tk.Frame(body, bg=C_CARD, height=18).pack(fill="x")

    def _row(self, parent, p):
        key = p["key"]
        card = tk.Frame(parent, bg=C_CARD, highlightbackground=C_BORDER, highlightcolor=C_BORDER, highlightthickness=1)
        card.pack(fill="x", padx=22, pady=(10, 0))
        top = tk.Frame(card, bg=C_CARD)
        top.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(top, text=L(p["label"]), bg=C_CARD, fg=C_TEXT, font=(FONT, 10, "bold")).pack(side="left")
        mark = tk.Label(top, text="", bg=C_CARD, fg=C_WARN, font=(FONT, 9, "bold"))
        mark.pack(side="left", padx=(8, 0))
        reset = ttk.Button(top, text=t("reset_one"), style="Link.TButton", command=lambda k=key: self.reset_one(k))
        self.marks[key], self.resets[key] = mark, reset

        var = tk.StringVar(value=self.pending.pop(key, self._shown(p, self._stored(p))))
        self.vars[key] = var
        if p["kind"] in ("int", "float", "percent", "text"):
            holder = tk.Frame(top, bg=C_CARD)
            holder.pack(side="right")
            if p["kind"] == "text":
                ttk.Entry(holder, textvariable=var, width=40).pack(side="left")
            else:
                step = 1 if p["kind"] in ("int", "percent") else p.get("step", 0.05)
                ttk.Spinbox(holder, from_=p["lo"], to=p["hi"], increment=step, textvariable=var,
                            width=7).pack(side="left")
                unit = "%" if p["kind"] == "percent" else ""
                if p.get("unit"):
                    unit = f"{unit} {L(p['unit'])}".strip()
                if unit:
                    tk.Label(holder, text=unit, bg=C_CARD, fg=C_MUTED, font=(FONT, 9)).pack(side="left", padx=(6, 0))

        help_lbl = tk.Label(card, text=L(p["help"]), bg=C_CARD, fg=C_MUTED, font=(FONT, 9), justify="left", anchor="w")
        help_lbl.pack(fill="x", padx=14, pady=(3, 0))
        auto_wrap(help_lbl)
        if p["kind"] == "folder":
            frow = tk.Frame(card, bg=C_CARD)
            frow.pack(fill="x", padx=14, pady=(6, 0))
            ttk.Entry(frow, textvariable=var).pack(side="left", fill="x", expand=True)
            ttk.Button(frow, text=t("browse"), command=lambda v=var: self._pick_folder(v)).pack(side="left", padx=(8, 0))
        if p["kind"] == "stores":
            self._store_boxes(card, var)
        if p["kind"] == "choice":
            radios = tk.Frame(card, bg=C_CARD)
            radios.pack(fill="x", padx=14, pady=(6, 0))
            for val, pair in p["choices"]:
                ttk.Radiobutton(radios, text=L(pair), value=val, variable=var).pack(anchor="w", pady=1)
        example = tk.Label(card, text="", bg=C_CARD, fg=C_ACCENT_DARK, font=(FONT, 9), justify="left", anchor="w")
        example.pack(fill="x", padx=14, pady=(4, 0))
        auto_wrap(example)
        self.examples[key] = example
        default_text = self._default_text(p)
        tk.Label(card, text=t("default_is", v=default_text), bg=C_CARD, fg="#8A958C", font=(FONT, 8),
                 anchor="w").pack(fill="x", padx=14, pady=(2, 10))
        var.trace_add("write", lambda *_a, k=key: self._refresh(k))

    def _store_boxes(self, card, var):
        """One checkbox per supermarket, kept in sync with the setting's text value ("super99,rey,...")."""
        row = tk.Frame(card, bg=C_CARD)
        row.pack(fill="x", padx=14, pady=(6, 0))
        boxes = {}
        syncing = [False]

        def from_boxes(*_a):
            if not syncing[0]:
                var.set(",".join(sid for sid, _ in STORES if boxes[sid].get()))

        def from_var(*_a):
            chosen = {part.strip() for part in var.get().split(",")}
            syncing[0] = True
            try:
                for sid, b in boxes.items():
                    if b.get() != (sid in chosen):
                        b.set(sid in chosen)
            finally:
                syncing[0] = False

        chosen = {part.strip() for part in var.get().split(",")}
        for sid, name in STORES:
            b = tk.BooleanVar(value=sid in chosen)
            ttk.Checkbutton(row, text=name, variable=b).pack(side="left", padx=(0, 22))
            b.trace_add("write", from_boxes)
            boxes[sid] = b
        ttk.Button(row, text=t("all"), style="Link.TButton",
                   command=lambda: var.set(",".join(sid for sid, _ in STORES))).pack(side="right")
        var.trace_add("write", from_var)
        self.store_boxes = boxes

    def _pick_folder(self, var):
        start = var.get().strip() or str(BASE_DIR)
        folder = filedialog.askdirectory(parent=self, title=t("pick_folder_title"),
                                         initialdir=start if Path(start).is_dir() else str(BASE_DIR))
        if folder:
            var.set(folder)

    def _current_values(self) -> dict:
        """Everything entered so far (defaults where a value is not valid) — used by the live previews."""
        vals = {}
        for p in SETTINGS_SPEC:
            value, error = self._parsed(p)
            vals[p["key"]] = p["default"] if error else value
        return vals

    def _default_text(self, p) -> str:
        if p["kind"] == "stores":
            return t("all_stores")
        if p["kind"] == "folder":
            return t("project_folder")
        if p["kind"] == "choice":
            return L(dict(p["choices"])[p["default"]])
        if p["kind"] == "text":
            return str(p["default"])
        text = display_value(p, p["default"]) + (" %" if p["kind"] == "percent" else "")
        if p.get("unit"):
            text += f" {L(p['unit'])}"
        return text

    # -- navigation ---------------------------------------------------------
    def _ensure_page(self, sid):
        if sid in self.pages:
            return
        for i, (s_id, title, _subtitle, intro_text) in enumerate(ADV_SECTIONS, start=1):
            if s_id == sid:
                self._page(sid, i, L(title), L(intro_text))
        for p in SETTINGS_SPEC:
            if p["section"] == sid:
                self._refresh(p["key"])

    def show(self, sid):
        self._ensure_page(sid)
        if self.current:
            self.pages[self.current].pack_forget()
        self.current = sid
        self.pages[sid].pack(fill="both", expand=True)
        self.pages[sid].canvas.yview_moveto(0)
        for s, item in self.nav.items():
            selected = s == sid
            bg = C_CARD if selected else C_BG
            for w in item["widgets"]:
                w.configure(bg=bg)
            item["accent"].configure(bg=C_ACCENT if selected else C_BG)

    def toggle_expert(self, sid):
        frame = self.expert_frames[sid]
        if frame._open:
            frame.pack_forget()
        else:
            frame.pack(fill="x", after=self.expert_toggles[sid].master)
        frame._open = not frame._open
        self._expert_label(sid)

    def _expert_label(self, sid):
        frame = self.expert_frames[sid]
        n = sum(1 for p in SETTINGS_SPEC if p["section"] == sid and p["level"] == "expert")
        key = "expert_hide" if frame._open else "expert_show"
        self.expert_toggles[sid].configure(text=t(key, n=n))

    # -- live feedback --------------------------------------------------------
    def _refresh(self, key):
        p = SPEC_BY_KEY[key]
        value, error = self._parsed(p)
        mark, reset, example = self.marks[key], self.resets[key], self.examples[key]
        if error:
            mark.configure(text=f"● {error}", fg=C_ERROR)
        else:
            mark.configure(text=t("modified") if value != p["default"] else "", fg=C_WARN)
        changed = error is not None or value != p["default"]
        if changed and not getattr(reset, "_visible", False):
            reset.pack(side="left", padx=(6, 0), after=mark)
            reset._visible = True
        elif not changed and getattr(reset, "_visible", False):
            reset.pack_forget()
            reset._visible = False
        if p["section"] == "output":
            # the file-name previews depend on several settings at once
            vals = self._current_values()
            for q in SETTINGS_SPEC:
                if q.get("example_all") and q["key"] in self.examples:
                    try:
                        self.examples[q["key"]].configure(text="→ " + L(q["example_all"](vals)))
                    except Exception:
                        self.examples[q["key"]].configure(text="")
        if p.get("example"):
            try:
                text = "" if error and p["kind"] == "stores" else L(p["example"](value if error is None else p["default"]))
            except Exception:
                text = ""
            example.configure(text=("→ " + text) if text else "")
        self._refresh_counts()

    def _refresh_counts(self):
        for sid, item in self.nav.items():
            n = 0
            for p in SETTINGS_SPEC:
                if p["section"] != sid:
                    continue
                value, error = self._parsed(p)
                if error or value != p["default"]:
                    n += 1
            item["count"].configure(text=t("n_modified", n=n) if n else "")

    # -- resets ---------------------------------------------------------------
    def reset_one(self, key):
        p = SPEC_BY_KEY[key]
        if key in self.vars:
            self.vars[key].set(self._shown(p, p["default"]))
        else:
            self.pending[key] = self._shown(p, p["default"])
            self._refresh_counts()

    def reset_section(self, sid):
        for p in SETTINGS_SPEC:
            if p["section"] == sid:
                self.reset_one(p["key"])

    def reset_all(self):
        if messagebox.askyesno(t("reset_all"), t("confirm_reset"), parent=self):
            for p in SETTINGS_SPEC:
                self.reset_one(p["key"])

    # -- save -----------------------------------------------------------------
    def _fail(self, p, message):
        self.show(p["section"])
        if p["level"] == "expert" and not self.expert_frames[p["section"]]._open:
            self.toggle_expert(p["section"])
        messagebox.showerror(t("invalid_title"), f"{L(p['label'])}: {message}", parent=self)

    def save(self):
        values = {}
        for p in SETTINGS_SPEC:
            value, error = self._parsed(p)
            if error:
                self._fail(p, error + ".")
                return
            values[p["key"]] = value

        if values["MIN_SIZE_RATIO"] > values["PREFERRED_SIZE_RATIO_MIN"]:
            self._fail(SPEC_BY_KEY["PREFERRED_SIZE_RATIO_MIN"], t("err_pref_min"))
            return
        if values["PREFERRED_SIZE_RATIO_MAX"] > values["MAX_SIZE_RATIO"]:
            self._fail(SPEC_BY_KEY["PREFERRED_SIZE_RATIO_MAX"], t("err_pref_max"))
            return
        output, perf = values["output"], values["perf_output"]
        if not output or Path(output).name != output or Path(output).suffix.lower() not in (".xlsx", ".csv"):
            self._fail(SPEC_BY_KEY["output"], t("err_output"))
            return
        if not perf or Path(perf).name != perf or Path(perf).suffix.lower() != ".xlsx":
            self._fail(SPEC_BY_KEY["perf_output"], t("err_perf_output"))
            return
        if output.lower() == perf.lower():
            self._fail(SPEC_BY_KEY["perf_output"], t("err_same_names"))
            return
        folder = values["output_dir"]
        if folder and not Path(folder).is_dir():
            self._fail(SPEC_BY_KEY["output_dir"], t("err_folder"))
            return

        for p in SETTINGS_SPEC:
            target = self.settings.run if p["store"] == "run" else self.settings.matcher
            target[p["key"]] = values[p["key"]]
        self.settings.save()
        self.app.refresh_settings_badge()
        self.close()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
def input_files_problem(products, current) -> str | None:
    """A message when the products or current-prices file lacks a required column (or can't be read);
    None when both are fine. The search can't start until this is None."""
    from current_prices import product_columns_missing, current_prices_columns_missing, read_current_rows
    bullets = lambda cols: "\n".join("•  " + c for c in cols)
    try:
        missing = product_columns_missing(products)
    except Exception as exc:
        return t("err_file_read", path=products, error=exc)
    if missing:
        return t("err_products_columns", cols=bullets(missing), path=products)
    try:
        missing = current_prices_columns_missing(current)
        if missing:
            return t("err_current_columns", cols=bullets(missing), path=current)
        rows = read_current_rows(current)   # also catches duplicate codes and invalid prices
        if rows and not any(row.get("Id") for row in rows):
            return t("err_current_columns", cols="•  Id (" + L(("columna vacía", "empty column")) + ")", path=current)
    except Exception as exc:
        return t("err_file_read", path=current, error=exc)
    return None


def _without_focus(layout):
    """A ttk layout with every "*.focus" element taken out (its contents are kept)."""
    result = []
    for name, options in layout or []:
        options = dict(options or {})
        children = _without_focus(options.pop("children", None))
        if name.endswith(".focus"):
            result.extend(children)
            continue
        if children:
            options["children"] = children
        result.append((name, options))
    return result


def remove_focus_outlines(root, style):
    """No focus outlines anywhere: no dashed ring on buttons / checkboxes / radio buttons / tabs, no dotted
    ring on list rows, no darker border on the field being typed in, no highlight ring on tk widgets."""
    for name in ("TButton", "TCheckbutton", "TRadiobutton", "TMenubutton", "TNotebook.Tab", "Toolbutton",
                 "Item", "Treeview.Item", "TCombobox", "TEntry", "TSpinbox"):
        try:
            layout = style.layout(name)
        except tk.TclError:
            continue
        if layout:
            try:
                style.layout(name, _without_focus(layout))
            except tk.TclError:
                pass
    style.configure(".", focuscolor="")
    for name in ("TEntry", "TCombobox", "TSpinbox"):   # same border whether or not the field is focused
        style.map(name, bordercolor=[], lightcolor=[])
    # The theme paints a focused drop-down list blue with white text; keep it dark text on white instead
    # (the selected text inside it too, so nothing looks highlighted).
    style.map("TCombobox", foreground=[("disabled", "#8A958C")], fieldbackground=[("readonly", "white")],
              selectbackground=[("readonly", "white")], selectforeground=[("readonly", C_TEXT)])
    for widget_class in ("Text", "Canvas", "Listbox", "Entry", "Spinbox", "Button", "Checkbutton",
                         "Radiobutton", "Scale", "Label", "Frame"):
        root.option_add(f"*{widget_class}.highlightThickness", 0)


def asset_path(name) -> Path:
    """A file shipped with the app (inside the .exe when built, next to this file when run from source)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / name


def header_photos(root, height):
    """The header photos (assets/header_photo_1.png … _4.png), each scaled to `height` pixels tall."""
    images = []
    for number in range(1, 5):
        path = asset_path(f"header_photo_{number}.png")
        if not path.is_file():
            continue
        try:
            image = tk.PhotoImage(master=root, file=str(path))
        except tk.TclError:
            continue
        # Tk scales images by whole numbers only, so zoom by a and shrink by b: the smallest a/b (small
        # numbers) that makes the photo at least `height` tall, so it always fills the panel.
        target = height / image.height()
        best = None
        for b in range(1, 13):
            for a in range(1, 6):
                if a / b >= target - 1e-9 and (best is None or a / b < best[0] / best[1]):
                    best = (a, b)
        a, b = best or (1, 1)
        if a > 1:
            image = image.zoom(a)
        images.append(image.subsample(b) if b > 1 else image)
    return images


def _panel_image(image, panel, slant, height, cut_left):
    """A copy of `image` cropped to one panel's box (panel + slant wide), with the triangle left of the "/"
    diagonal made see-through so the previous photo shows there."""
    box_w = panel + slant
    x0 = max(0, (image.width() - box_w) // 2)
    y0 = max(0, (image.height() - height) // 2)
    piece = tk.PhotoImage(width=box_w, height=height)
    piece.tk.call(piece, "copy", image, "-from", x0, y0, x0 + box_w, y0 + height, "-to", 0, 0)
    if cut_left:
        for y in range(height):
            edge = int(round(slant * (1 - y / max(1, height - 1))))   # diagonal: `slant` at the top, 0 at the bottom
            for x in range(edge):
                piece.transparency_set(x, y, True)
    return piece


def draw_header_photos(canvas, images, width, height, panel, slant, gap, green):
    """Draw the photos as slanted "/" panels side by side, with a thin green diagonal between neighbours and
    plain header green outside the first and last panel."""
    key = (tuple(str(i) for i in images), width, height, panel, slant, gap)
    if getattr(canvas, "_drawn", None) == key:
        return
    canvas._drawn = key
    canvas.delete("all")
    canvas.configure(width=width, height=height)
    canvas._pieces = [_panel_image(image, panel, slant, height, cut_left=k > 0) for k, image in enumerate(images)]
    for k, piece in enumerate(canvas._pieces):
        canvas.create_image(k * panel, 0, image=piece, anchor="nw")
    green_kw = dict(fill=green, outline=green)
    canvas.create_polygon(-2, -2, slant, -2, 0, height + 2, -2, height + 2, **green_kw)            # left edge
    for k in range(1, len(images)):
        x = k * panel   # bottom of the k-th divider; its top is `slant` further right
        canvas.create_polygon(x - gap / 2, height + 2, x + slant - gap / 2, -2, x + slant + gap / 2, -2,
                              x + gap / 2, height + 2, **green_kw)
    right = len(images) * panel
    canvas.create_polygon(right, height + 2, right + slant, -2, width + 2, -2, width + 2, height + 2, **green_kw)


def results_are_self_contained(path) -> bool:
    """True when a results file can be reviewed and exported without the current-prices file."""
    path = Path(path)
    saved = path.with_suffix(path.suffix + ".review.json")
    try:
        if saved.is_file() and json.loads(saved.read_text(encoding="utf-8")).get("template_rows"):
            return True
    except (ValueError, OSError):
        pass
    try:
        from current_prices import is_spreadsheet, read_text_table
        if not is_spreadsheet(path):
            rows, _ = read_text_table(path)
            headers = rows[0] if rows else []
        else:
            from openpyxl import load_workbook
            from results_format import SUMMARY_SHEET, find_sheet
            wb = load_workbook(path, read_only=True)
            try:
                ws = find_sheet(wb, SUMMARY_SHEET) or wb.active
                headers = next(ws.iter_rows(max_row=1, values_only=True), ())
            finally:
                wb.close()
        from results_format import internal_header
        return "Salesforce Id" in [internal_header(h) for h in headers]
    except Exception:
        return False


class App:
    def __init__(self, root: tk.Tk):
        global LANG
        self.root = root
        self.settings = Settings()
        self.settings.load()
        LANG = self.settings.last["lang"]

        self.proc: subprocess.Popen | None = None
        self.lines: queue.Queue = queue.Queue()
        self.ui_calls: queue.Queue = queue.Queue()   # work finished in background threads, run on the main thread
        self.total = 0
        self.done = 0
        self.started_at = 0.0
        self.output_path: Path | None = None
        self.perf_path: Path | None = None
        self.log_tail: list[str] = []
        self.stopped_by_user = False
        self._last_name = None
        self._rows: list[tuple] = []        # (code, name_norm, type, type_norm) from the products file
        self._opts_state = "loading"          # loading | ok | no_file | missing_file | error
        self._opts_error = ""
        self._opts_after = None
        # file choices for this session only (never pre-filled when the app opens)
        self.session = {"current": ""}
        self._log_text = ""
        self.progress_was_done = False

        self._loading_slow = False             # "Loading…" only shows if the products file takes a while
        self._loading_timer = None

        root.configure(bg=C_BG)
        try:
            root.attributes("-alpha", 0.0)     # build the window invisibly, then show it complete in one go
        except Exception:
            pass
        fit_window(root, 1250, 900, 820, 640)
        try:
            self._icons = [app_icon(64), app_icon(32), app_icon(16)]
            root.iconphoto(True, *self._icons)   # also used by the Advanced settings window
        except Exception:
            pass
        self._style()
        install_scrolling(root)
        self._build()
        self.load_options()
        self._settle_layout()
        try:
            root.attributes("-alpha", 1.0)
        except Exception:
            pass
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(100, self._poll)
        warm_products_cache()

    def _settle_layout(self, measure=True):
        """Draw the header photos straight away, so they don't pop in after the rest of the window."""
        try:
            if measure:
                self.root.update_idletasks()
            self._place_strip()
            if measure:
                self.root.update()   # let everything paint while the window is still invisible
        except tk.TclError:
            pass

    # -- style --------------------------------------------------------------
    def _style(self):
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        remove_focus_outlines(self.root, st)
        st.configure(".", font=(FONT, 10), background=C_CARD, foreground=C_TEXT)
        st.configure("TFrame", background=C_CARD)
        st.configure("TCheckbutton", background=C_CARD, font=(FONT, 10))
        # checkboxes with a real ✓ instead of the theme's ✕
        try:
            self._check_imgs = checkbox_images(ui_scale(self.root))
            im = self._check_imgs
            st.element_create("Tick.indicator", "image", str(im["off"]),
                              ("disabled", "selected", str(im["on_disabled"])),
                              ("disabled", str(im["off_disabled"])),
                              ("selected", "active", str(im["on_hover"])),
                              ("selected", str(im["on"])),
                              ("active", str(im["off_hover"])))
            st.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
                ("Tick.indicator", {"side": "left", "sticky": ""}),
                ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                    ("Checkbutton.label", {"sticky": "nswe"})]})]})])
        except Exception:
            pass  # fall back to the theme's own checkbox
        # read-only dropdowns should look usable (white), not greyed out
        st.map("TCombobox", fieldbackground=[("readonly", "white"), ("disabled", "#F1F3F1")],
               selectbackground=[("readonly", "white")], selectforeground=[("readonly", C_TEXT)],
               background=[("readonly", "white")])
        st.configure("Small.TButton", padding=(8, 4), font=(FONT, 9))
        st.configure("TRadiobutton", background=C_CARD, font=(FONT, 10))
        st.map("TCheckbutton", background=[("active", C_CARD)])
        st.map("TRadiobutton", background=[("active", C_CARD)])
        st.configure("TButton", padding=(12, 6))
        st.configure("Accent.TButton", background=C_ACCENT, foreground="white", padding=(18, 8),
                     font=(FONT, 11, "bold"), bordercolor=C_ACCENT_DARK)
        st.map("Accent.TButton",
               background=[("disabled", "#A5C8A7"), ("active", C_ACCENT_DARK), ("pressed", C_ACCENT_DARK)],
               foreground=[("disabled", "white")])
        st.configure("Stop.TButton", foreground=C_ERROR, padding=(14, 8), font=(FONT, 10, "bold"))
        st.configure("Start.TButton", background=C_ACCENT, foreground="white", padding=(18, 10),
                     font=(FONT, 12, "bold"), bordercolor=C_ACCENT_DARK)
        st.map("Start.TButton",
               background=[("disabled", "#A5C8A7"), ("active", C_ACCENT_DARK), ("pressed", C_ACCENT_DARK)],
               foreground=[("disabled", "white")])
        st.map("Stop.TButton", foreground=[("disabled", "#A7B0A9")])
        st.configure("Link.TButton", foreground=C_ACCENT, padding=(4, 2), relief="flat", borderwidth=0, background=C_CARD)
        st.map("Link.TButton", background=[("active", C_CARD)], foreground=[("active", C_ACCENT_DARK)])
        st.configure("green.Horizontal.TProgressbar", troughcolor="#E6ECE6", background=C_ACCENT,
                     bordercolor="#E6ECE6", lightcolor=C_ACCENT, darkcolor=C_ACCENT, thickness=14)
        # slim, flat scrollbars without arrow buttons
        width = max(8, int(10 * ui_scale(self.root)))
        for name, trough, thumb, hover in (
            ("Slim.Vertical.TScrollbar", C_BG, "#C3CCC4", "#94A597"),
            ("SlimCard.Vertical.TScrollbar", C_CARD, "#C3CCC4", "#94A597"),
            ("Dark.Vertical.TScrollbar", "#10160F", "#3C4B3E", "#5B6F5E"),
        ):
            st.layout(name, [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
            st.configure(name, troughcolor=trough, background=thumb, bordercolor=trough, lightcolor=thumb,
                         darkcolor=thumb, arrowcolor=thumb, gripcount=0, relief="flat", borderwidth=0,
                         arrowsize=width, width=width)
            st.map(name, background=[("pressed", hover), ("active", hover)],
                   lightcolor=[("pressed", hover), ("active", hover)], darkcolor=[("pressed", hover), ("active", hover)])
        st.configure("TNotebook", background=C_BG, borderwidth=0)
        # main tabs: sit on the green header strip; the selected tab joins the page below it
        st.configure("Main.TNotebook", background=C_HEADER, borderwidth=0, tabmargins=(18, 0, 0, 0))
        st.configure("Main.TNotebook.Tab", font=(FONT, 11, "bold"), padding=(22, 9), background="#2F6A3D",
                     foreground="#D7EAD9", borderwidth=0, lightcolor=C_HEADER, bordercolor=C_HEADER, focuscolor=C_HEADER)
        # Same tab layout as the theme but without the focus element, so clicking a tab draws no focus box.
        st.layout("Main.TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
            ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                ("Notebook.label", {"side": "top", "sticky": ""})]})]})])
        st.map("Main.TNotebook.Tab", background=[("selected", C_BG), ("active", "#3B7A49")],
               foreground=[("selected", C_HEADER), ("active", "white")],
               lightcolor=[("selected", C_BG)], bordercolor=[("selected", C_BG)],
               padding=[("selected", (22, 9))], expand=[("selected", (0, 0, 0, 0))])
        st.configure("TNotebook.Tab", padding=(14, 6), font=(FONT, 10))

    # -- language -----------------------------------------------------------
    def set_language(self, lang: str):
        """Switch language and rebuild the main window, keeping everything the user entered."""
        global LANG
        if lang == LANG:
            return
        self._capture_inputs()
        LANG = lang
        self.settings.last["lang"] = lang
        self.settings.save()
        self._log_text = "" if getattr(self, "_log_placeholder", False) else self.log.get("1.0", "end-1c")
        on_review_tab = self.tabs.select() == str(self.review_tab)
        # The review tab is kept as it is (the price sheet is not read again); only its texts change.
        # Build the new window first and only then remove the old one, so the screen never shows it empty.
        old = [w for w in self.root.winfo_children() if not isinstance(w, tk.Toplevel) and w is not self.review_tab]
        self._relabel_review_tab()   # (the slow part, done while the old window is still showing)
        self._build()
        for w in old:
            w.destroy()
        self._apply_options()
        self._render_status()   # status + details under the progress bar, now in the new language
        if self.output_path and self.output_path.exists() and self.progress_was_done:
            self.progress.configure(maximum=1, value=1)
            self._show_results_row()
        if on_review_tab:
            self.tabs.select(self.review_tab)
        self._settle_layout(measure=False)   # same size as before: no need to show a half-drawn window first

    def on_lang_click(self, lang: str):
        if self.proc and lang != LANG:
            messagebox.showinfo(t("app_title"), t("busy_lang"))
            return
        self.set_language(lang)

    def _capture_inputs(self):
        """Copy the current form values into settings.last (no validation)."""
        last = self.settings.last
        last["products"] = self.products_var.get().strip()
        last["mode"] = "test" if self.scope_var.get() == "first" else "all"   # "problems" is chosen again each session
        try:
            last["limit"] = max(1, int(self.limit_var.get()))
        except Exception:
            pass
        last["contains"] = self.contains_var.get().strip()
        last["type"] = self.selected_type()
        last["perf"] = bool(self.perf_var.get())
        self.session.update(current=self.current_var.get().strip())

    def selected_type(self) -> str:
        value = self.type_var.get()
        return "" if value in STRINGS["all_types"] else value

    # -- layout -------------------------------------------------------------
    def _build(self):
        last = self.settings.last
        self.root.title(t("app_title"))

        header = tk.Frame(self.root, bg=C_HEADER)
        header.pack(fill="x")
        titles = tk.Frame(header, bg=C_HEADER)
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(titles, text=t("app_title"), bg=C_HEADER, fg="white", font=(FONT, 17, "bold")).pack(anchor="w", padx=22, pady=(10, 0))
        tk.Label(titles, text=t("app_subtitle"), bg=C_HEADER, fg="#CFE3D2", font=(FONT, 10)).pack(anchor="w", padx=22, pady=(0, 8))
        toggle = LangToggle(header, C_HEADER, self.on_lang_click)
        toggle.pack(side="right", padx=22)
        # Four photos in slanted "/" panels in the open green space between the title and the ES/EN switch.
        # They run from the top of the window down to where the white page starts (through the tab row, right
        # of the tabs). The panels get narrower when there is less room, so all four always show in full.
        strip = tk.Canvas(self.root, bg=C_HEADER, bd=0, highlightthickness=0)
        self._header_photos = []
        cache = self.__dict__.setdefault("_photo_cache", {})   # scaled photos, kept across language switches
        tab_font = tkfont.Font(family=FONT, size=11, weight="bold")

        def place_strip(_event=None):
            if not strip.winfo_exists() or not hasattr(self, "tabs") or not self.tabs.winfo_exists():
                return
            try:   # measure from whichever page is open (the search or the review tab)
                page = self.root.nametowidget(self.tabs.select())
            except (KeyError, tk.TclError):
                page = self._search_tab
            scale = ui_scale(self.root)
            # header + tab row, down to the page's top edge line (not over it, so the bottom of the green is level
            # across the whole window); the edge is as thick as the page's bottom border
            edge = max(0, (self.tabs.winfo_rooty() + self.tabs.winfo_height())
                       - (page.winfo_rooty() + page.winfo_height()))
            height = page.winfo_rooty() - header.winfo_rooty() - edge
            # Right after a rebuild (e.g. a language switch with the review open) the new tabs can briefly sit
            # over the header, which would measure only part of it: wait until the tabs are below the header.
            laid_out = (height >= 20 and page.winfo_ismapped() and header.winfo_ismapped()
                        and self.tabs.winfo_ismapped() and page.winfo_y() > 0
                        and self.tabs.winfo_rooty() >= header.winfo_rooty() + header.winfo_height() - 2)
            if not laid_out:
                self.root.after(100, place_strip)   # the window isn't laid out yet: measure again shortly
                height = getattr(self, "_strip_height", 0)   # meanwhile use the last size (a rebuild keeps it)
                if height < 20:
                    return
            self._strip_height = height
            if height not in cache:
                cache.clear()
                cache[height] = header_photos(self.root, height)
            self._header_photos = cache[height]
            if not self._header_photos:
                return
            title_right = max(w.winfo_reqwidth() for w in titles.winfo_children()) + int(22 * 2 * scale)
            tabs_right = int(18 * scale) + sum(tab_font.measure(self.tabs.tab(i, "text")) + int((22 * 2 + 4) * scale)
                                               for i in range(self.tabs.index("end")))
            space_left = max(title_right, tabs_right + int(16 * scale))
            header_width = header.winfo_width() if laid_out else self.root.winfo_width()
            space_right = header_width - toggle.winfo_reqwidth() - int(22 * 2 * scale)
            room = max(0, space_right - space_left)
            count = len(self._header_photos)
            slant, gap = round(height * 0.36), max(2, round(height * 0.05))
            panel = min(round(height * 1.9), (room - slant) // count)   # width of each panel at its middle
            if panel < height * 0.5:
                strip.place_forget()
                return
            width = panel * count + slant
            draw_header_photos(strip, self._header_photos, width, height, panel, slant, gap, C_HEADER)
            strip.place(x=space_left + (room - width) // 2, y=0, width=width, height=height)
            tk.Misc.lift(strip)   # (Canvas.lift would raise a drawing, not the widget)
        self._place_strip = place_strip
        header.bind("<Configure>", place_strip, add="+")
        self.root.bind("<Configure>", lambda e: place_strip() if e.widget is self.root else None, add="+")
        self.root.after_idle(place_strip)

        # Two tabs below the header: search, then review. The header strip continues behind the tabs.
        tabbar_pad = tk.Frame(self.root, bg=C_HEADER, height=4)
        tabbar_pad.pack(fill="x")
        self.tabs = ttk.Notebook(self.root, style="Main.TNotebook", takefocus=False)
        self.tabs.pack(fill="both", expand=True)
        search_tab = tk.Frame(self.tabs, bg=C_BG)
        self._search_tab = search_tab
        # The review tab belongs to the window (not the notebook) so it survives a language change
        # without reading the price sheet again.
        existing = getattr(self, "review_tab", None)
        keep_review = existing is not None and existing.winfo_exists()
        if not keep_review:
            self.review_tab = tk.Frame(self.root, bg=C_BG)
        self.tabs.add(search_tab, text=t("tab_search"))
        self.tabs.add(self.review_tab, text=t("tab_review"))
        self.review_tab.lift(self.tabs)   # stack above the (possibly newer) notebook so it is visible
        if not keep_review:
            self._build_review_tab()

        # Two columns that both reach the bottom of the window, with no scrolling:
        #   left  = the steps (1 files, 2 which products, 3 options, 4 search + progress)
        #   right = technical details, which takes whatever height is left.
        page = search_tab
        main = tk.Frame(page, bg=C_BG)
        main.pack(fill="both", expand=True, padx=14, pady=(8, 6))
        main.columnconfigure(0, weight=7, uniform="cols")
        main.columnconfigure(1, weight=3, uniform="cols")   # left: steps 1-4 · right: technical details (or blank)
        main.rowconfigure(0, weight=1)
        left = tk.Frame(main, bg=C_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.columnconfigure(0, weight=1)
        for card_row in range(4):   # spare height is shared by all four cards (contents stay centred)
            left.rowconfigure(card_row, weight=1)
        right = tk.Frame(main, bg=C_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        # 1. files
        c1 = Card(left, t("card_products"), "1", compact=True, center=True)
        c1.grid(row=0, column=0, sticky="nsew")
        files = tk.Frame(c1.body, bg=C_CARD)
        files.pack(fill="x")
        files.columnconfigure(1, weight=1)
        tk.Label(files, text=t("products_label"), bg=C_CARD, fg=C_TEXT, font=(FONT, 10)).grid(row=0, column=0, sticky="w")
        self.products_var = tk.StringVar(value=last["products"])
        ttk.Entry(files, textvariable=self.products_var).grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self._recent_button(files, "products", self.products_var).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(files, text=t("browse"), command=self.pick_products).grid(row=0, column=3, padx=(6, 0))
        tk.Label(files, text=t("current_label"), bg=C_CARD, fg=C_TEXT, font=(FONT, 10)).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.current_var = tk.StringVar(value=self.session["current"])
        ttk.Entry(files, textvariable=self.current_var).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(8, 0))
        self._recent_button(files, "current", self.current_var).grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        ttk.Button(files, text=t("browse"), command=self.pick_current).grid(row=1, column=3, padx=(6, 0), pady=(8, 0))

        # 2. which products — how many, then the two filters; they combine
        # (e.g. the first 50 "Tipo A seco" products whose name contains "leche").
        c3 = Card(left, t("card_which"), "2", compact=True, center=True)
        c3.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.scope_var = tk.StringVar(value="first" if last["mode"] == "test" else "all")
        self.limit_var = tk.StringVar(value=str(last["limit"]))
        self.type_var = tk.StringVar(value=last["type"] or t("all_types"))
        self.contains_var = tk.StringVar(value=last["contains"])
        form = tk.Frame(c3.body, bg=C_CARD)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        lbl = dict(bg=C_CARD, fg=C_TEXT, font=(FONT, 10, "bold"), anchor="w")
        tk.Label(form, text=t("qty_label"), **lbl).grid(row=0, column=0, sticky="w", padx=(0, 14))
        qty = tk.Frame(form, bg=C_CARD)
        qty.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(qty, text=t("qty_all"), value="all", variable=self.scope_var).pack(side="left")
        ttk.Radiobutton(qty, text=t("qty_first"), value="first", variable=self.scope_var).pack(side="left", padx=(22, 0))
        self.limit_spin = ttk.Spinbox(qty, from_=1, to=10000, textvariable=self.limit_var, width=6)
        self.limit_spin.pack(side="left", padx=6)
        tk.Label(qty, text=t("products_word"), bg=C_CARD, fg=C_TEXT, font=(FONT, 10)).pack(side="left")

        tk.Label(form, text=t("filters_label"), **lbl).grid(row=1, column=0, sticky="nw", padx=(0, 14), pady=(8, 0))
        self.filt_box = tk.Frame(form, bg=C_CARD)
        self.filt_box.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        self.filt_box.columnconfigure(1, weight=2)
        self.filt_box.columnconfigure(3, weight=3)
        tk.Label(self.filt_box, text=t("type_short"), bg=C_CARD, fg=C_TEXT, font=(FONT, 10)).grid(row=0, column=0, sticky="w")
        self.type_combo = ttk.Combobox(self.filt_box, textvariable=self.type_var, values=[t("all_types")], state="readonly", width=14)
        self.type_combo.grid(row=0, column=1, sticky="ew", padx=(6, 12))
        tk.Label(self.filt_box, text=t("contains_short"), bg=C_CARD, fg=C_TEXT, font=(FONT, 10)).grid(row=0, column=2, sticky="w")
        ttk.Entry(self.filt_box, textvariable=self.contains_var, width=10).grid(row=0, column=3, sticky="ew", padx=(6, 0))
        hint_row = tk.Frame(self.filt_box, bg=C_CARD)
        hint_row.grid(row=1, column=3, sticky="ew", padx=(6, 0))
        tk.Label(hint_row, text=t("name_hint"), bg=C_CARD, fg=C_MUTED, font=(FONT, 9), anchor="w").pack(side="left")
        ttk.Button(hint_row, text=t("clear_filters"), style="Link.TButton", command=self.clear_filters).pack(side="right")

        # 3. options — fills the rest of the left column
        c_opt = Card(left, t("card_options"), "3", compact=True, center=True)
        c_opt.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        self.perf_var = tk.BooleanVar(value=bool(last.get("perf", True)))
        opt_row = tk.Frame(c_opt.body, bg=C_CARD)
        opt_row.pack(fill="x")
        ttk.Button(opt_row, text=t("advanced_btn"), command=self.open_advanced).pack(side="left")
        self.perf_check = ttk.Checkbutton(opt_row, text=t("perf_check"), variable=self.perf_var)
        self.perf_check.pack(side="left", padx=(16, 0))
        self.badge = tk.Label(c_opt.body, text="", bg=C_CARD, fg=C_MUTED, font=(FONT, 9), anchor="w", justify="left")
        self.badge.pack(fill="x", pady=(4, 0))
        self.stores_lbl = tk.Label(c_opt.body, text="", bg=C_CARD, fg=C_MUTED, font=(FONT, 9), anchor="w", justify="left")
        self.stores_lbl.pack(fill="x")
        auto_wrap(self.stores_lbl)

        # 4. run — the rest of the left column
        c4 = Card(left, t("card_run"), "4", compact=True, center=True)
        c4.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
        self.count_lbl = tk.Label(c4.body, text="", bg=C_CARD, fg=C_ACCENT_DARK, font=(FONT, 11, "bold"), anchor="w", justify="left")
        self.count_lbl.pack(fill="x")
        auto_wrap(self.count_lbl)
        self.estimate_lbl = tk.Label(c4.body, text="", bg=C_CARD, fg=C_MUTED, font=(FONT, 9), anchor="w", justify="left")
        self.estimate_lbl.pack(fill="x")
        auto_wrap(self.estimate_lbl)
        buttons = tk.Frame(c4.body, bg=C_CARD)
        buttons.pack(fill="x", pady=(8, 0))
        self.stop_btn = ttk.Button(buttons, text=t("stop"), style="Stop.TButton", command=self.stop, state="disabled")
        self.stop_btn.pack(side="right", padx=(8, 0))  # always visible, greyed out unless a search is running
        self.start_btn = ttk.Button(buttons, text=t("start"), style="Start.TButton", command=self.start)
        self.start_btn.pack(side="left", fill="x", expand=True)
        # Progress follows directly under the Start button.
        progress_box = tk.Frame(c4.body, bg=C_CARD)
        progress_box.pack(fill="x")
        ttk.Separator(progress_box).pack(fill="x", pady=(10, 6))
        status_row = tk.Frame(progress_box, bg=C_CARD)
        status_row.pack(fill="x")
        self.log_visible = False
        self.log_toggle = ttk.Button(status_row, text=t("show_log"), style="Link.TButton", command=self.toggle_log)
        self.log_toggle.pack(side="right", anchor="n")
        self.status_lbl = tk.Label(status_row, text=t("ready"), bg=C_CARD, fg=C_TEXT, font=(FONT, 11, "bold"), anchor="w", justify="left")
        self.status_lbl.pack(side="left", fill="x", expand=True)
        auto_wrap(self.status_lbl)
        self.progress = ttk.Progressbar(progress_box, style="green.Horizontal.TProgressbar", mode="determinate", maximum=1, value=0)
        self.progress.pack(fill="x", pady=(6, 2))
        self.detail_lbl = tk.Label(progress_box, text="", bg=C_CARD, fg=C_MUTED, font=(FONT, 9), anchor="w", justify="left")
        self.detail_lbl.pack(fill="x")
        auto_wrap(self.detail_lbl)

        # Results: always shown under the progress bar; greyed out until a search has produced them.
        self.results_row = tk.Frame(progress_box, bg=C_CARD)
        self.results_row.pack(fill="x", pady=(8, 0))
        self.btn_open_out = ttk.Button(self.results_row, text=t("open_results"),
                                       command=lambda: self.output_path and open_path(self.output_path))
        self.btn_open_perf = ttk.Button(self.results_row, text=t("open_perf"),
                                        command=lambda: self.perf_path and open_path(self.perf_path))
        self.btn_open_dir = ttk.Button(self.results_row, text=t("open_folder"), command=self.open_output_folder)
        for b in (self.btn_open_out, self.btn_open_perf, self.btn_open_dir):
            b.pack(side="left", padx=(0, 8))
            b.configure(state="disabled" if b is not self.btn_open_dir else "normal")

        self.log_head = tk.Frame(c4.body, bg=C_CARD)   # results buttons go just above this
        self.log_head.pack(fill="x")

        # Technical details: the right column. When hidden, the steps stretch across the whole width.
        self.log_card = Card(right, t("log_title_card"), compact=True)
        self.log_card.grid(row=0, column=0, sticky="nsew")
        self._left, self._right = left, right
        self.log_frame = tk.Frame(self.log_card.body, bg=C_CARD)
        self.log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(self.log_frame, height=8, wrap="none", font=("Consolas" if FONT == "Segoe UI" else "Courier", 9),
                           bg="#10160F", fg="#D6E4D6", insertbackground="white", relief="flat", padx=8, pady=6)
        ysb, setter = slim_scrollbar(self.log_frame, self.log.yview, "Dark.Vertical.TScrollbar")
        self.log.configure(yscrollcommand=setter)
        register_scroll(self.log, text_lines=True)
        self.log.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        self.log.tag_configure("placeholder", foreground="#7E8F80")
        self._log_placeholder = not self._log_text
        if self._log_text:
            self.log.insert("end", self._log_text + "\n")
            self.log.see("end")
        else:
            self.log.insert("end", t("log_empty"), "placeholder")
        self.log.configure(state="disabled")

        if last.get("show_log"):
            self.toggle_log()
        else:   # hidden: the steps use the whole width
            right.grid_remove()
            left.grid_configure(columnspan=2, padx=0)
        self.products_var.trace_add("write", lambda *_: self._products_changed())
        # keep "N of M products will be searched" (and the time estimate) in step with every choice that changes it
        for var in (self.scope_var, self.limit_var, self.type_var, self.contains_var):
            var.trace_add("write", lambda *_: self.update_count())
        self.refresh_settings_badge()

    # -- helpers ------------------------------------------------------------
    def _mode_changed(self):
        self.limit_spin.configure(state="normal" if self.scope_var.get() == "first" else "disabled")

    def toggle_log(self):
        """Show or hide the technical details on the right (the choice is remembered)."""
        if self.log_visible:
            self._right.grid_remove()
            self._left.grid_configure(columnspan=2, padx=0)
            self.log_toggle.configure(text=t("show_log"))
        else:
            self._left.grid_configure(columnspan=1, padx=(0, 6))
            self._right.grid()
            self.log_toggle.configure(text=t("hide_log"))
            self.root.after(50, self.scroll_to_bottom)
        self.log_visible = not self.log_visible
        self.settings.last["show_log"] = self.log_visible

    def scroll_to_bottom(self):
        self.log.see("end")   # the page itself no longer scrolls

    def append_log(self, text: str):
        self.log.configure(state="normal")
        if getattr(self, "_log_placeholder", False):
            self.log.delete("1.0", "end")
            self._log_placeholder = False
        self.log.insert("end", text + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 5000:
            self.log.delete("1.0", "1000.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    # The status line and the detail line under the progress bar are stored as message keys, not as
    # finished sentences, so they can be re-written in the other language when the language changes.
    def set_status(self, key: str, color: str = C_TEXT, **kw):
        self._status_spec = (key, kw, color)
        self._render_status()

    def set_detail(self, *parts):
        """Each part is (message key, values) or a function returning text; parts are joined with ' · '."""
        self._detail_spec = parts
        self._render_status()

    def _render_status(self):
        key, kw, color = getattr(self, "_status_spec", ("ready", {}, C_TEXT))
        self.status_lbl.configure(text=t(key, **kw), fg=color)
        texts = []
        for part in getattr(self, "_detail_spec", ()):
            text = part() if callable(part) else t(part[0], **part[1])
            if text:
                texts.append(text)
        self.detail_lbl.configure(text="   ·   ".join(texts))

    def _show_results_row(self):
        """Enable the result buttons that have something to open."""
        ok = bool(self.output_path and Path(self.output_path).exists())
        self.btn_open_out.configure(state="normal" if ok else "disabled")
        self.btn_open_dir.configure(state="normal")   # the results folder can always be opened
        self.btn_open_perf.configure(state="normal" if self.perf_path and self.perf_path.exists() else "disabled")

    def _disable_results(self):
        for b in (self.btn_open_out, self.btn_open_perf):
            b.configure(state="disabled")
        self.btn_open_dir.configure(state="normal")

    def open_output_folder(self):
        """Open the folder results are saved to (Documents\\Robot de Precios unless changed in Advanced settings)."""
        folder = output_folder(self.settings.run)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        open_path(folder)

    def refresh_settings_badge(self):
        if getattr(self, "stores_lbl", None) is not None:
            chosen = self.settings.run.get("stores") or [sid for sid, _ in STORES]
            names = ", ".join(name for sid, name in STORES if sid in chosen)
            self.stores_lbl.configure(text=t("stores_line", names=names))
            self.update_count()
        n = len(self.settings.changed_matcher()) + len(self.settings.changed_run())
        if n:
            text = t("badge_custom", n=n)
            stores = self.settings.run.get("stores") or []
            if len(stores) < len(STORES):
                text += " · " + t("badge_stores", n=len(stores), total=len(STORES))
            self.badge.configure(text=text, fg=C_WARN)
        else:
            self.badge.configure(text=t("badge_default"), fg=C_MUTED)

    def pick_products(self):
        current = self.products_var.get().strip()
        start_dir = Path(current).parent if current else BASE_DIR
        path = filedialog.askopenfilename(
            title=t("pick_title"),
            initialdir=str(start_dir if start_dir.exists() else BASE_DIR),
            filetypes=[("Excel", "*.xlsx *.xlsm"), (t("all_files"), "*.*")],
        )
        if path:
            self.products_var.set(path)
            self.remember_recent("products", path)

    def _pick_excel(self, var: tk.StringVar, title_key: str):
        current = var.get().strip()
        start_dir = Path(current).parent if current else BASE_DIR
        path = filedialog.askopenfilename(
            title=t(title_key),
            initialdir=str(start_dir if start_dir.exists() else BASE_DIR),
            filetypes=[("Excel", "*.xlsx *.xlsm *.csv"), (t("all_files"), "*.*")],
        )
        if path:
            var.set(path)

    def _recent_button(self, parent, kind: str, var: tk.StringVar):
        btn = ttk.Button(parent, text=t("recent"), style="Small.TButton")
        btn.configure(command=lambda b=btn: self._show_recent(b, kind, var))
        return btn

    def _recent_results_button(self, parent):
        """'Recientes ▾' for the review tab: reopen one of the last results files reviewed."""
        btn = ttk.Button(parent, text=t("recent"), style="Small.TButton")
        btn.configure(command=lambda b=btn: self._show_recent(b, "results", on_pick=lambda f: self.open_review(path=f)))
        return btn

    def _show_recent(self, btn, kind: str, var: tk.StringVar | None = None, on_pick=None):
        files = [f for f in self.settings.last.get("recent", {}).get(kind, []) if Path(f).is_file()]
        menu = tk.Menu(self.root, tearoff=0, font=(FONT, 10))
        pick = on_pick or (lambda f: var.set(f))
        if files:
            for f in files:
                menu.add_command(label=f"{Path(f).name}    —    {Path(f).parent}", command=lambda f=f: pick(f))
        else:
            menu.add_command(label=t("recent_none"), state="disabled")
        menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())

    def remember_recent(self, kind: str, path: str) -> None:
        path = (path or "").strip()
        if not path or not Path(path).is_file():
            return
        recent = self.settings.last.setdefault("recent", {"products": [], "current": [], "results": []})
        items = [f for f in recent.get(kind, []) if not same_path(f, path)]
        recent[kind] = [str(Path(path))] + items[:5]

    def pick_current(self):
        self._pick_excel(self.current_var, "pick_current_title")

    # -- review tab -----------------------------------------------------------
    def _build_review_tab(self):
        """Fill the review tab: the loaded review, or a short explanation when nothing is loaded yet."""
        for child in self.review_tab.winfo_children():
            child.destroy()
        self._review_window = None
        bar = tk.Frame(self.review_tab, bg=C_BG)
        bar.pack(fill="x", padx=18, pady=(10, 0))
        self.review_file_lbl = tk.Label(bar, text="", bg=C_BG, fg=C_MUTED, font=(FONT, 9), anchor="w")
        self.review_file_lbl.pack(side="left", fill="x", expand=True)
        self.review_other_btn = ttk.Button(bar, text=t("review_other"), style="Small.TButton",
                                           command=lambda: self.open_review(choose=True))
        self.review_recent_btn = self._recent_results_button(bar)
        self.review_host = tk.Frame(self.review_tab, bg=C_BG)
        self.review_host.pack(fill="both", expand=True)
        self._show_review_placeholder()

    def _relabel_review_tab(self):
        """After a language change: translate the review tab in place, keeping the loaded review and its state."""
        self.review_other_btn.configure(text=t("review_other"))
        self.review_recent_btn.configure(text=t("recent"))
        if self._review_window is not None:
            path = (getattr(self, "_review_args", None) or ("",))[0]
            self.review_file_lbl.configure(text=t("review_file", name=Path(path).name) if path else "")
            self._review_window.set_language(LANG)
        else:
            loading = getattr(self, "_review_loading", False)
            self._show_review_placeholder("review_loading" if loading else getattr(self, "_placeholder_key", "review_empty"))

    def _show_review_placeholder(self, text_key="review_empty"):
        for child in self.review_host.winfo_children():
            child.destroy()
        self._placeholder_key = text_key
        self._review_window = None
        self._review_args = None
        self.review_file_lbl.configure(text="")
        self.review_other_btn.pack_forget()
        self.review_recent_btn.pack_forget()
        box = Card(self.review_host, t("review_empty_title") if text_key == "review_empty" else t("tab_review"))
        box.pack(fill="x", padx=18, pady=(8, 0))
        msg = tk.Label(box.body, text=t(text_key), bg=C_CARD, fg=C_TEXT, font=(FONT, 10), anchor="w", justify="left")
        msg.pack(fill="x")
        auto_wrap(msg)
        if text_key == "review_empty":
            open_row = tk.Frame(box.body, bg=C_CARD)
            open_row.pack(anchor="w", pady=(12, 0))
            ttk.Button(open_row, text=t("review_open"), command=lambda: self.open_review(choose=True)).pack(side="left")
            self._recent_results_button(open_row).pack(side="left", padx=(8, 0))

    def open_review(self, choose=False, path=None):
        """Open results in the review tab: this search's results, a file chosen in a dialog (choose=True), or a
        given file (path=…, e.g. from Recientes)."""
        if getattr(self, "_review_loading", False):
            self.set_status("loading_review")
            return
        if self.proc:
            messagebox.showinfo(t("app_title"), L(("Espere a que termine la búsqueda.", "Wait for the search to finish.")))
            return
        if path:
            choose = True   # a file picked from Recientes is treated like one chosen in the dialog
            if not Path(path).is_file():
                messagebox.showerror(t("app_title"), t("file_not_found_short") + f":\n{path}", parent=self.root)
                return
        else:
            path = None if choose else self.output_path   # "choose" = always ask with the file dialog
        if not path:
            path = filedialog.askopenfilename(parent=self.root, title=L(("Elegir resultados para revisar", "Choose results to review")),
                                              filetypes=[("Results", "*.xlsx *.csv")])
            if not path:
                return
        context = getattr(self, "_review_context", {}) if not choose else {}
        # A results file opened from the review tab is reviewed and exported on its own: it carries each
        # product's Salesforce Id and current price (or its saved review keeps a copy). Only results from an
        # older version need the current-prices file, and then it is asked for.
        template = None if choose else (context.get("template") or self.current_var.get().strip() or None)
        if template and not Path(template).is_file():
            template = None
        if template is None and not results_are_self_contained(path):
            template = filedialog.askopenfilename(parent=self.root, title=t("pick_current_title"), filetypes=[("Current prices", "*.xlsx *.xlsm *.csv")])
            if not template:
                return
        self._load_review(str(path), template, context.get("settings", dict(self.settings.matcher)),
                          context.get("products", self.products_var.get().strip()))

    def _load_review(self, path, template, settings, products, select=True):
        """Open a results file in the review tab (replacing whatever was there).
        The workbook is read in the background, so the window stays usable while a big file loads."""
        if select:
            self.tabs.select(self.review_tab)
        self._show_review_placeholder("review_loading")
        self._review_loading = True
        previous_status = getattr(self, "_status_spec", ("ready", {}, C_TEXT))  # e.g. "✓ Done: 500 products"
        self.set_status("loading_review")
        lang = LANG

        def finish(session, error):
            self._review_loading = False
            if error:
                self._show_review_placeholder()
                self.set_status("failed", C_ERROR)
                messagebox.showerror(t("app_title"), error, parent=self.root)
                return
            from price_review_ui import ReviewPanel
            session.lang = LANG
            session.rescore()
            panel = ReviewPanel(self.review_host, path, template, session=session)
            for child in self.review_host.winfo_children():
                if child is not panel:
                    child.destroy()
            panel.pack(fill="both", expand=True)
            self._review_window = panel
            self._review_args = (path, template, settings, products)
            self.remember_recent("results", path)   # for the Recientes buttons in the review tab
            self.settings.save()
            self.review_file_lbl.configure(text=t("review_file", name=Path(path).name))
            self.review_recent_btn.pack(side="right")
            self.review_other_btn.pack(side="right", padx=(0, 6))
            key, kw, color = previous_status
            self.set_status(key, color, **kw)   # put back what the status line said before loading

        def load():
            try:
                from price_review import ReviewSession
                session = ReviewSession(path, template, settings, products, lang)
                self.call_ui(lambda: finish(session, None))
            except Exception as exc:
                error = str(exc)
                self.call_ui(lambda: finish(None, error))

        threading.Thread(target=load, daemon=True).start()

    def open_advanced(self):
        if self.proc:
            messagebox.showinfo(t("app_title"), t("busy_settings"))
            return
        existing = getattr(self, "advanced", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass
        self.advanced = AdvancedWindow(self)

    # -- product list: type dropdown and live product count --------------------
    def _products_changed(self):
        if self._opts_after:
            self.root.after_cancel(self._opts_after)
        self._opts_after = self.root.after(300, self.load_options)

    def load_options(self):
        self._opts_after = None
        text = self.products_var.get().strip()
        if not text:
            self._rows, self._opts_state = [], "no_file"
            self._apply_options()
            return
        path = Path(text)
        if not path.is_file():
            self._rows, self._opts_state = [], "missing_file"
            self._apply_options()
            return
        self._opts_state = "loading"
        self._loading_slow = False
        if self._loading_timer is not None:
            self.root.after_cancel(self._loading_timer)
        self._loading_timer = self.root.after(350, self._loading_is_slow)
        self._apply_options()

        def work():
            try:
                raw = read_product_rows(path)
                rows = [(code, norm(name), typ, norm(typ)) for code, name, typ in raw]
                self.call_ui(lambda: self._options_loaded(rows, None, text))
            except Exception as exc:
                err = str(exc)
                self.call_ui(lambda: self._options_loaded([], err, text))

        threading.Thread(target=work, daemon=True).start()

    def _loading_is_slow(self):
        self._loading_timer = None
        if self._opts_state == "loading":
            self._loading_slow = True
            self.update_count()

    def _options_loaded(self, rows, error, path_text):
        if not same_path(path_text, self.products_var.get()):
            return  # the user picked another file meanwhile
        self._rows = rows
        self._opts_state, self._opts_error = ("error", error) if error else ("ok", "")
        if error:
            self.append_log(f"[UI] Could not read the products file: {error}")
        self._apply_options()

    def _types(self) -> list[str]:
        return sorted({r[2] for r in self._rows if r[2]}, key=norm)

    def _apply_options(self):
        """Refresh dropdowns/notes from the loaded products (also used after a language change)."""
        state = self._opts_state
        types = self._types()
        current = self.selected_type()
        self.type_combo.configure(values=[t("all_types")] + types)
        if state != "loading":  # while loading, keep the saved selection
            self.type_var.set(current if current in types else t("all_types"))
        self.update_count()

    def clear_filters(self):
        self.type_var.set(t("all_types"))
        self.contains_var.set("")
        self.update_count()

    # -- live product count ---------------------------------------------------
    def _limit_value(self) -> int | None:
        """The "only the first N" number, or None when it isn't a whole number above 0 (Start refuses it too)."""
        try:
            value = int(self.limit_var.get().strip())
        except (ValueError, tk.TclError):
            return None
        return value if value >= 1 else None

    def matching_count(self) -> int | None:
        """How many products the robot will search with the current choices (None if unknown)."""
        if self._opts_state != "ok":
            return None
        if self.scope_var.get() == "first" and self._limit_value() is None:
            return None
        ptype = norm(self.selected_type())
        contains = norm(self.contains_var.get())
        n = 0
        for code, name_n, _type, type_n in self._rows:
            if ptype and type_n != ptype:
                continue
            if contains and contains not in name_n:
                continue
            n += 1
        if self.scope_var.get() == "first":
            n = min(n, self._limit_value())
        return n

    def update_count(self):
        if not hasattr(self, "count_lbl"):
            return
        self._mode_changed()
        n = self.matching_count()
        if getattr(self, "estimate_lbl", None) is not None:
            run = self.settings.run
            secs = estimate_run_seconds(n, run.get("workers", 1), len(run.get("stores") or STORES)) if n else 0
            # small runs: the per-product math says a few seconds, but starting up takes longer than that
            self.estimate_lbl.configure(text="" if not n else t("estimate_short") if secs < 60
                                        else t("estimate_line", t=fmt_duration(secs)))
        if n is None:
            state = self._opts_state
            if state == "ok":   # the products are known, so the "first N" number is what's missing
                text, color = "⚠  " + t("count_bad_limit"), C_WARN
            elif state == "error":
                err = self._opts_error or ""
                key = "count_python" if ("ModuleNotFoundError" in err or "No module named" in err) else "count_failed"
                text, color = "⚠  " + t(key), C_WARN
            elif state == "missing_file":
                text, color = "⚠  " + t("count_missing"), C_ERROR
            elif state == "loading":
                if not self._loading_slow:
                    return   # a quick load goes straight to the count, without flashing "Loading…" first
                text, color = t("count_loading"), C_MUTED
            elif state == "no_file":
                text, color = t("count_waiting"), C_MUTED
            else:
                text, color = "", C_MUTED
            self.count_lbl.configure(text=text, fg=color)
        elif n == 0:
            self.count_lbl.configure(text="⚠  " + t("will_search_none"), fg=C_WARN)
        else:
            self.count_lbl.configure(text="→  " + t("will_search", n=f"{n:,}", total=f"{len(self._rows):,}"),
                                     fg=C_ACCENT_DARK)

    # -- run ----------------------------------------------------------------
    def _child_env(self, overrides: dict, product_filter: dict | None = None, current_prices: str | None = None,
                   perf_file: str | None = None) -> dict:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        env.pop("BAP_ROBOT_SETTINGS", None)
        env.pop("BAP_ROBOT_FILTER", None)
        env.pop("BAP_ROBOT_CURRENT_PRICES", None)
        env.pop("BAP_ROBOT_PERFORMANCE_FILE", None)
        env["BAP_ROBOT_PERFORMANCE"] = "1" if self.perf_var.get() else "0"
        if perf_file:
            env["BAP_ROBOT_PERFORMANCE_FILE"] = perf_file
        if current_prices is not None:
            env["BAP_ROBOT_CURRENT_PRICES"] = current_prices  # "" = comparison off
        if overrides:
            env["BAP_ROBOT_SETTINGS"] = json.dumps(overrides)
        if product_filter:
            env["BAP_ROBOT_FILTER"] = json.dumps(product_filter, ensure_ascii=False)
        return env

    def build_command(self) -> list[str] | None:
        products_text = self.products_var.get().strip()
        products = Path(products_text)
        if not products_text or not products.is_file():
            messagebox.showerror(t("app_title"), t("err_products"))
            return None
        chosen = self.settings.run.get("stores") or []
        stores = [sid for sid, _ in STORES if sid in chosen]
        if not stores:
            messagebox.showerror(t("app_title"), t("err_stores"))
            return None

        if not Path(self.current_var.get().strip() or "\0").is_file():
            messagebox.showerror(t("app_title"), t("err_current"))
            return None
        problem = input_files_problem(products, self.current_var.get().strip())
        if problem:
            messagebox.showerror(t("app_title"), problem)
            return None
        cmd = worker_command() + ["--products", str(products), "--stores", ",".join(stores)]
        if self.scope_var.get() == "first":
            try:
                limit = int(self.limit_var.get())
                if limit < 1:
                    raise ValueError
            except Exception:
                messagebox.showerror(t("app_title"), t("err_limit"))
                return None
            cmd += ["--limit", str(limit)]
        contains = self.contains_var.get().strip()
        if contains:
            cmd += ["--contains", contains]
        ptype = self.selected_type()
        if ptype:
            cmd += ["--type", ptype]

        r = self.settings.run
        if not output_folder(r).is_dir():
            messagebox.showerror(t("app_title"), t("err_folder_run", path=output_folder(r)))
            return None
        results_path, perf_path = output_paths(r)
        self._planned_perf = perf_path
        cmd += ["--workers", str(r["workers"]), "--average-mode", r["average_mode"], "--output", str(results_path)]
        if r["cache_mode"] == "clear":
            cmd.append("--clear-cache")
        elif r["cache_mode"] == "none":
            cmd.append("--no-cache")

        self._capture_inputs()  # remember choices for next time
        self.settings.save()
        return cmd

    def start(self):
        if self.proc:
            return
        if getattr(self, "_review_loading", False):
            self.set_status("loading_review")
            return
        cmd = self.build_command()
        if not cmd:
            return
        n = self.matching_count()
        if n is not None and n > 300:
            est = estimate_run_seconds(n, self.settings.run["workers"], len(self.settings.run.get("stores") or STORES))
            if not messagebox.askyesno(t("app_title"), t("confirm_many", n=f"{n:,}", t=fmt_duration(est))):
                return

        # The new search rewrites the results file, so close the review now (its decisions are already saved).
        if self._review_window is not None:
            self._show_review_placeholder()
        overrides = dict(self.settings.matcher)
        self._review_context = {"settings": dict(overrides), "products": self.products_var.get().strip(),
                                "template": self.current_var.get().strip() or str(BASE_DIR / "current_prices.xlsx")}
        overrides["CACHE_TTL_HOURS"] = self.settings.run["CACHE_TTL_HOURS"]

        self.total = self.done = 0
        self.output_path = self.perf_path = None
        self.progress_was_done = False
        self.log_tail = []
        self.stopped_by_user = False
        self._disable_results()
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(12)
        self.set_status("reading")
        self.set_detail()
        self.append_log("\n$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd[1:]))

        try:
            self.proc = subprocess.Popen(
                cmd, cwd=str(BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=no_window_flags(), env=self._child_env(overrides, perf_file=str(self._planned_perf),
                                                                        current_prices=self.current_var.get().strip()),
            )
        except Exception as exc:
            self.proc = None
            self.progress.stop()
            self.set_status("cant_start", C_ERROR)
            messagebox.showerror(t("app_title"), f"{t('cant_start')}\n{exc}")
            return

        self.started_at = time.time()
        self._rate_start = None   # (time, products done) at the first finished product
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.root.title(t("app_title"))
        self.remember_recent("products", self.products_var.get())
        self.remember_recent("current", self.current_var.get())
        self.settings.save()
        self.root.after(150, self.scroll_to_bottom)  # bring the progress into view
        proc = self.proc

        def reader():
            assert proc.stdout is not None
            for line in proc.stdout:
                self.lines.put(line.rstrip("\r\n"))
            proc.wait()
            self.lines.put(None)  # sentinel: finished

        threading.Thread(target=reader, daemon=True).start()
        self._tick()

    def stop(self):
        if not self.proc:
            return
        if not messagebox.askyesno(t("app_title"), t("confirm_stop")):
            return
        self.stopped_by_user = True
        try:
            self.proc.terminate()
        except Exception:
            pass
        self.set_status("stopping", C_WARN)

    def on_close(self):
        if self.proc:
            if not messagebox.askyesno(t("app_title"), t("confirm_close")):
                return
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.root.destroy()

    # -- output parsing -----------------------------------------------------
    RE_TOTAL = re.compile(r"^Products:\s*(\d+)")
    RE_STEP = re.compile(r"^\[(\d+)/(\d+)\]\s*(.*)")
    RE_SAVED = re.compile(r"^Saved:\s*(.+)$")
    RE_PERF = re.compile(r"^Performance analysis saved:\s*(.+)$")

    def call_ui(self, fn):
        """Safe from any thread: run fn on the main (window) thread at the next poll."""
        self.ui_calls.put(fn)

    def _poll(self):
        try:
            while True:
                try:
                    fn = self.ui_calls.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn()
                except Exception as exc:
                    self.append_log(f"[UI] {exc!r}")
            while True:
                try:
                    line = self.lines.get_nowait()
                except queue.Empty:
                    break
                if line is None:
                    self._finished()
                    break
                self._handle_line(line)
        except Exception as exc:
            try:
                self.append_log(f"[UI] {exc!r}")
            except Exception:
                pass
        finally:
            self.root.after(100, self._poll)

    def _handle_line(self, line: str):
        self.append_log(line)
        self.log_tail.append(line)
        self.log_tail = self.log_tail[-40:]
        if line.startswith("[EXPORT]"):
            self.set_status("exporting")
            return

        if line.startswith("Cleared cache"):
            self.set_status("cache_cleared")
        m = self.RE_TOTAL.match(line)
        if m:
            self.total = int(m.group(1))
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=max(1, self.total), value=0)
            if self.total == 0:
                self.set_status("no_products_match", C_WARN)
            else:
                self.set_status("searching_n", n=self.total)
            return
        m = self.RE_STEP.match(line)
        if m:
            self.done, self.total = int(m.group(1)), int(m.group(2))
            if getattr(self, "_rate_start", None) is None:
                self._rate_start = (time.time(), self.done)
            self.progress.configure(value=self.done, maximum=max(1, self.total))
            self.set_status("searching_step", i=self.done, n=self.total)
            self._last_name = m.group(3)
            if self.done >= self.total:
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
                self.set_status("saving")
            return
        m = self.RE_SAVED.match(line)
        if m:
            self.output_path = Path(m.group(1).strip())
            self.set_status("making_perf" if self.perf_var.get() else "finishing")
            return
        m = self.RE_PERF.match(line)
        if m:
            self.perf_path = Path(m.group(1).strip())

    def remaining_seconds(self, elapsed):
        """Time left: from the actual pace once products are finishing (ignoring the start-up time spent
        reading files), before that from the pre-run estimate."""
        if not self.total or self.done >= self.total:
            return None
        start = getattr(self, "_rate_start", None)
        if start and self.done - start[1] >= 3:
            pace = (time.time() - start[0]) / (self.done - start[1])
            return pace * (self.total - self.done)
        run = self.settings.run
        estimate = estimate_run_seconds(self.total, run.get("workers", 1), len(run.get("stores") or STORES))
        return max(estimate - elapsed, 0) if self.done == 0 else max(estimate * (self.total - self.done) / self.total, 0)

    def _tick(self):
        """Update elapsed / remaining time once per second while running."""
        if not self.proc:
            return
        elapsed = time.time() - self.started_at
        parts = [("time", {"t": fmt_duration(elapsed)})]
        left = self.remaining_seconds(elapsed)
        if left is not None:
            parts.append(("remaining", {"t": fmt_duration(left)}))
        if self._last_name and self.done < self.total:
            parts.append(("last_item", {"name": self._last_name}))
        self.set_detail(*parts)
        self.root.after(1000, self._tick)

    def _finished(self):
        proc, self.proc = self.proc, None
        code = proc.returncode if proc else -1
        elapsed = time.time() - self.started_at
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._last_name = None
        tail = "\n".join(self.log_tail)
        ok = code == 0 and bool(self.output_path)
        if not self.stopped_by_user:
            self.notify_finished(ok or code == 0)

        if self.stopped_by_user:
            self.progress.configure(value=0)
            self.set_status("stopped", C_WARN)
            self.set_detail(("stopped_detail", {"t": fmt_duration(elapsed)}))
            return

        if code == 0 and self.output_path:
            self.progress.configure(value=self.progress["maximum"])
            self.progress_was_done = True
            self.set_status("done", C_OK, n=self.total, t=fmt_duration(elapsed))
            self.set_detail(("results_file", {"name": self.output_path.name}), ("summarizing", {}))
            self._show_results_row()
            threading.Thread(target=self._summarize, args=(self.output_path,), daemon=True).start()
            self.root.after_idle(self.open_review)
            when = self.settings.run.get("open_when_done", "none")
            if when in ("results", "both"):
                open_path(self.output_path)
            if when in ("perf", "both") and self.perf_path and self.perf_path.exists():
                open_path(self.perf_path)
            return

        if code == 0 and self.total == 0:
            self.progress.configure(value=0)
            self.set_status("no_products_match", C_WARN)
            self.set_detail(("check_filters", {}))
            return

        # --- error handling with friendly messages ---
        self.progress.configure(value=0)
        self.set_status("failed", C_ERROR)
        if not self.log_visible:
            self.toggle_log()
        if "ModuleNotFoundError" in tail or "No module named" in tail:
            self.set_detail(("missing_python", {}))
            if messagebox.askyesno(t("app_title"), t("ask_install")):
                self.install_requirements()
        elif "PermissionError" in tail:
            self.set_detail(("cant_save", {}))
            messagebox.showerror(t("app_title"), t("cant_save_long"))
        elif "FileNotFoundError" in tail:
            self.set_detail(("file_missing_detail", {}))
        else:
            last = next((ln for ln in reversed(self.log_tail) if ln.strip()), "")
            self.set_detail(("detail", {"text": last[:180]}))

    def notify_finished(self, ok: bool):
        """Long searches: flash the taskbar and show the result in the window title until the user looks."""
        try:
            focused = self.root.focus_displayof() is not None
        except Exception:
            focused = False
        if focused:
            try:
                self.root.bell()
            except Exception:
                pass
            return
        self.root.title(t("title_done" if ok else "title_failed", title=t("app_title")))
        flash_window(self.root)

        def restore(_e=None):
            self.root.title(t("app_title"))
            self.root.unbind("<FocusIn>")
        self.root.bind("<FocusIn>", restore)

    def _summarize(self, path: Path):
        """Count estimates and flags from the results summary for a plain-language result."""
        counts = None
        change = None
        try:
            if path.suffix.lower() == ".xlsx":
                from results_format import internal_header, read_records
                headers, records = read_records(path)
                n = len(records)
                est = sum(1 for r in records if r.get("Estimated New Product Price") not in (None, ""))
                ok = sum(1 for r in records if str(r.get("Quality Flag") or "").strip() == "OK")
                counts = dict(n=n, est=est, ok=ok, review=est - ok, none=n - est)
                big_header = next((h for h in headers if internal_header(h) == "Large Price Change"), None)
                if big_header is not None:
                    limit = re.search(r"(\d+(?:[.,]\d+)?)\s*%", str(big_header))
                    big = sum(1 for r in records if r.get("Large Price Change") == "YES")
                    change = (big, limit[1] if limit else "")
        except Exception:
            pass

        def summary_text():   # written in whatever language is active when it is shown
            text = t("summary", **counts) if counts else t("results_file", name=path.name)
            if counts and change:
                text += t("summary_change", n=change[0], p=change[1])
            return text
        self.call_ui(lambda: self.set_detail(summary_text))

    def install_requirements(self):
        if is_frozen():
            messagebox.showerror(t("app_title"), L(("La aplicación incluye sus componentes. Vuelva a copiar una versión completa del ejecutable.",
                                                    "The app includes its dependencies. Replace it with a complete executable build.")))
            return
        cmd = [python_for_subprocess(), "-m", "pip", "install", "-r", str(REQUIREMENTS)]
        self.set_status("installing")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.start_btn.configure(state="disabled")
        self.append_log("\n$ pip install -r requirements.txt")

        def work():
            try:
                res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", creationflags=no_window_flags())
                out, ok = res.stdout + res.stderr, res.returncode == 0
            except Exception as exc:
                out, ok = str(exc), False

            def done():
                self.append_log(out)
                self.progress.stop()
                self.progress.configure(mode="determinate", value=0)
                self.start_btn.configure(state="normal")
                if ok:
                    self.set_status("installed", C_OK)
                    self.set_detail()
                    self.load_options()
                else:
                    self.set_status("install_failed", C_ERROR)
            self.call_ui(done)

        threading.Thread(target=work, daemon=True).start()


def main():
    load_code_defaults()
    if sys.platform.startswith("win"):
        try:  # crisp text on high-DPI screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        try:  # own taskbar button + icon instead of being grouped with Python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BancoDeAlimentosPanama.RobotDePrecios")
        except Exception:
            pass
    root = tk.Tk()

    def report_error(exc_type, exc, tb):
        """Errors inside the window are otherwise invisible (no console): log them and tell the user."""
        import traceback
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
        except Exception:
            pass
        try:
            messagebox.showerror(t("app_title"), f"{t('unexpected_error')}\n\n{exc_type.__name__}: {exc}\n\n{ERROR_LOG}")
        except Exception:
            pass

    root.report_callback_exception = report_error
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
