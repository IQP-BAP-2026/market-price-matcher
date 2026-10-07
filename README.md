# Banco de Alimentos Panamá — Price Robot

Project layout: keep source, build instructions and input spreadsheets in Git. `input/` (the products workbook and the Salesforce current-prices export) remains trackable. Runtime caches live in `caché/` (candidate indexes in a `caché/` folder beside their results), and new exports default to `resultados/` when running from source. Caches, outputs, review decisions/archives, local preferences, logs, bytecode, `build/` and `dist/` are ignored. Existing root-level exports are also ignored; ignoring/untracking generated files does not delete local copies.

Estimates current market prices for Banco de Alimentos Panamá (BAP) products by searching supermarket websites, matching each BAP product to comparable store products, cleaning the prices, and applying the BAP pricing rule.

Supported supermarkets:

- **Super 99** — Adobe Commerce / GraphQL search
- **Super Xtra** — VTEX search
- **Supermercados Rey (El Rey)** — Next.js / Instaleap search
- **Riba Smith** — Next.js / React Server Components search

It can be used two ways:

- **Desktop app** (recommended) — a Spanish/English window, no command line needed. Install it with `RobotDePrecios_Instalador.exe`, or use `launch.bat` when running from source.
- **Command line** — `py price_robot.py …`, for scripting and debugging.

Both use exactly the same matching and pricing code.

---

## 1. Project files

```text
market-price-matcher-main/
├── launch.bat               # opens the desktop app from source (double-click)
├── price_robot_ui.py        # the desktop app: Search prices tab, Advanced settings
├── price_review_ui.py       # the Review prices tab (approve prices, export CSV)
├── candidate_review_ui.py   # "Choose candidates…" window
├── price_review.py          # review logic: confidence scores, decisions, CSV export
├── review_config.py         # review scoring parameters
├── candidate_store.py       # fast index of saved store listings for the review
├── current_prices.py        # reads the Salesforce current-prices export
├── excel_export.py          # fast Excel writing for large results
├── robot_launcher.py        # runs price_robot.py with the app's settings
├── price_robot.py           # the price robot (search, clean, price, Excel output)
├── matcher_core.py          # shared matching / pricing rules
├── app_runtime.py           # where settings, caches and results are saved
├── desktop_entry.py         # entry point of the .exe (app, worker, self-test)
├── store_parsers/           # one adapter per supermarket website
│   ├── __init__.py
│   ├── base.py
│   ├── super99.py
│   ├── superxtra.py
│   ├── rey.py
│   └── ribasmith.py
├── assets/                  # header photos (header_photo_1.png … _4.png, real PNG files) and app_icon.ico
├── PriceRobot.spec          # PyInstaller build recipe
├── build_windows.ps1        # builds and checks dist/RobotDePrecios.exe, then the installer
├── installer.iss            # Inno Setup script for RobotDePrecios_Instalador.exe
├── windows_version.txt      # version information shown in the .exe properties
├── requirements.txt
├── requirements-build.txt
└── input/
    ├── products.xlsx                # BAP product list
    └── pricebookcurrent.csv.xlsx    # Salesforce current-prices export
```

To change a header photo, replace the matching file in `assets/` with a **real PNG** (Tk cannot read JPEG files, even renamed to `.png`) and rebuild the executable. A wide photo works best; it is cropped to a slanted panel.

Created automatically while working (safe to delete; they are rebuilt):

| File | What it is |
|---|---|
| `caché/store_search_cache.sqlite3` | Saved supermarket responses (reused for 12 hours by default) |
| `caché/ui_products_cache.json` | Saved product list so the app's filters load instantly |
| `__pycache__/` | Python's compiled files |
| `ui_errors.log` | Only appears if the app hits an unexpected error |
| `worker.log` | Only appears if the packaged search process cannot write its output to the app |

`ui_settings.json` stores the app's language, recent files and Advanced settings. Deleting it resets them to defaults.

---

## 2. Installation

### Installing on a BAP computer

Run **`RobotDePrecios_Instalador.exe`** (no administrator rights needed). It:

- installs `RobotDePrecios.exe` in `%LOCALAPPDATA%\Robot de Precios` — the app's settings (`ui_settings.json`), caches (`caché\`) and logs are saved there too;
- creates **Documentos\Robot de Precios**, where results are saved (the real Documents folder, also when it lives in OneDrive);
- adds a **Robot de Precios** shortcut to the desktop and the Start menu, and opens the app.

The executable includes Python, Tk, the scraper, review screens and Excel libraries; nothing else needs to be installed. Internet access is needed for supermarket searches. **Open folder** in the app opens the results folder (Documentos\Robot de Precios, or the folder chosen in Advanced settings → Results). Running the installer again over an existing installation updates the app and keeps its settings.

To uninstall, use **Settings → Apps → Robot de Precios → Uninstall** (or *Uninstall Robot de Precios* in the Start menu). It closes the app, removes the AppData folder (app, settings, caches, logs) and both shortcuts, then asks whether to also delete the results in Documentos\Robot de Precios.

### Building the executable and the installer

On Windows, once:

```powershell
python -m pip install -r requirements-build.txt
winget install JRSoftware.InnoSetup
```

Then, from the project folder:

```powershell
.\build_windows.ps1 -Python python
```

The script builds `dist\RobotDePrecios.exe` (`PriceRobot.spec` controls the bundle, including the header photos and `assets\app_icon.ico`), checks that it starts and that its background search process works, and then compiles `installer.iss` into **`dist\RobotDePrecios_Instalador.exe`** — the only file to give to BAP. If Inno Setup isn't installed, the script installs it with winget (or stops and says where to get it). After source changes, rebuild. Optional diagnostic check: `RobotDePrecios.exe --self-test C:\path\report.json`.

To change the version shown in Settings → Apps, edit `AppVersion` in `installer.iss` (and `windows_version.txt` for the executable's properties).

### Running from source

Needs Python 3 (3.13 and 3.14 are known to work) plus two packages:

```bash
py -m pip install -r requirements.txt
```

(`requests` and `openpyxl`. If `py` is not available, use `python -m pip install -r requirements.txt`.)

If the packages are missing, the desktop app offers to install them for you.

---

## 3. Using the desktop app

Open **Robot de Precios** from the desktop shortcut (or, from source, double-click **`launch.bat`** / run `py price_robot_ui.py`). The window has two tabs: **1 · Search prices** and **2 · Review prices**. The **ES / EN** switch in the top-right corner changes the language at any time; the loaded review is kept.

### Search prices tab

**1 · Files**

- **Products** — the BAP product workbook. **Browse…** chooses it; **Recent ▾** lists the last few files used. Nothing is pre-selected when the app opens.
- **Current prices** — the current-prices report downloaded from Salesforce (Excel or CSV) with the columns `ProductCode`, `Id` and `UnitPrice`. It is required: the robot will not start unless both files have all their required columns, and it says which column is missing.

**2 · Which products?**

- **How many** — *All products*, or *Only the first N* for a quick test.
- **Filters** — *Type* (the `Sub-familia de Productos` column) and *Name contains* (ignores capitals and accents). The filters combine with the amount: for example, the first 50 `Tipo A seco` products whose name contains `leche`. **Clear filters** resets them.

**3 · Options**

- **Advanced settings…** — see below. The line under it shows whether the default settings are in use and which supermarkets will be searched (choose the supermarkets in Advanced settings → Store search).
- **Create performance analysis** — a second Excel file with a dashboard and review columns. On big searches it takes extra time; the results file is created either way.

**4 · Search**

The line at the top shows how many products will be searched and the estimated time; it updates as soon as any choice above changes. Click **▶ Start**; **■ Stop** is only active while a search runs (stopping discards that search). The progress bar shows products done, elapsed time and time left. When finished, the line below it summarizes the results (how many got a price, how many need review, big price changes) and the results file opens in **2 · Review prices**. **Open results**, **Open performance analysis** and **Open folder** are always visible and become active when there is something to open. **Show technical details** shows the robot's full log on the right.

If you're in another window when a long search finishes, the taskbar button flashes and the window title shows the result.

### Review prices tab

The results of the last search open here automatically. **Open results file…** (or **Open another file…** / **Recent ▾** once a review is loaded) opens any earlier results workbook without searching again. The results file includes each product's Salesforce `Id` and current price, so the review and its CSV export do not need the current-prices file. The performance-analysis workbook is not required.

1. Filter by confidence **1–5**, by decision (*All*, *Pending*, *Accepted / manual*, *Rejected*, *Rejected / no price — enter prices*) or by text search. A decision that no longer matches the filter stays in the list until you click **Refresh list**, so products don't disappear while you work. Every product starts **Pending**, including high-confidence products. The table shows confidence, code, product, current price, new (proposed) price, change % and decision. Below it, the selected product's current price, new price and change % are shown in fixed boxes. The confidence grade describes the proposed estimate; it is not a probability that the price is correct.
2. Press **A** (or **Accept [A]**) to accept or **R** (**Reject [R]**) to reject; the next product is selected automatically. Accepting a product with no proposed price keeps its current BAP price. Ctrl/Shift-click or click-and-drag selects several products; dragging past the table edge scrolls.
3. To set your own price, **start typing a number** and press **Enter**, or simply select another product — the typed price is saved either way. **Escape** cancels the draft. **Calculator [C]** opens a small calculator that averages store prices you type in. **Undo [Ctrl+Z]** and **Redo [Ctrl+Y]** reverse or repeat the latest decisions.
4. **Export CSV…** creates a UTF-8 CSV containing exactly **`Id,UnitPrice`**, with prices written to two decimal places, ready for Salesforce Data Loader (*Update* on *PricebookEntry*). Only accepted and manually entered prices are included; pending and rejected products are left out. If products are still pending, the app shows how many and asks before exporting. Every exported product must have a Salesforce `Id`; the export lists products without one and stops instead of guessing.

**Categories ▾** expands filters for product type (`Tipo A seco`, etc.) and a second classification: match group, family, product line, RepTrim category or GFN type. Match group is the matcher's first generated search query (for example `pasta tomate`), not an invented classification. Category choices combine with score, decision and text filters. Search also finds category names and ignores accents. Click **Sort by category ↕** to group similar products; click any table heading to sort by that column, including numeric price changes. Active category filters are counted on the collapsed button.

**Choose candidates… / Elegir candidatos…** opens the selected product's saved listings in separate supermarket tabs. Each listing shows whether it is used in the price, the robot's original accepted/rejected decision and reason, product price, normalized size and price per kg/unit. Select one or several listings and use **Include [A]** or **Exclude [R]**; the proposal preview updates across all supermarkets. **Open page [O]** opens the selected listing in the browser for verification. Listings without a usable price or package size cannot be included.

**Apply new price** saves the choices, updates the proposed price and confidence, and returns the product to **Pending**, replacing any previous price approval. Accept the revised proposal through the normal review controls. Excluding every listing clears the proposal. **Cancel** discards draft choices; **Restore robot's choices** resets the draft to the original selections; the main review's **Undo** also reverses an applied candidate change. Original workbook evidence is preserved. Summary-only CSVs do not contain candidate details.

The candidate picker supports search by product, SKU, rejection reason or search query, plus filters for included/excluded listings, reviewer changes and the matcher's original decision. Filters apply across supermarket tabs but never change the price calculation. Click any column heading to sort; click again to reverse. Prices and quantities sort numerically, with missing values last. Drag across rows to select a range (including automatic scrolling at the edges); Ctrl-drag adds to the selection. Ctrl/Shift-click also work.

With the candidate list focused: **A / Enter** includes, **R / Delete** excludes and advances to the next visible listing, **Space** toggles the selection, **Ctrl+A** selects all visible listings in the current supermarket, **Ctrl+Z / Ctrl+Y** undo and redo draft candidate changes, and **O** opens the selected product page. **Ctrl+F** focuses search; **Ctrl+Enter** applies the draft; **Esc** cancels. Typing in search does not change candidate decisions. Like the main review, filtered-out listings only leave the list when you click **Refresh list**.

Recalculation uses the same package quantity, store weighting, market price level and BAP percentage formula as the scraper, without rerunning filters over the human's selected candidates. New results record the percentage, store-weight cap and economy percentile in the Summary sheet. Older results use the review's saved/current settings, falling back to code defaults for settings that were not saved.

Decisions, candidate choices, explanations and run settings save next to the results as `*.xlsx.review.json` (or `*.csv.review.json`). Keep that file with the results to resume. If the results or current-price file changes, the previous decisions are archived and the new review starts pending. A new search's results replace the open review when the search finishes.

Large exports stream the Candidates sheet directly to Excel instead of constructing a cell object for every value. Both workbooks retain the full candidate evidence, formatting and comparison columns. Faster ZIP compression can make the files larger. Saves use a temporary file so a failed export preserves the previous workbook, and the progress area identifies the Excel-writing stage.

Review preparation runs in the background. A disposable `*.xlsx.candidates.sqlite3` index holds compressed candidate groups; the review only loads the selected product's candidates into memory. New searches prepare this index during export. Older workbooks build it on first opening, which can take longer; later openings reuse it. The index is rebuilt if the results change and can safely be deleted. Keep the separate `*.review.json` file: that one contains your human decisions.

### Confidence policy and configuration

`review_config.py` contains named global review parameters: component weights, evidence targets, query-confidence credits, grade boundaries, warning penalties, grade caps, rounding, and the current-price-change limit. Existing matching/package/outlier parameters remain in `matcher_core.py` and Advanced settings.

The composite starts with up to 100 evidence points:

| Component | Maximum points | Default rule |
|---|---:|---|
| Store coverage | 20 | Full credit at 3 stores |
| Comparable products per store | 20 | Up to 3 per store, target 9 across stores |
| Query confidence | 20 | High: 100%, medium: 65%, low: 25% of this component |
| Agreement with current price | 25 | Full credit within ±20%; declining credit outside it; limited credit when current price is missing |
| Price variation | 15 | Full credit within the configured price-CV limit; declining credit above it |

Warnings then deduct points. The grade boundaries are 25/45/65/85 points for grades 2/3/4/5. Missing or invalid estimates always receive grade 1. Severe evidence/size warnings cap the grade at 2; high risk, store-request failures, and changes exceeding the current-price limit cap it at 3. These conservative defaults are configurable and have not been statistically calibrated as prediction probabilities.

**Advanced settings → Review warnings → Price change that needs review** controls the shared absolute percentage limit, now **20%**: both +20% and −20% are within range; larger changes trigger concern. Existing settings using the former 30% default migrate once to 20%; other customized limits are retained. Saved reviews retain their threshold settings when reopened.


### Advanced settings

Grouped in the order the robot works, each with a plain explanation and a live example:

1. **Store search** — which supermarkets to search, simultaneous searches (default 100), search memory (cache) and how long it lasts, when to stop searching.
2. **Package size** — which store package sizes count as comparable.
3. **Price cleanup** — removing duplicates and prices far from the median.
4. **BAP price** — the BAP percentage, regular vs. sale price, how supermarkets are combined.
5. **Review warnings** — when a product is marked for review, including the big-price-change threshold.
6. **Results** — output folder, file names, keep each search (date/time in the name), open files when done.

Rarely needed settings are under *Expert settings*. Changes only apply to searches started from the app; `price_robot.py` and `matcher_core.py` are never modified.

---

## 4. Input files

### File formats (both input files)

The products file and the current-prices file can be **.xlsx / .xlsm**, old **.xls** workbooks, **.csv / .txt**, or an "Excel" file that is really an HTML table (as some Salesforce report exports are). The format is recognised from the file's content, not its name. Text files can be UTF-8, UTF-16 ("Unicode text") or the Windows code page, so accented letters (ñ, á, é…) read correctly, and separated by commas, semicolons or tabs; with semicolons, decimal commas (`5,02`) are understood. The header row doesn't have to be the first row (title lines above it are skipped). `table_files.py` does the reading.

### Products file (`products.xlsx`)

The robot looks for a worksheet named `MASTER-YYYY`; otherwise it uses the first sheet containing the required headers. Required columns:

```text
Nombre del producto
Código de producto
```

These improve matching when present (they resolve ambiguous names, e.g. `Leche 946ml` → whole milk rather than powdered/almond/flavored):

```text
ERP Id (QBO)            Linea de producto        Familia de productos
Sub-familia de Productos   Unidad de Peso en KG  Descripción del producto
Grupo de Productos      Categoria RepTrim
```

### Current prices (Salesforce price book download)

Only these columns are read; any other columns in the file are ignored, in any order. Header names are compared without accents, capitals or spaces, and the usual alternatives are accepted:

| Column | Also accepted | Use |
|---|---|---|
| `ProductCode` | Product Code, Código de producto | Matches the product code in the products/results file (required) |
| `UnitPrice` | Unit Price, List Price, Precio de lista | Current price for comparison (required) |
| `Id` | Price Book Entry ID, PricebookEntryId | PricebookEntry record ID, required for the review's CSV export (required) |
| `Pricebook2Id` | Price Book ID, PricebookId | Which price book the row belongs to |
| `Name` | Product Name, Nombre del producto | Optional product name |

Salesforce lists a product once per price book, so the same `ProductCode` can appear several times. **Only rows whose `Pricebook2Id` is BAP's price book, `01s41000004hcm1AAA`, are used** (the 15-character form `01s41000004hcm1` is accepted too); rows of other price books are skipped. The Id is `STANDARD_PRICEBOOK_ID` in `current_prices.py`. Within that price book each product must appear once: a duplicate `ProductCode` or `Id` produces a clear error. A file without a `Pricebook2Id` column is accepted when each product appears only once. Missing/blank prices remain unavailable for comparison; malformed prices are reported.

Categories such as `Tipo A seco`, family and product line come from the **products file**, because the price book does not contain them.

In the app, choose it under **Current prices** (the search will not start without it). On the command line, `current_prices.xlsx` is read from the folder you run in, if present.

---

## 5. How it works

```text
products.xlsx
  → conservative search terms per product
  → search the selected supermarket websites
  → each store parser converts results to one common format
  → matcher_core.py checks product identity and subtype
  → normalize package quantities to price per kg (or per unit)
  → pick one package-size group across ALL stores
  → remove duplicates (per store) and price outliers (across stores)
  → cleaned average per store
  → combine stores into the market estimate
  → apply the BAP pricing rule
  → Excel results + performance analysis
```

### BAP pricing rule

```text
Estimated BAP Price = cleaned market price per kg × target quantity in kg × 20%
```

The 20% is `BAP_MARKET_PRICE_PERCENT = 0.20` in `matcher_core.py` (changeable per search in the app's Advanced settings).

### Market value level

Stores sell cheap and expensive brands of the same product, so "the market price" depends on which part of that range is used. **Advanced settings → BAP price → Market value level** (`MARKET_PRICE_LEVEL`):

| Level | Market price per kg | Example: one store at $2, $3, $4, $7 /kg |
|---|---|---|
| **Economy** (default) | the lower quartile (cheapest 25%, `ECONOMY_PERCENTILE`) of each store's prices, then the stores combined | $2.75 |
| Median | the middle price | $3.50 |
| Average | the average price (the robot's behaviour before this setting) | $4.00 |

Economy was chosen as the default after a 500-product test: it tracks BAP's own price level best (estimates ≈ 8% above current prices, vs 18% with Average) and brings the most products within ±30% of the current price. Meat and bakery products still come out 30–50% above current prices with every level: the stores sell mostly deli-counter and premium items there.

The results always show the **Average**, **Median** and **Economy** price per kg, plus the *Market Price Level* the estimate used, so the other levels can be compared without re-running.

### Product identity

The matcher ignores packaging/admin words and focuses on the words that identify the product:

```text
Arroz Integral 3kg              → arroz integral
Agua Saborizada de 12x355ml     → agua saborizada
PV Sazonadores variados 2kg     → sazonador
```

Words that change what the product is — `integral`, `saborizada`, `condensada`, `evaporada`, `polvo`, `concentrado`, `picante` … — are never silently ignored.

Wording differences are handled before comparing:

- **Accents, plurals and gender** — `instantánea` = `instantáneo`, `Leches Saborizadas` = `leche saborizada`. Garbled accents from a website (`TÃ© FrÃ­o`) are repaired.
- **English and abbreviations** — `lemon` = limón, `LMN` = limón, `almond` = almendra, `BEB` = bebida, `Chocoleche` = chocolate milk.
- **Words implied by another word** — a *colado/compota/papilla* is baby purée (`licuado`), *Gerber* is a baby product, a *muffin* is a `pan`, *champiñones* are `hongos`, a flavour (`fresa`, `chocolate`) makes milk `saborizada`, *Bebida de soya/almendra* is plant milk.
- **Generic or soft words** — `alimento` is optional when other words identify the product; `concentrado` is optional for lemon/lime juice (bottled lemon juice rarely says it).

### Category safeguards

Broad searches return look-alikes, so families have protections. Plain **water** does not accept flavored, sparkling, tonic, coconut, micellar or oxygenated water; plain **milk** does not accept powdered, condensed, evaporated, almond, soy, oat, formula, supplement or flavored milk — unless the BAP product (or its spreadsheet context) asks for that subtype.

Products marked as varied/assorted/generic are matched more flexibly *within* their category (e.g. assorted cereal accepts ordinary cereals), but not with anything remotely related (generic juice still rejects garlic juice).

Look-alike products are rejected for every product, not only specific families:

| Rejected | Example |
|---|---|
| Target word is only an ingredient/flavour/purpose (after *con, anti, sabor, para, en, sin*) | `Salsa de Tomate con Hongos`, `Clorox Anti Hongos`, `Atún en Aceite` |
| Title leads with a different product noun | `Salsa Maggi Tomate Hongos`, `Croquetas de Pescado`, `Gel de Baño … Leche de Almendras` |
| Made from the target (one-word targets) | `Pasta de Tomate` for *Tomate*, `Filete de Pescado Apanado` for *Pescado* |
| Cleaning, personal-care or pet products for a food item (uses *Categoria RepTrim*) | `Desinfectante … Limón`, `Alimento para Gatos … Pescado` |
| Alcoholic drinks | `Licor Te Frío …` |
| Mixes / preparations | `Mezcla de Muffin`, `Mezcla Té Frío` |
| Powders for ready-to-drink tea/juice | `Zuko Té Frío 13 g` |
| Speciality subtypes for a plain product | apple/balsamic/rice vinegar for plain *Vinagre*; peanut butter for *Mantequilla* |
| Extra flavours when the product names one | `Jugo Piña y Limón` for *Jugo de limón* |
| Canned goods for fresh produce (*Familia* = Fruver) and fresh produce for a canned product | `Tomates Pelados Enlatados` for *Tomate 2kg* |
| Different container dimensions | `Fiambrera 8x8` for *Fiambrera 7x7* |
| Speciality/premium versions of a plain product | `Mostaza Dijon`, organic, gourmet, protein, pasture-raised for plain *Mostaza*, *Alitas de pollo* … |
| Breaded/prepared versions of a raw product | `Filete de Pescado Apanado` for *Filete de pescado* |
| Titles led by the target's purpose word | `Pan de Masa Madre` for *Masa para pan* |
| Cooked, deli or seasoned versions of raw meat, poultry or fish (*Línea* Aves, Carnes rojas, Cerdo, Pescado y mariscos) | `Rollo de Pechuga`, `Pechuga Ahumada/Rostizada` for *Pechuga de pollo* |
| Artisan loaves and breadcrumbs for ordinary bread | masa madre, bâtard, brioche, ciabatta, panko for *Pan* |
| Bakery items whose title leads with the filling | `Queso de Cabra … Rollo` for *Rollos de queso* |

### Package size

Small packages usually cost more per kg, so candidates of similar size are preferred:

```python
MIN_SIZE_RATIO = 0.67
MAX_SIZE_RATIO = 1.50
```

The size group is chosen **once for all stores together**, so every store is compared on the same package sizes (a store that only sells small cans cannot pull the price per kg up):

1. near-exact sizes (0.80–1.25×) when there are enough of them;
2. otherwise the close range (0.67–1.50×);
3. otherwise — typically a bulk box much bigger than anything sold at retail — the retail size group nearest to the target that still has enough listings (preferably from 2+ stores). One unusually large pack cannot set the price alone.

At most `MAX_FALLBACK_SIZE_MATCHES` listings per store are kept from a fallback group.

**Meats sold by weight** (deli counter, priced per kg) can be bought in any quantity. For bulk meat boxes (*Familia* Cárnicos) they are added to the size group chosen from packaged products instead of choosing it, so a 17 kg "Embutidos varios" box is compared with ordinary packaged sausages and chorizo as well as the deli counter.

### Quantity normalization

Understands `kg, g, lb/libra, oz/fl oz/"Z", L, ml, cc, gallon (gal/gl)`, fractions (`1/2 GL`, `1 1/2 lb`), multipacks (`12 x 170g`, `250ml x 6`, `2 Pack`, `6PK`, drinks listed as `200ml 6 Unidades`), case listings priced per unit (`24/400ML`, `6 2LT`), deli items (`Por Media Libra`, `KILO`) and items each store sells **by weight** — Super 99 `sales_unit_of_measure = Kilogramo`, El Rey `unit = kg`, Super Xtra `measurement unit = kg` (price per `unit multiplier` kg), Riba Smith size `KG` or a weighed stock — whose listed price is per kg even when the title or size shows a whole log or pack weight. Business rule for comparison: **1 liter = 1 kilogram** (a pricing convention, not a density claim).

**Products counted in units.** When a BAP name gives a count and no weight or volume (`Fiambrera de Foam 50 unid 7x7`), prices are compared **per unit** instead of per kg: the *Target Quantity kg* column then holds the number of units and *Target Quantity Source* says `count basis`. Eggs are counted too: "Huevos 5 docenas" = 60 eggs, and store titles with "Docena", "30 und" or "15U" are priced per egg. Non-food items that give both a size and a count (`Vasos Plásticos 9oz 150und`, `Vasos 20x25 32oz`) are also counted: the 9 oz is the cup size, and only cups of a similar size are compared.

### Duplicates and outliers

Before averaging, near-duplicate listings and obvious price-per-kg outliers (median-based limits plus a robust log-MAD test) are removed. Everything removed stays visible in the *Candidates* output.

### Combining supermarkets

- **`store_balanced`** (default) — the market value level (above) inside each store, then combine the stores, each store weighted by its number of clean matches capped at 3 (`STORE_WEIGHT_CAP`). A store with a big online catalog doesn't dominate, and a store with a single listing doesn't count as much as one with several. E.g. Super 99 $4.00/kg (12 products), Super Xtra $3.80 (1), Rey $4.10 (15) → (4.00×3 + 3.80×1 + 4.10×3) / 7.
- **`all_candidates`** — apply the market value level to every surviving product together.

### Quality flags

```text
NO MATCHES · VERY HIGH RISK · HIGH RISK · LOW SEARCH CONFIDENCE
ONE STORE ONLY · TARGET SIZE WARNING · REQUEST ERROR
```

The evidence target is `MIN_GOOD_MATCHES = 5`. Fewer matches still give a price, flagged as weaker evidence — better than broadening the search until five wrong products are found.

- **LOW SEARCH CONFIDENCE** (one-word search) is only shown when the evidence is also thin (fewer than 5 clean matches or a single store).
- **TARGET SIZE WARNING** — the name and the *Unidad de Peso en KG* column disagree. A spreadsheet weight up to 1.5× the name's weight is treated as packaging (gross weight) and only noted.

Only the flags above send a product to review. A 1,000-product test showed they are the ones that predict a doubtful estimate (with 1–2 matches, 46% of estimates were more than 2× off the current price, against 21% for unflagged products).

**Notes** (column *Notes*, informational, not a reason for review):

- **PRICE SPREAD** — a wide price range (CV, and with 5+ prices the 10th–90th percentile ratio; limits 1.5× wider for *variado/surtido*). Normal for store brands vs premium; these estimates matched current prices better than unflagged ones.
- **Spreadsheet weight … probably includes packaging** — see TARGET SIZE WARNING.

**Deeper search for thin evidence.** When a store gives fewer than `MIN_GOOD_MATCHES` matches, the robot searches deeper there before settling: Super 99 up to 4 result pages (normally 2) and Riba Smith up to 3 (normally 2). El Rey and Super Xtra return one page (50 and 30 products).

---

## 6. Outputs

### Results file (`coincidencias_de_precios.xlsx` by default)

Written in Spanish for BAP. `results_format.py` decides the sheet names, the headers and which columns are shown.

- **Resumen** — one row per BAP product. Visible: *Código de producto*, *Nombre del producto*, *Peso del producto (kg)*, *Precio BAP actual*, **Precio BAP propuesto**, *Diferencia vs. actual*, *Cambio mayor a ±20%* (SÍ, highlighted; the label follows the configured limit), *Precio de mercado por kg*, *Supermercados*, *Productos comparables* and *Alertas* (the quality flags in plain Spanish).
- **Candidatos** — one row per store product checked. Visible: product code and name, *Supermercado*, *Producto en el supermercado*, *Estado* (Aceptado/Rechazado), *Precio*, *Tamaño (kg)*, *Precio por kg*, *Motivo* (in plain Spanish) and *Enlace*.

Columns that only the Review prices tab needs (search terms and confidence, per-store averages, the price statistics, the technical quality codes, the calculation settings, the Salesforce Id, …) are kept at the right of each sheet, **hidden**: BAP doesn't see them, but the review keeps working from the file alone. Columns nobody needs are left out. Results files from older versions (English headers, *Summary* / *Candidates* sheets) still open in the review.

`.csv` output is also possible (Resumen only, every kept column).

### Performance analysis (`analisis_de_desempeno.xlsx` by default)

Everything in Spanish, with every column (this file is for checking how the robot performed):

- **Panel** — products processed, with a proposed price, supported by 2+ supermarkets, without alerts, store products checked.
- **Análisis de productos** — the original product-sheet columns plus all of the robot's columns, the current price and difference, *Necesita revisión* (SÍ/NO), *Alertas* and *Motivo de revisión* (quality alerts and big price changes).
- **Candidatos** — the full candidate audit, with the technical reason and the plain-Spanish *Motivo*.

The default 20% limit is in Advanced settings → Review warnings.

---

## 7. Command line

```bash
py price_robot.py                                   # all products, all four stores
py price_robot.py --limit 20 --clear-cache          # quick fresh test
py price_robot.py --contains "leche" --stores super99,rey
py price_robot.py --type "Tipo A seco" --limit 100 --workers 6
py price_robot.py --list-stores
py price_robot.py --list-types
py price_robot.py --help
```

| Option | Purpose | Example |
|---|---|---|
| `--limit N` | Only the first N matching products | `--limit 100` |
| `--contains TEXT` | Only names containing the text (ignores case/accents) | `--contains "leche"` |
| `--type TYPE` | Filter `Sub-familia de Productos` | `--type "Tipo A seco"` |
| `--list-types` | Print the product types in the workbook | |
| `--products PATH` | Another product workbook (relative = next to `price_robot.py`) | `--products test.xlsx` |
| `--workers N` | Products searched at once (default 100, which worked well for the full 5,440-product list) | `--workers 20` |
| `--stores LIST` | Comma-separated stores | `--stores super99,rey` |
| `--store NAME` | Repeatable single store | `--store rey --store ribasmith` |
| `--list-stores` | Print available stores | |
| `--clear-cache` | Forget saved searches for the selected stores first | |
| `--no-cache` | Don't reuse saved searches this run | |
| `--average-mode MODE` | `store_balanced` or `all_candidates` | |
| `--output FILE` | Results file name (`.xlsx` or `.csv`) | `--output test.xlsx` |

Store IDs: `super99`, `superxtra`, `rey`, `ribasmith`. Aliases: `99`, `xtra`, `elrey`, `smrey`, `riba`, `riba-smith`, `riba_smith`.

Observed performance: **5,440 products at 100 workers in approximately 6 minutes**, and about 80 products at 6 workers in 47 seconds (all four stores, no search cache). The pre-run time estimate is fitted to both runs: seconds = products × (3.3 / workers + 0.033), scaled by the number of selected stores. More workers therefore help with diminishing returns (50 → ≈ 9 min, 100 → 6 min, 200 → ≈ 4.5 min for the full list) instead of scaling proportionally. Store response times, connection and search-cache hits change the real runtime; during a search the remaining-time display uses the actual pace (ignoring start-up time). Settings saved with the old default of 6 are moved to 100 once.

---

## 8. Supermarket adapters (`store_parsers/`)

Each website has its own adapter, so a site change usually means fixing one file. Adapters only fetch and normalize products into one common shape; all matching is in `matcher_core.py`:

```python
{"store": "rey", "sku": "123456", "name": "Arroz Especial 2kg",
 "price": 3.95, "regular_price": 3.95, "final_price": 3.95,
 "currency": "USD", "url": "...", "attrs": {...}}
```

| Store | File | Notes |
|---|---|---|
| Super 99 | `super99.py` | Adobe Commerce GraphQL: title, SKU, prices, attributes |
| Super Xtra | `superxtra.py` | VTEX search/runtime response |
| Rey | `rey.py` | Next.js/Instaleap fields (`name, price, sku, brand, stock, isAvailable, subUnit, subQty`); decodes the response as UTF-8; prefers the quantity in the title when metadata looks wrong; `unit = kg` means priced per kg |
| Riba Smith | `ribasmith.py` | Next.js RSC stream (header `rsc: 1` only — `next-router-prefetch` returns an empty stub); the product list sits inside `initialData`; 40 per page, 2 pages; titles have no size, so the `size` field (`32 OZ`) is used |

The regular/final price choice (`PRICE_BASIS`) is applied when results are matched, so changing it in Advanced settings takes effect even for cached search results.

---

## 9. Troubleshooting

**The app says Python components are missing** — accept its offer to install them, or run `py -m pip install -r requirements.txt`.

**"Could not save the results file"** — the file is open in Excel. Close it and search again.

**The app shows an unexpected-error message** — details are in `ui_errors.log`, in the folder the message names (`%LOCALAPPDATA%\Robot de Precios` for the installed app, or the project folder when running from source).

**Many store errors** — the site may have changed, the internet may be down, or too many searches ran at once. Try fewer simultaneous searches and a fresh cache, then test stores one at a time:

```bash
py price_robot.py --stores super99 --limit 20 --clear-cache
py price_robot.py --stores superxtra --limit 20 --clear-cache
py price_robot.py --stores rey --limit 20 --clear-cache
py price_robot.py --stores ribasmith --limit 20 --clear-cache
```

If one store fails, its adapter in `store_parsers/` is the likely fix.

**Riba Smith / Next Action IDs** — the scraper reads the search page's RSC product data directly, including nested `initialData`, without a `Next-Action` ID. There is no action ID to update after a site deployment. Do not add `next-router-prefetch`: it can return a loading shell without products. Missing product data is reported as an error rather than cached as an empty search. Changes to the site's search URL or product schema may still require an adapter update.

**A strange match or price** — open the performance analysis, *Candidates* sheet, and check Target Product, Candidate Product, Store, Normalized kg, Size Ratio, Price / kg, Status and **Reason**.

**The search won't start because of the current-prices file** — choose the current-prices report downloaded from Salesforce; it needs the columns `ProductCode`, `Id` and `UnitPrice` (any order). The message names the missing column. On the command line, put `current_prices.xlsx` in the folder you run from.

---

## 10. Design principles

- **Conservative before confident** — no estimate is better than an unrelated product quietly changing the price.
- **One matching system, many store adapters** — website parsing stays isolated; identity rules are shared.
- **Keep the audit trail** — every rejection, removal, size decision, error and flag is kept, so each price can be traced to its evidence.
- **Prefer comparable package sizes** — price per kg helps, but package size still matters.
- **Don't broaden just to reach five matches** — three strong matches flagged HIGH RISK beat five weak ones.
- **Store-balanced estimate** — each supermarket is one market source, however many products its site returns.
