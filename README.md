# Banco de Alimentos Panamá — Price Robot

Project layout: keep source, tests, build instructions and input spreadsheets in Git. `input/`, `products.xlsx` and `current_prices.xlsx` remain trackable. Runtime caches live in `cache/` (candidate indexes in a `cache/` folder beside their results), and new exports default to `output/`. Caches, outputs, review decisions/archives, local preferences, logs, bytecode, `build/` and `dist/` are ignored. Existing root-level exports are also ignored; ignoring/untracking generated files does not delete local copies.

Estimates current market prices for Banco de Alimentos Panamá (BAP) products by searching supermarket websites, matching each BAP product to comparable store products, cleaning the prices, and applying the BAP pricing rule.

Supported supermarkets:

- **Super 99** — Adobe Commerce / GraphQL search
- **Super Xtra** — VTEX search
- **Supermercados Rey (El Rey)** — Next.js / Instaleap search
- **Riba Smith** — Next.js / React Server Components search

It can be used two ways:

- **Desktop app** (recommended) — a Spanish/English window, no command line needed. Double-click `PriceRobot.exe`, or use `launch.bat` when running from source.
- **Command line** — `py price_robot.py …`, for scripting and debugging.

Both use exactly the same matching and pricing code.

---

## 1. Project files

```text
PRICEB/
├── launch.bat               # opens the desktop app (double-click)
├── price_robot_ui.py        # the desktop app (window)
├── robot_launcher.py        # runs price_robot.py with the app's settings
├── price_robot.py           # the price robot (search, clean, price, Excel output)
├── matcher_core.py          # shared matching / pricing rules
├── store_parsers/           # one adapter per supermarket website
│   ├── __init__.py
│   ├── base.py
│   ├── super99.py
│   ├── superxtra.py
│   ├── rey.py
│   └── ribasmith.py
├── requirements.txt
├── products.xlsx            # BAP product list (input)
└── current_prices.xlsx      # current BAP prices (optional input)
```

Created automatically while working (safe to delete; they are rebuilt):

| File | What it is |
|---|---|
| `cache/store_search_cache.sqlite3` | Saved supermarket responses (reused for 12 hours by default) |
| `cache/ui_products_cache.json` | Saved product list so the app's filters load instantly |
| `__pycache__/` | Python's compiled files |
| `ui_errors.log` | Only appears if the app hits an unexpected error |

`ui_settings.json` stores the app's language, recent files and Advanced settings. Deleting it resets them to defaults.

---

## 2. Installation

### Standalone Windows app

Use `dist/PriceRobot.exe` on 64-bit Windows. This single file includes Python, Tk, the scraper, review screens and Excel libraries; recipients do not need Python or Excel installed. Internet access is needed for supermarket searches. Copy the executable into a folder you can write to, open it, and select your product spreadsheet and optional current-price file. Spreadsheets, saved decisions and existing settings are not bundled into the executable.

Settings are stored beside the executable, caches under `cache/`, and default exports under `output/`. If the executable's folder is read-only, these go under `%LOCALAPPDATA%\BAP Price Robot`. Results can also be saved to the output folder selected in Advanced settings. To retain an existing setup, copy `ui_settings.json` alongside the executable, and keep results with their corresponding `.review.json` files. The executable may take a few seconds to unpack its bundled libraries at startup.

Build on Windows with the desired Python interpreter:

```powershell
python -m pip install -r requirements-build.txt
.\build_windows.ps1 -Python python
```

The build script produces `dist/PriceRobot.exe` and checks GUI startup plus the packaged worker. `PriceRobot.spec` controls the bundle. After source changes, rebuild the executable to include them. Optional diagnostic check: `PriceRobot.exe --self-test C:\path\report.json`.

### Running from source

Needs Python 3 (3.13 and 3.14 are known to work) plus two packages:

```bash
py -m pip install -r requirements.txt
```

(`requests` and `openpyxl`. If `py` is not available, use `python -m pip install -r requirements.txt`.)

If the packages are missing, the desktop app offers to install them for you.

---

## 3. Using the desktop app

Double-click **`launch.bat`** (or run `py price_robot_ui.py`). The **ES / EN** switch in the top-right corner changes the language.

### 1 · Files

- **Products** — choose the BAP product workbook with **Browse…** (nothing is pre-selected). **Recent ▾** lists the last few files used.
- **Create performance analysis** — on by default. Untick it to skip the second Excel file (dashboard + review columns); on big searches this saves time. The results file is created either way.
- **Compare with current BAP prices** — tick to choose a Salesforce current-prices Excel or CSV file, using `ProductCode`, `Id` and `UnitPrice` headers. Column order does not matter. Results get the current price, the % difference, and a review flag for big changes (see §7).

### 2 · Supermarkets

Tick the stores to search.

### 3 · Which products

- **Quick test** — the first N products in the selected product type (for example, the first 20 `Tipo A seco` products). Choose all types to use the first N products overall. The type filter is applied before the limit.
- **All products that match the filters** — selecting it opens the filters below it: *Product type* (the `Sub-familia de Productos` column) and *Name contains* (ignores capitals and accents). Filters are only used with this option.
- **Only the problems from a previous search** — choose an earlier results file, then tick which problems to search again: *no price*, *to review*, *store errors*, *big price change* (the last one only if that search had price comparison on). After each search, its results file is filled in here automatically.

The line at the bottom of this section shows how many products will be searched.

### Start, progress and results

Click **▶ Iniciar / Start**. **Stop** is only active while a search runs. The Progress section shows products done, elapsed time and time left. When finished it shows a summary (how many got a price, how many need review, big price changes) and buttons to open the results, the performance analysis and the folder. **Show technical details** shows the robot's full log.

If you're in another window when a long search finishes, the taskbar button flashes and the window title shows the result.

### Review and approve prices

After a successful search, **Review prices** opens the human verification step. **Open review…** also opens an existing results workbook (Summary + Candidates) or summary CSV without repeating the search. The performance-analysis workbook is not required.

1. Filter by confidence **1–5**, decision, or product name/code. Every product starts **Pending**, including high-confidence products. The table shows current, proposed and approved prices, dollar/percentage changes, and the human decision. Changes use the manually approved price when one has been entered.
2. Select a product to read short review notes: comparable listings by store and relevant missing-price, size, search, or price-variation observations. **Full evidence** reveals the diagnostics and supermarket listings when needed. Both views scroll with the mouse wheel. The confidence grade describes the proposed estimate; it is not a probability that the price is correct.
3. With the table focused, press **A** to accept or **R** to reject. Successful decisions automatically select the next visible item. Ctrl/Shift or click-and-drag selects multiple products; dragging past the table edge scrolls the selection. **Group actions → Accept/Reject visible group** acts only on the filtered rows and confirms the count before replacing decisions. Items without a usable price cannot be bulk accepted.
4. To override a selected product, **start typing a number**, then press **Enter** to save and advance. You can also edit the fixed **New price** box and click **Save price**. No reason is required. **Escape** cancels a draft edit. Current price, new price and bold percentage change remain in fixed positions; the percentage updates as you type. **Undo** (or Ctrl+Z while the table is focused) reverses the latest decision batch. **Group actions → Reset selected to pending** clears decisions. The rejected/unpriced filter makes missing estimates easy to work through.
5. **Export CSV…** creates a UTF-8 CSV containing exactly **`Id,UnitPrice`**, with prices written to two decimal places. `Id` is copied from the matching `ProductCode` row in the uploaded current-prices file. By default only explicitly accepted or manually approved prices are included. Pending, rejected and unpriced products are excluded. Export can proceed with pending products after displaying the pending count.

**Include unchanged current prices** additionally includes positive existing prices, including products outside the search. Pending/rejected proposals never overwrite those prices. An unpriced bath mat is excluded unless a reviewer supplies and approves a price. Every exported product must have an `Id` in the uploaded current-prices file; export lists missing IDs and stops instead of guessing or silently dropping approved rows. Product metadata cannot substitute for a Salesforce record ID.

**Categories ▾** expands filters for product type (`Tipo A seco`, etc.) and a second classification: match group, family, product line, RepTrim category or GFN type. Match group is the matcher's first generated search query (for example `pasta tomate`), not an invented classification. Category choices combine with score, decision and text filters. Search also finds category names and ignores accents. Click **Sort by category ↕** to group similar products; click any table heading to sort by that column, including numeric price changes. Active category filters are counted on the collapsed button.

**Choose candidates… / Elegir candidatos…** opens the selected product's saved listings in separate supermarket tabs. Each listing shows whether it is included, the matcher's original accepted/rejected decision, product price, normalized size, price per kg/unit and original reason. Select one or several listings and use **Include selected** or **Exclude selected**; the price preview updates across all supermarkets. **Open product page** opens the selected listing for verification. Listings without a usable normalized price cannot be included.

**Apply recalculated price** saves the choices, updates the proposed price and confidence, and returns the product to **Pending**, replacing any previous price approval. Accept the revised proposal through the normal review controls. Excluding every listing clears the proposal. **Cancel** discards draft choices; **Restore matcher choices** resets the draft to the original selections; the main review's **Undo** also reverses an applied candidate change. Original workbook evidence is preserved. Summary-only CSVs do not contain candidate details.

The candidate picker supports search by product, SKU, rejection reason or search query, plus filters for included/excluded listings, reviewer changes and the matcher's original decision. Filters apply across supermarket tabs but never change the price calculation. Click any column heading to sort; click again to reverse. Prices and quantities sort numerically, with missing values last. Drag across rows to select a range (including automatic scrolling at the edges); Ctrl-drag adds to the selection. Ctrl/Shift-click also work.

With the candidate list focused: **A / Enter** includes, **R / Delete** excludes and advances to the next visible listing, **Space** toggles the selection, **Ctrl+A** selects all visible listings in the current supermarket, **Ctrl+Z** undoes the last draft candidate change, and **O** opens the selected product page. **Ctrl+F** focuses search; **Ctrl+Enter** applies the draft; **Esc** cancels. Typing in search does not change candidate decisions. The picker also has an **Undo** button and visible/selected counts.

Recalculation uses the same package quantity, store weighting, market price level and BAP percentage formula as the scraper, without rerunning filters over the human's selected candidates. New results record the percentage, store-weight cap and economy percentile in the Summary sheet. Older results use the review's saved/current settings, falling back to code defaults for settings that were not saved.

Decisions, candidate choices, explanations and run settings save next to the results as `*.xlsx.review.json` (or `*.csv.review.json`). Keep that file with the results to resume. If the results or current-price file changes, the previous decisions are archived and the new review starts pending. Close the review before starting another search. The default template is `current_prices.xlsx`; a selected current-prices file takes precedence.

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

Verification: `python -m unittest test_price_review -v` tests scoring, decisions, persistence and export. `python -m unittest test_review_ui.ReviewUITests -v` additionally tests the desktop controls with hidden Tk windows in both languages.

### Advanced settings

Grouped in the order the robot works, each with a plain explanation and a live example:

1. **Store search** — simultaneous searches, search memory (cache) and how long it lasts, when to stop searching.
2. **Package size** — which store package sizes count as comparable.
3. **Price cleanup** — removing duplicates and prices far from the median.
4. **BAP price** — the BAP percentage, regular vs. sale price, how supermarkets are combined.
5. **Review warnings** — when a product is marked for review, including the big-price-change threshold.
6. **Results** — output folder, file names, keep each search (date/time in the name), open files when done.

Rarely needed settings are under *Expert settings*. Changes only apply to searches started from the app; `price_robot.py` and `matcher_core.py` are never modified.

---

## 4. Input files

### `products.xlsx`

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

### Current prices (`.xlsx`, `.xlsm` or `.csv`)

Use a Salesforce export with these headers (any column order):

| Header | Use |
|---|---|
| `ProductCode` | Matches the product code in the products/results workbook |
| `UnitPrice` | Current price for comparison |
| `Id` | PricebookEntry record ID, required for review CSV export |
| `Name` | Optional product name |
| `IsActive`, `LastModifiedDate`, `UseStandardPrice`, `Pricebook2Id` | Accepted as additional source fields; not included in the two-column output |

The supplied format has all fields needed for comparison and CSV updates. Categories such as `Tipo A seco`, family and product line still come from the original **products workbook**, because the Salesforce price sheet does not contain them. Select that workbook when starting the search. Use one pricebook entry per product: duplicate `ProductCode` or `Id` values produce a clear error. Missing/blank prices remain unavailable for comparison; malformed prices are reported.

Legacy `Código de producto` / `Precio de lista` headers remain supported for comparison, but exports require an `Id` for each included product.

In the app, choose it with *Compare with current BAP prices*. On the command line it is read from the folder you run in, if present.

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

- **Summary** — one row per BAP product: search terms and confidence, stores used, per-store averages, matches kept/removed, target quantity, average/median/economy/min/max price per kg, the market value level used, **Estimated New Product Price**, price spread, quality flag, request errors.
- **Candidates** — one row per store product checked: store, search term, ACCEPTED/REJECTED, product name, URL, prices, normalized kg, size ratio, price per kg and the **reason**. This is where to look when a match or price seems wrong.

`.csv` output is also possible (Summary only). The *Notes* column holds informational notes (price spread, packaging weight).

### Performance analysis (`analisis_de_desempeno.xlsx` by default)

- **Dashboard** — products processed, with an estimate, supported by 2+ stores, marked OK, candidate rows.
- **Product Analysis** — the original spreadsheet columns plus the robot's result, current BAP price, % difference and *Needs Manual Review*.
- **Candidates** — the full candidate audit.

### Price comparison columns (app, with *Compare with current BAP prices* on)

- Results *Summary*: **Current BAP Price**, **% Difference vs Current**, **Price Change > 20%** (YES highlighted, label follows the configured threshold).
- Results *Summary* also gets **Salesforce Id** (the PricebookEntry Id from the current-prices file), so a results file can be opened in the Review prices tab and exported to CSV on its own, without the current-prices file. Results from older versions without this column still ask for the current-prices file once; after that the saved review keeps its own copy.
- Performance analysis: *Needs Manual Review* also becomes YES for big price changes, and a **Review Reason** column explains why.

The default 20% threshold is in Advanced settings → Review warnings.

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

**The app shows an unexpected-error message** — details are in `ui_errors.log` in the project folder.

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

**No current-price comparison** — in the app, tick *Compare with current BAP prices* and choose the file. On the command line, put `current_prices.xlsx` in the folder you run from. Use `ProductCode` and `UnitPrice` headers; column positions are not used.

---

## 10. Design principles

- **Conservative before confident** — no estimate is better than an unrelated product quietly changing the price.
- **One matching system, many store adapters** — website parsing stays isolated; identity rules are shared.
- **Keep the audit trail** — every rejection, removal, size decision, error and flag is kept, so each price can be traced to its evidence.
- **Prefer comparable package sizes** — price per kg helps, but package size still matters.
- **Don't broaden just to reach five matches** — three strong matches flagged HIGH RISK beat five weak ones.
- **Store-balanced estimate** — each supermarket is one market source, however many products its site returns.
