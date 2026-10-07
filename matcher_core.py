from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from statistics import mean, median, pstdev

# Shared matching/business rules. Store parsers only fetch and normalize retailer data.
# The numeric settings below can be changed for one run from the desktop window
# (Advanced settings), which overrides them in memory.
MIN_GOOD_MATCHES = 5
BAP_MARKET_PRICE_PERCENT = 0.20
PRICE_BASIS = "regular"
MIN_SIZE_RATIO = 0.67
MAX_SIZE_RATIO = 1.50
PREFERRED_SIZE_RATIO_MIN = 0.80
PREFERRED_SIZE_RATIO_MAX = 1.25
MIN_PREFERRED_SIZE_MATCHES = 3
SIZE_CLUSTER_FACTOR = 1.75
MAX_FALLBACK_SIZE_MATCHES = 10
RAW_MATCH_STOP_COUNT = 10
PRICE_RATIO_WARNING = 1.75
PRICE_CV_WARNING = 0.30
HARD_OUTLIER_LOW_RATIO = 0.50
HARD_OUTLIER_HIGH_RATIO = 2.00
LOG_MAD_Z_THRESHOLD = 3.5
DUPLICATE_SIZE_TOLERANCE = 0.10
DUPLICATE_PRICE_TOLERANCE = 0.15
DUPLICATE_TOKEN_JACCARD = 0.80
# "Variado" targets accept several flavours/brands, so a wider price spread is
# expected before the variation warning is raised (thresholds are multiplied).
VARIETY_VARIATION_FACTOR = 1.5
# store_balanced averaging: each store's average is weighted by its number of
# clean matches, capped at this value, so one store with many listings cannot
# dominate and a store with a single listing does not count as much as a store
# with several.
STORE_WEIGHT_CAP = 3
# Which point of each product's market the BAP rule is applied to:
#   "average" - the average price per kg of all clean matches
#   "median"  - the middle price
#   "economy" - the cheaper end: the lower quartile (25th percentile) of each
#               store's prices, then the stores are combined as above
MARKET_PRICE_LEVEL = "economy"
ECONOMY_PERCENTILE = 0.25

SEARCH_STOPWORDS = {
    "empaque", "empacado", "empacada", "paquete", "pack", "caja", "cajeta",
    "bolsa", "botella", "bot", "lata", "frasco", "bap", "del", "de", "la",
    "el", "los", "las", "por", "para", "con", "en", "tipo", "original",
    "fabricante", "unidad", "unidades", "unid", "unids", "und", "uds", "u",
    "marca", "marcas", "carton", "cartones", "pv", "pre",
    "sabor", "sabores", "producto", "productos", "aprox", "aproximadamente",
    "kg", "kgs", "kilo", "kilos", "kilogramo", "kilogramos", "g", "gr",
    "gramo", "gramos", "lb", "lbs", "onza", "onzas", "oz", "ml", "l", "lt",
    "litro", "litros", "gal", "galon", "docena", "docenas",
    # "variado" means BAP accepts multiple variants; it must not become a literal
    # Super 99 query term or a required candidate word.
    "variado", "variada", "variados", "variadas", "vario", "varios", "varias",
    "surtido", "surtida", "surtidos", "surtidas", "etc",
    "y", "a", "al", "o", "un", "una", "pet", "tba", "tetra",
    "programa", "programas", "desayuno", "desayunos", "varioses",
    "paca", "pacas", "fardo", "fardos", "bulto", "bultos", "saco", "sacos", "display", "pqte", "pqt",
}

# Words in a BAP name meaning "any variety is fine".
VARIETY_WORDS = {
    "variado", "variada", "variados", "variadas", "vario", "varios", "varias",
    "surtido", "surtida", "surtidos", "surtidas", "mixto", "mixta", "mixtos", "mixtas",
}

# Deterministic aliases/normalizations. These are equivalence mappings, not
# fuzzy semantic guesses. They mainly handle English catalog names and common
# abbreviations/typos in retailer titles.
WORD_ALIASES = {
    "tomato": "tomate", "tomatoes": "tomate",
    "paste": "pasta",
    "juice": "jugo", "juic": "jugo",
    "water": "agua",
    "sparkling": "gas", "carbonated": "gas", "carbonatada": "gas",
    "carbonatado": "gas", "gasificada": "gas", "gasificado": "gas",
    "flavored": "saborizada", "flavoured": "saborizada", "saboriz": "saborizada",
    "oil": "aceite",
    "rice": "arroz",
    "milk": "leche",
    "powder": "polvo", "powdered": "polvo",
    "almond": "almendra", "soy": "soya", "soja": "soya", "oat": "avena", "oatmeal": "avena",
    "tea": "te",
    "syrup": "sirope",
    "flour": "harina",
    "bread": "pan",
    "puro": "puro", "pur": "puro",
    "clas": "clasico",
    "trad": "tradicional",
    "duraz": "durazno", "melocoton": "durazno", "peach": "durazno",
    "maizena": "maicena",
    "baby": "bebe",
    "infant": "bebe", "infantil": "bebe",
    "hazelnut": "avellana",
    "coconut": "coco",
    "goat": "cabra",
    "lactosefree": "deslactosado",
    "prefrita": "frita", "prefritas": "frita",
    # Common English / abbreviated retailer spellings.
    "lemon": "limon", "lmn": "limon", "lime": "lima", "orange": "naranja", "apple": "manzana",
    "strawberry": "fresa", "frutilla": "fresa", "grape": "uva", "pineapple": "pina",
    "banana": "banano", "vanilla": "vainilla", "choco": "chocolate",
    "chocolatada": "chocolate", "chocolatado": "chocolate",
    "chocorico": "chocolate", "chocorrico": "chocolate",
    "mushroom": "hongo", "champignon": "champinon",
    "vinegar": "vinagre", "soup": "sopa", "food": "alimento",
    "gaseosa": "soda",
    "beb": "bebida", "bebi": "bebida",
    "consentrado": "concentrado", "concent": "concentrado", "conc": "concentrado",
    "mix": "mezcla",
    "cider": "sidra", "balsamic": "balsamico",
    "liqueur": "licor",
    "manazana": "manzana", "jueguete": "juguete", "churroz": "churro", "cramberry": "cranberry",
    "frecco": "fresco", "rost": "rostizado", "empanz": "empanizado", "pasto": "pastoreo",
    "asada": "asado", "asados": "asado", "asadas": "asado", "hamb": "hamburguesa", "organic": "organico",
}

# Adjectives are compared in their masculine form, so "instantánea" and
# "instantáneo" (or "entera"/"entero") are the same word.
_GENDERED_ADJECTIVES = {
    "instantaneo", "saborizado", "descremado", "semidescremado", "deslactosado", "evaporado",
    "condensado", "entero", "liquido", "congelado", "enlatado", "tostado", "concentrado",
    "frio", "fresco", "refrigerado", "deshidratado", "seco", "precocido", "blanco",
    "amarillo", "rojo", "negro", "moreno", "variado", "surtido", "picado", "rallado",
    "molido", "ahumado", "cocido", "crudo", "salado", "mixto", "enriquecido", "fortificado",
    "pasteurizado", "organico", "clasico", "rebanado", "deshuesado", "fileteado",
    "empanizado", "relleno", "azucarado", "endulzado", "sazonado", "rostizado", "horneado",
    "grueso", "fino", "largo", "corto", "pequeno", "mediano", "puro", "licuado", "colado",
    "cremoso", "picoso", "natural", "enlatado", "sancochado",
}
FEMININE_TO_MASCULINE = {w[:-1] + "a": w for w in _GENDERED_ADJECTIVES if w.endswith("o")}

# Words that strongly change identity. All meaningful target words are required
# in v4, but these are also used to increase search confidence and catch
# explicit subtype conflicts.
IDENTITY_MODIFIERS = {
    "saborizado", "saborizada", "integral", "especial", "primera", "precocido", "precocida",
    "jazmin", "basmati", "evaporado", "evaporada", "condensado", "condensada", "descremado", "descremada",
    "semidescremado", "semidescremada", "entero", "entera", "vegetal", "picante", "dulce", "liquido", "liquida",
    "congelado", "congelada", "enlatado", "enlatada", "tostado", "tostada", "instantaneo", "instantanea", "polvo",
    "concentrado", "concentrada", "frio", "fria", "deslactosado", "deslactosada", "almendra", "soya", "avena",
    "coco", "avellana", "canola", "girasol", "oliva", "maiz", "tonica",
    "gas", "mineral",
}

GENERIC_QUERY_WORDS = {
    "agua", "pescado", "harina", "aderezo", "yogurt", "soda", "jugo", "carne",
    "pan", "leche", "aceite", "cereal", "galleta", "salsa", "snack", "sirope",
    "vinagre", "embutido", "embutidos",
}

MODIFIER_GROUPS = [
    {"integral", "especial", "primera", "precocido", "precocida", "jazmin", "basmati"},
    {"entero", "entera", "descremado", "descremada", "semidescremado", "semidescremada", "deslactosado", "deslactosada"},
    {"evaporado", "evaporada", "condensado", "condensada", "polvo", "liquido", "liquida"},
    {"vegetal", "oliva", "canola", "girasol", "maiz", "coco", "soya", "almendra", "avellana"},
    {"picante", "dulce"},
    {"blanco", "blanca", "amarillo", "amarilla", "rojo", "roja", "negro", "negra", "moreno", "morena", "verde"},
]

# Product-family-specific false positives seen commonly in supermarket search.
FAMILY_FORBIDDEN = {
    "soda": {"baking", "bicarbonato"},
    "agua": {"oxigenada", "micelar"},
}

# Subtypes that should NOT silently satisfy a generic/plain family search.
# They are only forbidden when the target itself does not request that subtype.
# Example: generic "Agua" rejects sparkling/flavored water, while
# "Agua saborizada" is still allowed because "saborizada" is in the target.
FAMILY_UNSPECIFIED_FORBIDDEN = {
    "agua": {"gas", "saborizado", "saborizada", "tonica", "coco"},
    "leche": {
        "polvo", "instantaneo", "instantanea", "evaporado", "evaporada", "condensado", "condensada", "saborizado", "saborizada",
        "vegetal", "almendra", "soya", "avena", "coco", "avellana",
        "formula", "crema", "deslactosado", "deslactosada", "cabra", "bebe", "arroz",
    },
    # Plain vinegar is white/cane vinegar; speciality vinegars cost several times more.
    "vinagre": {"manzana", "balsamico", "vino", "arroz", "sidra", "jerez", "frambuesa", "coco", "modena"},
    # Ready-to-drink tea/juice targets must not take powders or mixes (priced per gram of powder).
    "te": {"polvo", "instantaneo", "mezcla"},
    "jugo": {"polvo", "instantaneo", "mezcla", "concentrado"},
    "cereal": {"barra"},
    "huevo": {"codorniz", "pato", "chocolate", "pascua"},
    "aceite": {"bebe", "spray", "esencial"},
}

# A target word that makes another subtype word acceptable: instant whole milk
# powder is ordinary "leche en polvo".
TARGET_ALLOWS = {
    "polvo": {"instantaneo"},
}

# Words that describe storage/form but are often omitted from retailer titles.
# They are not required for a positive match, but explicit conflicts are still
# rejected (e.g. a fresh target will not accept a title that explicitly says
# frozen/canned).
OPTIONAL_IDENTITY_WORDS = {"fresco", "fresca", "congelado", "congelada", "refrigerado", "refrigerada"}
FORM_CONFLICT_GROUP = {"fresco", "fresca", "congelado", "congelada", "enlatado", "enlatada", "deshidratado", "deshidratada", "seco", "seca"}

# Generic words that add nothing when a BAP name has other identity words:
# "Alimento licuado para bebé" is identified by "licuado" + "bebé".
GENERIC_OPTIONAL_WORDS = {"alimento", "comida"}

# Target word -> words that may be missing from a retailer title when the target
# also contains one of the trigger words. Bottled lemon juice is sold as "Jugo de
# limón" even though it is the concentrated product.
OPTIONAL_WHEN_TARGET_HAS = {
    "concentrado": {"limon", "lima"},
    "gallina": {"huevo"},       # "Huevos de gallina": store titles just say "Huevos"
    "liquido": {"leche"},       # ordinary milk is liquid; titles rarely say so
}

# Candidate evidence: a retailer word that implies target words it does not
# spell out. Each entry is (implied words, required context or None). The
# context, when given, must also appear in the candidate title.
CANDIDATE_IMPLIES = {
    "colado": ({"licuado", "bebe"}, None),
    "papilla": ({"licuado", "bebe"}, None),
    "compota": ({"licuado"}, None),
    "pure": ({"licuado"}, None),
    "gerber": ({"bebe"}, None),
    "chocoleche": ({"leche", "chocolate", "saborizado"}, None),
    "almondmilk": ({"leche", "almendra"}, None),
    "oatmilk": ({"leche", "avena"}, None),
    "soymilk": ({"leche", "soya"}, None),
    "muffin": ({"pan"}, None),
    "champinon": ({"hongo"}, None),
    "seta": ({"hongo"}, None),
    "portobello": ({"hongo"}, None),
    "shiitake": ({"hongo"}, None),
    "avena": ({"cereal"}, {"instantaneo", "hojuela"}),
    "granola": ({"cereal"}, None),
    "bebida": ({"leche"}, {"soya", "almendra", "avena", "coco", "arroz", "avellana"}),
    "zuko": ({"polvo"}, None),
    "tang": ({"polvo"}, None),
    "clight": ({"polvo"}, None),
    "livean": ({"polvo"}, None),
    "kool": ({"polvo"}, None),
    "rika": ({"polvo"}, {"aid", "bebida"}),
    "sobre": ({"polvo"}, {"sopa", "crema", "caldo", "consome"}),
}

# Flavours. A flavour in a milk/water/yogurt/drink title means it is flavoured;
# a target that names a flavour rejects titles adding other flavours.
FLAVOR_WORDS = {
    "limon", "lima", "naranja", "mandarina", "pina", "manzana", "uva", "fresa", "mango",
    "maracuya", "guayaba", "durazno", "pera", "banano", "cereza", "frambuesa", "mora",
    "arandano", "sandia", "melon", "tamarindo", "toronja", "chocolate", "vainilla",
    "caramelo", "miel", "raspadura", "panela", "jengibre", "zanahoria", "remolacha",
    "pepino", "menta", "guanabana", "papaya", "kiwi", "acerola", "maranon", "nance",
    "granadilla", "ponche", "frutal", "cola", "blueberry", "passionfruit",
}
FRUIT_WORDS = FLAVOR_WORDS - {"chocolate", "vainilla", "caramelo", "miel", "raspadura", "panela", "menta", "cola"}
FLAVORABLE_FAMILIES = {"leche", "agua", "yogurt", "bebida"}

# Retail titles in which the target word only appears as an ingredient, flavour
# or purpose: "Salsa ... con Hongos", "Clorox Anti Hongos", "Atún en Aceite",
# "Galletas sabor a Chocolate". The main product must come before these words.
SUBORDINATE_MARKERS = {"con", "anti", "sabor", "aroma", "para", "en", "c", "sin"}

# Nouns that name a different product when they lead a title before the target
# word: "Salsa Maggi Tomate Hongos" is a sauce, not mushrooms.
PRODUCT_NOUNS = {
    "salsa", "crema", "sopa", "pasta", "jugo", "leche", "aceite", "galleta", "pan", "cereal",
    "bebida", "te", "cafe", "yogurt", "queso", "harina", "arroz", "agua", "soda", "vinagre",
    "sirope", "mermelada", "helado", "pastel", "torta", "pizza", "snack", "barra", "jabon",
    "shampoo", "detergente", "desinfectante", "limpiador", "aplicador", "esponja", "mezcla",
    "aderezo", "mayonesa", "ketchup", "mostaza", "condimento", "sazonador", "caldo", "consome",
    "cubito", "gelatina", "pudin", "flan", "licor", "cerveza", "vino", "salsita",
    "atun", "sardina", "pollo", "carne", "embutido", "salchicha",
    "chorizo", "jamon", "mortadela", "papa", "tortilla", "nacho", "chip", "palomita",
    "avena", "granola", "compota", "colado", "refresco", "nectar", "concentrado", "polvo",
    "suavizante", "cloro", "vela", "insecticida", "ambientador", "toallita", "gel",
    "lava", "ceviche", "brocheta", "croqueta", "pincho", "panko", "dedito", "nugget", "hamburguesa", "empanada", "dip", "vinagreta",
}

# Products that are never the answer for a food target.
NON_FOOD_WORDS = {
    "detergente", "desinfectante", "limpiador", "limpieza", "cloro", "clorox", "blanqueador",
    "jabon", "shampoo", "champu", "acondicionador", "suavizante", "insecticida", "repelente",
    "ambientador", "aromatizante", "lavaplato", "toallita", "desodorante", "dental",
    "cepillo", "fungicida", "antihongo", "antimicotico", "locion", "bloqueador",
    "lysol", "raid", "fabuloso", "harpic", "biberon", "mamadera", "chupon", "tetina",
    "esponja", "aplicador", "maquillaje", "makeup", "antibacterial", "corporal", "motor",
    "capilar", "masaje", "llanta", "juguete", "bateria", "bano",
    # cleaning brands that often omit the product type ("AXION LIMON 1KG")
    "axion", "salvo", "laborin", "mistolin", "pinesol", "suavitel", "downy", "ariel", "ajax",
}
# Pet products are rejected unless the BAP product itself is for pets.
PET_WORDS = {
    "perro", "gato", "mascota", "cachorro", "gatito", "felino", "canino", "chow", "pedigree", "whiskas",
    # pet food brands whose titles often omit "perro/gato"
    "gati", "purina", "alimiau", "friskies", "felix", "mimaskot", "ascan", "rufo", "dogourmet",
}
ALCOHOL_WORDS = {
    "licor", "cerveza", "beer", "ron", "vodka", "whisky", "whiskey", "tequila", "ginebra",
    "seltzer", "sangria", "wine", "alcohol", "alcoholica", "alcoholico", "aguardiente", "herrerano",
}
# Fresh-produce targets (Familia "Fruver") must not take canned/processed goods.
FRESH_FAMILIES = {"fruver"}
PROCESSED_WORDS = {
    "enlatado", "conserva", "lata", "frasco", "triturado", "deshidratado", "frito", "pasta",
    "salsa", "pure", "dip", "vinagreta", "encurtido", "mermelada", "jugo", "almibar", "chip",
    "sopa", "crema", "polvo", "parrilla", "marinado", "pelado", "seco", "congelado", "snack",
}

# Speciality / premium versions that a plain BAP product must not be priced
# from (a plain "Mostaza" is not Dijon; plain "Alitas" are not pasture-raised).
SPECIALITY_WORDS = {
    "dijon", "organico", "gourmet", "trufa", "trufado", "keto", "gluten", "vegano", "vegan",
    "proteina", "protein", "pastoreo", "wagyu", "angus", "kosher",
    # artisan bakery loaves vs ordinary packaged bread
    "madre", "batard", "brioche", "ciabatta",
}
# Families (Familia de productos) whose sold-by-weight listings join the chosen
# package-size group for bulk targets instead of choosing it (see
# filter_preferred_size_matches). Not used for fresh produce, where the per-kg
# price IS the right comparison.
SIZE_NEUTRAL_WEIGHED_FAMILIES = {"carnicos"}
BAKERY_FAMILIES = {"panaderia"}
# Deli / cooked / seasoned versions of RAW meat, poultry and fish, rejected
# for products in these lines (Linea de producto) unless the name asks for them.
RAW_MEAT_LINES = {"aves", "carnes rojas", "cerdo", "pescado y mariscos"}
DELI_WORDS = {
    "rollo", "ahumado", "fiambre", "tubo", "rostizado", "asado", "cocido", "jamon", "embutido",
    "marinado", "hierba", "pimienta", "adobado", "sazonado", "horneado", "relleno", "nugget",
}
# Breaded / prepared versions of a raw product.
PREPARED_WORDS = {"apanado", "empanizado", "rebozado", "empanado"}

# A title with one of these words is a preparation/ingredient, not the product.
DERIVED_PRODUCT_WORDS = {"mezcla", "premezcla", "saborizante", "esencia"}

# Spreadsheet metadata is valuable when a product name is too generic. Only
# family-specific modifiers are borrowed from Linea/Descripcion; arbitrary
# spreadsheet words are never made mandatory.
CONTEXT_MODIFIERS_BY_FAMILY = {
    "leche": {
        "entero", "entera", "descremado", "descremada", "semidescremado", "semidescremada", "deslactosado", "deslactosada", "polvo",
        "evaporado", "evaporada", "condensado", "condensada", "saborizado", "saborizada", "almendra", "soya", "avena",
        "coco", "avellana",
    },
    "agua": {"saborizado", "saborizada", "gas", "mineral", "coco", "tonica"},
    "aceite": {"oliva", "canola", "girasol", "maiz", "coco", "soya"},
    "arroz": {"integral", "jazmin", "basmati", "precocido", "precocida"},
    "te": {"frio"},
}

# Generic family names whose BAP description explicitly means a group of
# possible products rather than a literal word that must occur in the SKU.
GENERIC_FAMILY_MEMBERS = {
    "embutido": {"chorizo", "mortadela", "salchicha", "salami", "pepperoni", "jamon"},
    "menestra": {"frijol", "poroto", "lenteja", "garbanzo", "arveja", "guandu"},
}

# Extra search queries used only when the first queries did not find enough
# matches. Keys are target words; values replace that word in the query.
QUERY_SYNONYMS = {
    "licuado": "colado",
    "hongo": "champinon",
}

LIQUID_FAMILIES = {"agua", "leche", "jugo", "aceite", "soda", "te", "vinagre", "sirope", "bebida"}
SOLID_MASS_FAMILIES = {"canela", "harina", "arroz", "frijol", "cereal", "galleta", "maicena", "sal", "azucar", "avena"}
GENERIC_FAMILY_FORBIDDEN = {
    "chocolate": {"pediasure", "ensure", "suplemento", "bebida", "leche", "soya", "almendra", "avellana"},
    "mantequilla": {"pan", "galleta", "palomita", "popcorn", "mani", "cacahuate", "almendra", "coco", "avellana"},
    "galleta": {"helado"},
    "waffle": {"papa", "potato", "frita", "frie", "hash"},
    "canela": {"crema", "avena", "hojuela", "coffee", "mate", "manzana", "te", "bebida"},
}

# If the BAP product is only one generic identity word, require that word to
# occur early in the retailer title. This rejects e.g. "Atun ... en Aceite"
# for a generic "Aceite" target while allowing "Borges Aceite ...".
MAX_GENERIC_HEAD_POSITION = 3


@dataclass
class Quantity:
    kg: float | None
    source: str


@dataclass
class PriceChoice:
    chosen: float | None
    regular: float | None
    final: float | None
    currency: str
    basis: str
    discount_percent: float | None


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

_MOJIBAKE_RE = re.compile(
    "[\u00c2-\u00df][\u0080-\u00bf]"
    "|[\u00e0-\u00ef][\u0080-\u00bf]{2}"
    "|[\u00f0-\u00f4][\u0080-\u00bf]{3}"
)


def repair_text(text: object) -> str:
    """Undo UTF-8 text that was decoded as Latin-1 ("TÃ© FrÃ­o" -> "Té Frío")."""
    s = "" if text is None else str(text)
    if "\u00c3" not in s and "\u00c2" not in s:
        return s

    def fix(m):
        chunk = m.group(0)
        try:
            return chunk.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return chunk

    return _MOJIBAKE_RE.sub(fix, s)


def normalize(text: object) -> str:
    s = repair_text(text)
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace(",", ".")
    return re.sub(r"[^a-z0-9.]+", " ", s).strip()


def _strip_plural(w: str) -> str:
    # Spanish plural cleanup. Handle common consonant+es plurals first, then the
    # simple -s case (the naive version produced vegetale, frijole, ...).
    if len(w) > 5 and w.endswith("ces"):
        return w[:-3] + "z"              # nueces -> nuez
    if len(w) > 6 and w.endswith(("ores", "ales", "oles", "ones", "anes")):
        return w[:-2]                    # sabores->sabor, vegetales->vegetal
    if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]                    # tomates->tomate, jugos->jugo
    return w


def canonical_word(word: str, gender: bool = True) -> str:
    """Canonical form used for comparisons (alias, singular, masculine adjective)."""
    w = WORD_ALIASES.get(word, word)
    w = _strip_plural(w)
    w = WORD_ALIASES.get(w, w)
    if gender:
        w = FEMININE_TO_MASCULINE.get(w, w)
    return w


def _canon_set(words) -> set[str]:
    return {canonical_word(w) for w in words} | set(words)


def identity_source_text(product_name: str) -> str:
    """Remove parenthetical context before identity tokenization.

    BAP names sometimes contain examples such as
    "Embutidos varios 17kg (chorizos, mortadelas, salchichas, etc.)".
    Those examples describe the family; they are not all mandatory words in one
    supermarket SKU.
    """
    return re.sub(r"\([^)]*\)", " ", str(product_name))


def normalize_quantity_text(text: object) -> str:
    """Normalize quantity text while preserving '/' used in case-pack notation."""
    s = repair_text(text)
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace(",", ".")
    s = re.sub(r"\bfl\.?\s*(?=oz\b)", "", s)          # "12 fl oz" -> "12 oz"
    s = re.sub(r"(?<=\d)\s*\"", " ", s)                # 7" x 7" -> 7 x 7
    return re.sub(r"[^a-z0-9./]+", " ", s).strip()


# Every unit the quantity parser understands, in kg (1 L == 1 kg by project rule).
_UNIT_FACTORS = {
    "kg": 1.0, "kgs": 1.0, "kgr": 1.0, "kgrs": 1.0, "kilo": 1.0, "kilos": 1.0,
    "kilogramo": 1.0, "kilogramos": 1.0,
    "g": 0.001, "gr": 0.001, "grs": 0.001, "grm": 0.001, "grms": 0.001, "gm": 0.001, "gms": 0.001,
    "gramo": 0.001, "gramos": 0.001,
    "lb": 0.45359237, "lbs": 0.45359237, "libra": 0.45359237, "libras": 0.45359237,
    "oz": 0.028349523125, "onz": 0.028349523125, "onza": 0.028349523125, "onzas": 0.028349523125,
    "z": 0.028349523125,
    "l": 1.0, "lt": 1.0, "lts": 1.0, "ltr": 1.0, "ltrs": 1.0, "litro": 1.0, "litros": 1.0,
    "ml": 0.001, "mls": 0.001, "cc": 0.001,
    "gal": 3.785411784, "gl": 3.785411784, "gln": 3.785411784, "galon": 3.785411784,
    "galones": 3.785411784,
}
_VOLUME_UNITS = {"l", "lt", "lts", "ltr", "ltrs", "litro", "litros", "ml", "mls", "cc", "gal", "gl", "gln", "galon", "galones"}
_MASS_UNITS = {"kg", "kgs", "kgr", "kgrs", "kilo", "kilos", "kilogramo", "kilogramos", "g", "gr", "grs", "grm",
               "grms", "gm", "gms", "gramo", "gramos", "lb", "lbs", "libra", "libras"}
# Ounces are ambiguous (weight or fluid ounces) so they are neither.
_UNITS_RE = "|".join(sorted(map(re.escape, _UNIT_FACTORS), key=len, reverse=True))
_NUM = r"\d+(?:\.\d+)?"
_COUNT_WORDS = r"unidades|unidad|unids|unid|unds|und|uds|un|u|piezas|pieza|pzas|pza|pcs|pc|ct|count"


def _unit_factor_map() -> dict[str, float]:
    return dict(_UNIT_FACTORS)


def repair_quantity_text(text: str) -> tuple[str, str | None]:
    """Repair narrow malformed decimals without corrupting slash case packs."""
    s = normalize_quantity_text(text)
    repair_note = None
    pat = re.compile(
        r"(?<![/.\d])\b(\d{1,2})\s+([0-9])\s*"
        r"(kg|kgs|kilo|kilos|l|lt|lts|litro|litros|ml)\b"
    )

    def repl(m):
        nonlocal repair_note
        original = m.group(0)
        whole, frac, unit = m.group(1), m.group(2), m.group(3)
        if frac == "5" or whole in ("0", "1"):
            # "2 5 LTS" -> 2.5L, "1 8 L" -> 1.8L
            fixed = f"{whole}.{frac}{unit}"
            repair_note = f"repaired ambiguous quantity '{original}' as '{fixed}'"
        else:
            # "SODA FRESA PET 6 2LT" is a 6 x 2L case listing priced per bottle.
            fixed = f"{whole}/{frac}{unit}"
            repair_note = f"read '{original}' as case pack {fixed}"
        return fixed

    s = pat.sub(repl, s)

    # "1 89L" / "3 78 L" (litre sizes with the decimal point lost).
    pat2 = re.compile(r"(?<![/.\d])\b([1-9])\s+(\d{2})\s*(l|lt|lts|litro|litros|kg|kgs)\b")

    def repl2(m):
        nonlocal repair_note
        fixed = f"{m.group(1)}.{m.group(2)}{m.group(3)}"
        repair_note = f"repaired ambiguous quantity '{m.group(0)}' as '{fixed}'"
        return fixed

    s = pat2.sub(repl2, s)
    return s, repair_note


def strip_quantity_text(text: str) -> str:
    s, _ = repair_quantity_text(identity_source_text(text))
    units = _UNITS_RE
    # x-pack and slash-pack quantities.
    s = re.sub(rf"\b{_NUM}\s*x\s*{_NUM}\s*(?:{units})\b", " ", s)
    s = re.sub(rf"\b\d+\s*/\s*{_NUM}\s*(?:{units})\b", " ", s)
    # Simple quantities / counts.
    s = re.sub(
        rf"\b{_NUM}\s*(?:{units}|unidades?|unid|unids|und|uds|docenas?|pack|pk|pck|un)\b",
        " ", s,
    )
    # Packaging dimensions such as 7x7; useful for auditing but poor search text.
    s = re.sub(rf"\b{_NUM}\s*[x/]\s*{_NUM}\b", " ", s)
    s = re.sub(rf"\b{_NUM}\b", " ", s)
    return re.sub(r"\s+", " ", s.replace("/", " ")).strip()


def _tokens_with_surface(product_name: str) -> list[tuple[str, str]]:
    """(canonical token, search form) pairs, in title order, without repeats."""
    cleaned = strip_quantity_text(product_name)
    out: dict[str, str] = {}
    for raw in cleaned.split():
        raw = raw.strip(".")
        if raw in SEARCH_STOPWORDS or len(raw) <= 1:
            continue
        t = canonical_word(raw)
        if t and t not in SEARCH_STOPWORDS and t not in out:
            out[t] = canonical_word(raw, gender=False)
    return list(out.items())


def semantic_tokens(product_name: str) -> list[str]:
    return [t for t, _ in _tokens_with_surface(product_name)]


def _base_head(product_name: str) -> str | None:
    toks = semantic_tokens(product_name)
    return toks[0] if toks else None


def is_variety_target(product_name: str) -> bool:
    return bool(set(normalize(identity_source_text(product_name)).split()) & VARIETY_WORDS)


def context_modifier_tokens(product_name: str, target_context: dict | None = None) -> set[str]:
    if not target_context:
        return set()
    head = _base_head(product_name)
    allowed = _canon_set(CONTEXT_MODIFIERS_BY_FAMILY.get(head, set()))
    if not allowed:
        return set()
    blob = " ".join(str(v or "") for v in target_context.values())
    return set(semantic_tokens(blob)) & allowed


def required_identity_tokens(product_name: str, target_context: dict | None = None) -> list[str]:
    """Identity words that a candidate must preserve.

    Storage/form descriptors such as "fresh" are allowed to be omitted from a
    retailer title, while strong subtype words and safe spreadsheet context
    (e.g. Linea='Leche entera') remain requirements.
    """
    optional = _canon_set(OPTIONAL_IDENTITY_WORDS)
    if normalize((target_context or {}).get("family")) in FRESH_FAMILIES:
        optional |= {"entero"}          # "Limones enteros": fresh produce is whole
    base = [t for t in semantic_tokens(product_name) if t not in optional]
    for t in sorted(context_modifier_tokens(product_name, target_context)):
        if t not in base:
            base.append(t)
    return base


def _effective_required(req: list[str]) -> list[str]:
    """Required words a candidate must actually show (generic/soft words dropped)."""
    req_set = set(req)
    out = []
    for t in req:
        if t in GENERIC_OPTIONAL_WORDS and len(req) > 1:
            continue
        triggers = OPTIONAL_WHEN_TARGET_HAS.get(t)
        if triggers and req_set & triggers:
            continue
        out.append(t)
    return out or list(req)


def build_queries(product_name: str, target_context: dict | None = None) -> tuple[list[str], str, str]:
    """Build specific discovery queries without broadening away identity."""
    req = required_identity_tokens(product_name, target_context)
    if not req:
        return [], "LOW", "No usable identity words after removing size/packaging text"

    surface = dict(_tokens_with_surface(product_name))
    words = [surface.get(t, t) for t in req]
    queries: list[str] = []
    head = req[0]

    if len(req) == 1:
        queries = [words[0]]
        if head in GENERIC_FAMILY_MEMBERS:
            queries.extend(sorted(GENERIC_FAMILY_MEMBERS[head])[:5])
        if head in QUERY_SYNONYMS:
            queries.append(QUERY_SYNONYMS[head])
        warning = (
            "Generic one-word search; family/subtype guardrails and manual review recommended"
            if head in GENERIC_QUERY_WORDS
            else "One-word search; manually review matches"
        )
        return list(dict.fromkeys(queries)), "LOW", warning

    queries.append(" ".join(words[:4]))
    if len(req) >= 3:
        for alt in (" ".join([words[0], words[-1]]), " ".join(words[:2])):
            if alt not in queries:
                queries.append(alt)

    # Fallback queries: drop words that another target word already implies
    # ("pan muffin" -> "muffin") or generic words, then try known synonyms.
    implied = set()
    for t in req:
        implied |= CANDIDATE_IMPLIES.get(t, (set(), None))[0]
    effective = _effective_required(req)
    reduced = [surface.get(t, t) for t in effective if t not in implied]
    if reduced and " ".join(reduced[:4]) not in queries:
        queries.append(" ".join(reduced[:4]))
    for t in effective:
        syn = QUERY_SYNONYMS.get(t)
        if syn:
            syn_implied = CANDIDATE_IMPLIES.get(syn, (set(), None))[0]
            q = " ".join([syn] + [surface.get(x, x) for x in effective if x != t and x not in syn_implied][:3])
            if q not in queries:
                queries.append(q)

    identity_mods = set(req) & _canon_set(IDENTITY_MODIFIERS)
    confidence = "HIGH" if identity_mods or len(req) >= 3 else "MEDIUM"
    warning = (
        "Strict identity validation requires: " + ", ".join(req)
        if confidence == "HIGH"
        else "Two-word query; strict candidate validation still requires both identity words"
    )
    return queries, confidence, warning


# ---------------------------------------------------------------------------
# Quantities
# ---------------------------------------------------------------------------

def quantity_kind(text: str) -> str | None:
    s = normalize_quantity_text(text)
    units = [m.group(1) for m in re.finditer(rf"(?<![a-z])\d+(?:\.\d+)?\s*({_UNITS_RE})\b", s)]
    if any(u in _VOLUME_UNITS for u in units):
        return "volume"
    if any(u in _MASS_UNITS for u in units):
        return "mass"
    return None


def _pack_count(s: str, unit: str) -> tuple[int | None, str]:
    """Number of selling units in a multipack title such as '200ml 6 unidades' or '2 pack'."""
    pats = [
        (rf"(?<![/\d])\b(\d{{1,2}})\s*(?:pack|pk|pck|pcks|paq|paquetes?|packs)\b", "pack"),
        (r"\b(?:pack|paquete|paq|pk)\s*(?:de\s*)?(\d{1,2})\b(?!\s*(?:" + _UNITS_RE + r")\b)", "pack"),
        (r"\b(six)\s*pack\b", "pack"),
    ]
    if unit in _VOLUME_UNITS or unit in {"oz", "onz", "onza", "onzas", "z"}:
        # Drinks list the size of one bottle and then the count; for solid food
        # "12 unidades" usually describes pieces inside the stated weight.
        pats.append((r"(?<![/\d.])\b(\d{1,2})\s*(?:unidades|unidad|unids|unid|unds|und|uds|un)\b", "units"))
    for pat, kind in pats:
        m = re.search(pat, s)
        if m:
            n = 6 if m.group(1) == "six" else int(m.group(1))
            if 2 <= n <= 48:
                return n, m.group(0)
    return None, ""


def _parse_quantity(name: str) -> tuple[float | None, float | None, str]:
    """(total kg, one selling unit kg, note) from a product name."""
    s, repair_note = repair_quantity_text(name)
    f = _UNIT_FACTORS

    def done(total, unit, note):
        if repair_note:
            note += f"; {repair_note}"
        return total, unit, note

    m = re.search(rf"\b({_NUM})\s*x\s*({_NUM})\s*({_UNITS_RE})\b", s)
    # "TOMATE 3X3 KILO" / "Jamon 4X4": a symmetric NxN is a grade or shape
    # code, not N packs of N kilos.
    if m and not (m.group(1) == m.group(2) and m.group(3) in ("kilo", "kilos", "lb", "libra")):
        count, amount, unit = float(m.group(1)), float(m.group(2)), m.group(3)
        return done(count * amount * f[unit], amount * f[unit], m.group(0))
    if m:
        s = s[:m.start()] + " " + s[m.start(3):]

    m = re.search(rf"\b({_NUM})\s*({_UNITS_RE})\s*x\s*(\d{{1,2}})\b(?!\s*(?:{_UNITS_RE})\b)", s)
    if m:
        amount, unit, count = float(m.group(1)), m.group(2), int(m.group(3))
        return done(count * amount * f[unit], amount * f[unit], m.group(0))

    # Fractions of a gallon/pound/kilo: "1/2 GL", "1/4GAL", "1 1/2 lb".
    frac_units = r"gal|gl|gln|galon|lb|lbs|libra|libras|kg|kilo|l|lt|litro"
    m = re.search(rf"\b(?:(\d)\s+)?([1-7])\s*/\s*([2-8])\s*({frac_units})\b", s)
    if m and int(m.group(2)) < int(m.group(3)):
        whole = float(m.group(1) or 0)
        amount = whole + int(m.group(2)) / int(m.group(3))
        kg = amount * f[m.group(4)]
        return done(kg, kg, f"fraction {m.group(0)}")

    # Retail titles often use 24/400ML to show case configuration while the
    # e-commerce price is for one selling unit. Preserve '/' so this is parsed
    # as 400ml, rather than accidentally repairing it to 24.4L.
    m = re.search(rf"\b\d+\s*/\s*({_NUM})\s*({_UNITS_RE})\b", s)
    if m:
        kg = float(m.group(1)) * f[m.group(2)]
        return done(kg, kg, f"unit size from slash-pack {m.group(0)}")

    m = re.search(rf"\b({_NUM})\s*({_UNITS_RE})\b", s)
    if m:
        amount, unit = float(m.group(1)), m.group(2)
        kg = amount * f[unit]
        count, pack_text = _pack_count(s, unit)
        if count:
            return done(kg * count, kg, f"{count} x {m.group(0)} (multipack '{pack_text}')")
        return done(kg, kg, m.group(0))

    # Deli items sold by weight: "Por Media Libra", "Por Libra".
    m = re.search(r"\b(media|1/2)\s*(libra|lb)\b", s)
    if m:
        kg = 0.5 * f["lb"]
        return kg, kg, f"implicit half pound from '{m.group(0)}'"
    m = re.search(r"\bpor\s+(libra|lb)\b", s)
    if m:
        return f["lb"], f["lb"], f"implicit 1 lb from '{m.group(0)}'"

    # Titles such as "SALAMI KILO" conventionally mean a 1kg selling unit.
    m = re.search(r"\b(kilo|kilogramo)\b", s)
    if m:
        return 1.0, 1.0, f"implicit 1kg from '{m.group(1)}'"

    return None, None, "no mass/volume in candidate name"


def parse_quantity_kg(name: str) -> Quantity:
    """Convert package mass/volume to comparable kg (project rule: 1L == 1kg)."""
    total, _, note = _parse_quantity(name)
    return Quantity(total, note)


def parse_count(name: str, allow_bare_number: bool = False) -> Quantity:
    """Number of pieces in a count-sold product ('50 unid', '4/50UN', 'De 50 Un').

    With allow_bare_number (retailer titles) a few looser forms are accepted:
    a trailing pack number, a bare 'Und' (one unit) and a single item that is
    described only by its weight/volume (one unit).
    """
    s = normalize_quantity_text(name)
    m = re.search(r"\b(\d+)\s*docenas?\b", s)
    if m and int(m.group(1)) > 0:
        n = int(m.group(1)) * 12
        return Quantity(float(n), f"{n} units ({m.group(0)})")
    if re.search(r"\bmedia\s+docena\b", s):
        return Quantity(6.0, "6 units (media docena)")
    m = re.search(rf"\b\d+\s*/\s*(\d+)\s*(?:{_COUNT_WORDS})\b", s)
    if m:
        return Quantity(float(m.group(1)), f"{m.group(1)} units (from {m.group(0)})")
    for m in re.finditer(rf"\b(\d+)\s*({_COUNT_WORDS})\b", s):
        n = int(m.group(1))
        # "Motas Nylon 300 Unidad" is one 300-size mop, not 300 mops.
        if n > 1 and m.group(2) in ("unidad", "pieza", "pza"):
            continue
        if n > 0:
            return Quantity(float(n), f"{n} units")
    if allow_bare_number:
        if re.search(r"\bdocena\b", s):
            return Quantity(12.0, "12 units (docena)")
        if re.search(r"\b(?:und|unidad|c/u)\b", s):
            return Quantity(1.0, "1 unit ('und')")
        # "Fiambreras 7x7 C/D Termo Foam 50": a trailing number after removing
        # dimensions is the pack count.
        t = re.sub(rf"\b{_NUM}\s*x\s*{_NUM}\b", " ", s).strip()
        m = re.search(r"\b(\d{2,4})$", t)
        if m:
            return Quantity(float(m.group(1)), f"{m.group(1)} units (trailing number)")
        if _parse_quantity(name)[0] is not None:
            return Quantity(1.0, "1 unit (single item sold by size)")
    return Quantity(None, "no unit count in name")


def _target_count(target_name: str) -> Quantity:
    """Pieces in a BAP product: '50 unid', '150und', or '20x25' (20 packs of 25)."""
    c = parse_count(target_name)
    if c.kg:
        return c
    s = normalize_quantity_text(identity_source_text(target_name))
    m = re.search(rf"\b(\d{{1,3}})\s*x\s*(\d{{2,4}})\b(?!\s*(?:{_UNITS_RE})\b)(?!\.\d)", s)
    if m:
        n = int(m.group(1)) * int(m.group(2))
        return Quantity(float(n), f"{n} units ({m.group(0)})")
    return Quantity(None, "no unit count in name")


def quantity_basis(target_name: str, target_context: dict | None = None) -> str:
    """'count' when a BAP product is defined by pieces, else 'mass'.

    A product is counted when its name gives a number of units and either no
    weight/volume, or it is a non-food item: for "Vasos Plásticos 9oz 150und"
    the 9 oz is the cup size, not what is being bought.
    """
    total, _, _ = _parse_quantity(target_name)
    count = _target_count(target_name).kg
    if not count:
        return "mass"
    if total is None:
        return "count"
    category = normalize((target_context or {}).get("category"))
    return "count" if category == "no alimento" else "mass"


def sold_by_weight_kg(attrs: dict[str, object] | None) -> Quantity | None:
    """Products the store sells by weight: the listed price is per kg (or per a
    fixed weight), whatever pack or log size the title or size field shows.

    Each store marks these differently:
      Super 99   sales_unit_of_measure = "Kilogramo"
      El Rey     unit = "kg"
      Super Xtra measurement unit = "kg", unit multiplier = kg per price
      Riba Smith size = "KG", or "0.58 KG" with a weighed (fractional) stock
    """
    if not attrs:
        return None
    if normalize(attrs.get("sales_unit_of_measure")) in ("kilogramo", "kilogramos", "kg"):
        return Quantity(1.0, "sold by weight (price per kg)")
    if normalize(attrs.get("unit")) == "kg" and normalize(attrs.get("sub unit") or "kg") == "kg":
        return Quantity(1.0, "sold by weight (price per kg)")
    if normalize(attrs.get("measurement unit")) == "kg":
        try:
            m = float(attrs.get("unit multiplier") or 1)
        except (TypeError, ValueError):
            m = 1.0
        if m > 0:
            return Quantity(m, f"sold by weight (price per {m:g} kg)")
    size = normalize(attrs.get("size"))
    if size == "kg":
        return Quantity(1.0, "sold by weight (price per kg)")
    if re.fullmatch(r"[\d.]+\s*kg", size) and re.search(r"\.\d*[1-9]", str(attrs.get("inventory") or "")):
        return Quantity(1.0, "sold by weight (price per kg; weighed stock)")
    return None


def parse_candidate_quantity(name: str, attrs: dict[str, object] | None = None, basis: str = "mass") -> Quantity:
    """Use title quantity first, then safe size/weight attributes when present."""
    if basis == "count":
        q = parse_count(name, allow_bare_number=True)
        if q.kg:
            return q
        for key, value in (attrs or {}).items():
            if value not in (None, "") and any(t in key for t in ("pack", "size", "count", "unidades")):
                aq = parse_count(str(value))
                if aq.kg:
                    return Quantity(aq.kg, f"attribute {key}: {value}")
        return Quantity(None, "cannot count units in candidate name")

    weighed = sold_by_weight_kg(attrs)
    if weighed:
        return weighed
    q = parse_quantity_kg(name)
    if q.kg is not None and q.kg > 0:
        return q
    if attrs:
        useful = ("peso", "weight", "contenido", "content", "tamano", "size", "capacidad", "volume", "volumen", "presentacion")
        for key, value in attrs.items():
            if value in (None, "") or not any(token in key for token in useful):
                continue
            aq = parse_quantity_kg(str(value))
            if aq.kg is not None and aq.kg > 0:
                return Quantity(aq.kg, f"attribute {key}: {value}")
    return q


def reference_unit_size_kg(name: str) -> Quantity:
    """Size used for similarity checks; a multipack uses ONE selling unit."""
    _, unit, note = _parse_quantity(name)
    return Quantity(unit, note)


def target_quantity_kg(product_name: str, spreadsheet_weight_kg=None, target_context: dict | None = None) -> Quantity:
    if quantity_basis(product_name, target_context) == "count":
        c = _target_count(product_name)
        return Quantity(c.kg, f"count basis: {c.source} (prices are per unit)")
    parsed = parse_quantity_kg(product_name)
    if parsed.kg is not None:
        return parsed
    try:
        value = float(spreadsheet_weight_kg)
        if value > 0:
            return Quantity(value, "Unidad de Peso en KG")
    except (TypeError, ValueError):
        pass
    return Quantity(None, "target quantity unavailable")


def target_quantity_warning(product_name: str, spreadsheet_weight_kg=None, target_context: dict | None = None) -> str:
    if quantity_basis(product_name, target_context) == "count":
        return ""
    parsed = parse_quantity_kg(product_name)
    try:
        sheet = float(spreadsheet_weight_kg)
    except (TypeError, ValueError):
        return ""
    if parsed.kg is None or sheet <= 0:
        return ""
    ratio = max(parsed.kg, sheet) / min(parsed.kg, sheet) if min(parsed.kg, sheet) > 0 else math.inf
    if ratio >= 1.15 and not _is_packaging_weight(parsed.kg, sheet):
        return f"TARGET SIZE WARNING: name parses to {parsed.kg:.3f}kg but spreadsheet weight is {sheet:.3f}kg"
    return ""


# The spreadsheet weight of a case is often the gross weight: product plus
# box and packaging ("Yogurt 24 x 125g" = 3.0 kg of yogurt, 3.5 kg in the sheet).
PACKAGING_WEIGHT_MAX_RATIO = 1.5


def _is_packaging_weight(name_kg: float, sheet_kg: float) -> bool:
    return name_kg > 0 and 1.0 < sheet_kg / name_kg <= PACKAGING_WEIGHT_MAX_RATIO


def target_quantity_note(product_name: str, spreadsheet_weight_kg=None, target_context: dict | None = None) -> str:
    """Informational note when the spreadsheet weight looks like the gross (packed) weight."""
    if quantity_basis(product_name, target_context) == "count":
        return ""
    parsed = parse_quantity_kg(product_name)
    try:
        sheet = float(spreadsheet_weight_kg)
    except (TypeError, ValueError):
        return ""
    if parsed.kg is None or sheet <= 0:
        return ""
    if sheet / parsed.kg >= 1.15 and _is_packaging_weight(parsed.kg, sheet):
        return (f"Spreadsheet weight {sheet:.3f}kg vs {parsed.kg:.3f}kg in the name "
                f"(probably includes packaging; the name is used)")
    return ""


def package_size_ratio(
    target_name: str,
    candidate_name: str,
    spreadsheet_weight_kg=None,
    candidate_attrs: dict[str, object] | None = None,
    target_context: dict | None = None,
):
    """Return (ratio, target_unit_kg, candidate_unit_kg) for size comparison."""
    if quantity_basis(target_name, target_context) == "count":
        target = _target_count(target_name)
        candidate = parse_candidate_quantity(candidate_name, candidate_attrs, basis="count")
    else:
        target = reference_unit_size_kg(target_name)
        candidate = reference_unit_size_kg(candidate_name)
        sold_by_weight = parse_candidate_quantity(candidate_name, candidate_attrs)
        if sold_by_weight.source.startswith("sold by weight"):
            candidate = sold_by_weight
        elif candidate.kg is None and candidate_attrs:
            candidate = parse_candidate_quantity(candidate_name, candidate_attrs)

        if target.kg is None:
            try:
                w = float(spreadsheet_weight_kg)
                if w > 0:
                    target = Quantity(w, "Unidad de Peso en KG")
            except (TypeError, ValueError):
                pass

    if target.kg is None or candidate.kg is None or target.kg <= 0 or candidate.kg <= 0:
        return None, target.kg, candidate.kg

    return candidate.kg / target.kg, target.kg, candidate.kg


def size_is_compatible(target_name: str, candidate_name: str, spreadsheet_weight_kg=None, candidate_attrs=None):
    """Legacy close-size check used for diagnostics; final selection is adaptive."""
    ratio, target_kg, candidate_kg = package_size_ratio(
        target_name, candidate_name, spreadsheet_weight_kg, candidate_attrs
    )
    if ratio is None:
        return False, "cannot safely compare package sizes"
    if ratio < MIN_SIZE_RATIO:
        return False, f"PACKAGE TOO SMALL: candidate={candidate_kg:.3f}kg, target unit={target_kg:.3f}kg, ratio={ratio:.2f}"
    if ratio > MAX_SIZE_RATIO:
        return False, f"PACKAGE TOO LARGE: candidate={candidate_kg:.3f}kg, target unit={target_kg:.3f}kg, ratio={ratio:.2f}"
    return True, f"compatible package size: candidate={candidate_kg:.3f}kg, target unit={target_kg:.3f}kg, ratio={ratio:.2f}"


def attributes_dict(entry: dict) -> dict[str, object]:
    attrs = entry.get("productView", {}).get("attributes") or []
    return {normalize(a.get("name", "")): a.get("value") for a in attrs}


# ---------------------------------------------------------------------------
# Identity matching
# ---------------------------------------------------------------------------

def _token_positions(name: str) -> list[str]:
    return semantic_tokens(name)


def _dimensions(text: str) -> tuple[int, int] | None:
    """Packaging dimensions such as 7x7 or 8" x 8" (not '12 x 170g')."""
    s = normalize_quantity_text(text)
    m = re.search(rf"\b(\d{{1,2}})\s*x\s*(\d{{1,2}})\b(?!\s*(?:{_UNITS_RE})\b)(?!\.\d)", s)
    if not m:
        return None
    return tuple(sorted((int(m.group(1)), int(m.group(2)))))


class _CandidateView:
    """Candidate title words with their positions and implied words."""

    def __init__(self, candidate_name: str, family: str | None):
        self.words = normalize(candidate_name).split()
        self.first_pos: dict[str, int] = {}
        for i, raw in enumerate(self.words):
            if len(raw) <= 1 or raw in SEARCH_STOPWORDS or re.fullmatch(r"[\d.]+", raw):
                continue
            t = canonical_word(raw)
            self.first_pos.setdefault(t, i)
        self.ordered = semantic_tokens(candidate_name)
        tokens = set(self.first_pos) | set(self.ordered)
        implied: dict[str, int] = {}
        for t in list(tokens):
            implies, needs = CANDIDATE_IMPLIES.get(t, (set(), None))
            if implies and (needs is None or tokens & needs):
                for x in implies:
                    implied.setdefault(x, self.first_pos.get(t, 0))
        raw_set = set(self.words)
        if family in FLAVORABLE_FAMILIES and (tokens & FLAVOR_WORDS or raw_set & {"sabor", "sabores", "saborizada", "saborizado", "saborizadas"}):
            implied.setdefault("saborizado", self.first_pos.get(family, 0))
        if tokens & FRUIT_WORDS and "concentrado" in tokens:
            implied.setdefault("jugo", self.first_pos.get("concentrado", 0))
        for x, pos in implied.items():
            self.first_pos.setdefault(x, pos)
        self.tokens = tokens | set(implied)

    def position(self, token: str) -> int | None:
        return self.first_pos.get(token)


def _target_is_food(target_tokens: set[str], target_context: dict | None) -> bool:
    category = normalize((target_context or {}).get("category"))
    if category:
        return category != "no alimento"
    return not (target_tokens & NON_FOOD_WORDS)


def candidate_matches(
    target_name: str,
    candidate_name: str,
    attrs: dict[str, object],
    target_context: dict | None = None,
) -> tuple[bool, str]:
    req = required_identity_tokens(target_name, target_context)
    target_all = set(semantic_tokens(target_name)) | context_modifier_tokens(target_name, target_context)
    for t in list(target_all):
        target_all |= TARGET_ALLOWS.get(t, set())
    head = req[0] if req else None
    view = _CandidateView(candidate_name, head)
    cand_ordered = view.ordered
    cand = view.tokens

    if not req or not cand_ordered:
        return False, "missing usable identity tokens"

    variety = is_variety_target(target_name)
    effective = _effective_required(req)
    missing = set(effective) - cand

    # A generic family can be represented by one of its concrete members.
    family_members = GENERIC_FAMILY_MEMBERS.get(head, set())
    if head in missing and family_members and (cand & family_members):
        missing.remove(head)

    if missing:
        return False, "missing required identity word(s): " + ", ".join(sorted(missing))

    # Products that can never be the answer.
    if _target_is_food(target_all, target_context):
        bad = (cand & NON_FOOD_WORDS) - target_all
        if bad:
            return False, "non-food product for a food target: " + ", ".join(sorted(bad))
    bad = (cand & PET_WORDS) - target_all
    if bad:
        return False, "pet product: " + ", ".join(sorted(bad))
    bad = (cand & ALCOHOL_WORDS) - target_all
    if bad and set(view.words) & {"sin", "zero", "cero", "free", "libre", "0"}:
        bad -= {"alcohol", "alcoholica", "alcoholico"}      # "Zero Alcohol" / "sin alcohol"
    if bad and "vinagre" not in target_all:
        return False, "alcoholic product: " + ", ".join(sorted(bad))
    bad = (cand & DERIVED_PRODUCT_WORDS) - target_all
    if bad and not variety:
        return False, "preparation/mix, not the product itself: " + ", ".join(sorted(bad))
    bad = (cand & _canon_set(SPECIALITY_WORDS)) - target_all
    if bad:
        return False, "speciality/premium version of the product: " + ", ".join(sorted(bad))
    bad = (cand & _canon_set(PREPARED_WORDS)) - target_all
    if bad:
        return False, "breaded/prepared version of the product: " + ", ".join(sorted(bad))

    if normalize((target_context or {}).get("line")) in RAW_MEAT_LINES:
        bad = (cand & _canon_set(DELI_WORDS)) - target_all
        if bad:
            return False, "cooked/deli/seasoned version of a raw meat product: " + ", ".join(sorted(bad))

    # "Masa para pan": a title led by the purpose word ("Pan de masa madre")
    # is that other product.
    t_words = normalize(identity_source_text(target_name)).split()
    purpose = set()
    for i, w in enumerate(t_words):
        if w in ("para", "con") and i + 1 < len(t_words):
            purpose.add(canonical_word(t_words[i + 1]))
    # Bakery items named "<item> de <filling>" (Rollos de queso, Pan de yuca):
    # a title that leads with the filling is that other product (goat cheese).
    if normalize((target_context or {}).get("family")) in BAKERY_FAMILIES:
        for i, w in enumerate(t_words):
            if w == "de" and i >= 1 and i + 1 < len(t_words):
                purpose.add(canonical_word(t_words[i + 1]))
    purpose &= set(effective)
    if purpose and view.ordered and view.ordered[0] in purpose and head not in purpose:
        return False, f"title is a '{view.ordered[0]}' product, the target is only for/with it"

    # The main product named by the title must be the target: reject titles in
    # which every target word only appears after "con/anti/sabor/para/en ..."
    # or after a different product noun ("Salsa ... Hongos").
    positions = []
    for t in effective:
        p = view.position(t)
        if p is None and t == head and family_members:
            ps = [view.position(x) for x in family_members if view.position(x) is not None]
            p = min(ps) if ps else None
        if p is not None:
            positions.append(p)
    if positions:
        first = min(positions)
        lead = view.words[1:first]
        marker = next((w for w in lead if w in SUBORDINATE_MARKERS), None)
        if marker:
            return False, f"target word only appears after '{marker}' (ingredient/flavour, not the product)"
        allowed_nouns = set(effective) | target_all | family_members
        for w in view.words[:first]:
            cw = canonical_word(w)
            if cw in PRODUCT_NOUNS and cw not in allowed_nouns:
                return False, f"different product: title leads with '{cw}'"

    # One-word targets: "Croquetas de Pescado", "Pasta de Tomate", "Harina de
    # Maíz" are products MADE FROM the target, not the target itself.
    if len(effective) == 1 and not family_members:
        p = view.position(effective[0])
        if p is not None and p >= 2 and view.words[p - 1] in ("de", "del"):
            before = [w for w in view.words[:p - 1] if canonical_word(w) in view.first_pos]
            if before:
                return False, f"made from/with '{effective[0]}', not the product itself"

    # Fresh produce must not be matched with canned or processed goods.
    family_ctx = normalize((target_context or {}).get("family"))
    if family_ctx in FRESH_FAMILIES:
        processed = ((cand | set(view.words)) & _canon_set(PROCESSED_WORDS)) - target_all
        if processed:
            return False, "processed/canned product for a fresh-produce target: " + ", ".join(sorted(processed))

    # A canned target ("Tomate en lata") must not take fresh produce sold by weight.
    target_words = set(normalize(identity_source_text(target_name)).split())
    canned_words = {"lata", "latas", "enlatado", "enlatada", "enlatados", "enlatadas", "conserva"}
    if target_words & canned_words and not (set(view.words) & canned_words):
        fresh = set(view.words) & {"granel", "fresco", "fresca", "frescos", "frescas", "kilo", "empacado", "empacada", "empacados", "empacadas"}
        if fresh:
            return False, "fresh product for a canned target: " + ", ".join(sorted(fresh))

    # Explicit subtype conflicts among strong identity modifiers.
    for group in MODIFIER_GROUPS:
        group = _canon_set(group)
        target_group = target_all & group
        candidate_group = cand & group
        if target_group and candidate_group and not (target_group & candidate_group):
            return False, f"conflicting subtype: target={sorted(target_group)}, candidate={sorted(candidate_group)}"

    # Optional storage/form words need not be stated by a candidate, but an
    # explicit contradictory form should still be rejected.
    form_group = _canon_set(FORM_CONFLICT_GROUP)
    target_form = target_all & form_group
    candidate_form = cand & form_group
    if target_form and candidate_form and not (target_form & candidate_form):
        return False, f"conflicting product form: target={sorted(target_form)}, candidate={sorted(candidate_form)}"

    forbidden = FAMILY_FORBIDDEN.get(head, set())
    bad = cand & forbidden
    if bad:
        return False, "false-positive family term(s): " + ", ".join(sorted(bad))

    subtype_forbidden = _canon_set(FAMILY_UNSPECIFIED_FORBIDDEN.get(head, set()))
    if variety:
        subtype_forbidden -= {"saborizado", "saborizada"}
    unexpected_subtypes = (cand & subtype_forbidden) - target_all
    if unexpected_subtypes:
        return False, f"unexpected subtype for plain '{head}': " + ", ".join(sorted(unexpected_subtypes))

    generic_bad = (cand & GENERIC_FAMILY_FORBIDDEN.get(head, set())) - target_all
    if generic_bad:
        return False, "generic-family false positive term(s): " + ", ".join(sorted(generic_bad))

    # A target that names a flavour must not take a title with other flavours
    # ("Jugo de limón" vs "Jugo Piña y Limón").
    target_flavors = target_all & FLAVOR_WORDS
    if target_flavors and not variety:
        extra = (cand & FLAVOR_WORDS) - target_flavors
        if extra:
            return False, "different/extra flavour(s): " + ", ".join(sorted(extra))

    # Counted products that also state a size (cups "9oz 150und") must be of a
    # similar size: a 30 oz tumbler is not a 9 oz disposable cup.
    if quantity_basis(target_name, target_context) == "count":
        tq, cq = _parse_quantity(target_name)[1], _parse_quantity(candidate_name)[1]
        if tq and cq and not (0.5 <= cq / tq <= 2.0):
            return False, f"different item size: target {tq:.3f}, candidate {cq:.3f} (kg/L)"

    # Packaging dimensions (7x7 vs 8x8 food containers) must agree.
    td = _dimensions(target_name)
    if td:
        cd = _dimensions(candidate_name)
        if cd and cd != td:
            return False, f"different dimensions: target {td[0]}x{td[1]}, candidate {cd[0]}x{cd[1]}"

    # A liquid target written explicitly in ml/L should not match a gram/kg
    # product such as powdered milk. This is an identity safeguard, not a
    # density conversion rule; BAP's 1L=1kg rule still applies after identity.
    if head in LIQUID_FAMILIES:
        tk = quantity_kind(target_name)
        ck = quantity_kind(candidate_name)
        if tk == "volume" and ck == "mass" and "polvo" not in target_all:
            return False, "physical-form mismatch: liquid target vs mass-labelled candidate"

    if head in SOLID_MASS_FAMILIES:
        tk = quantity_kind(target_name)
        ck = quantity_kind(candidate_name)
        if tk == "mass" and ck == "volume":
            return False, "physical-form mismatch: dry/mass target vs volume-labelled candidate"

    if len(req) == 1 and head in GENERIC_QUERY_WORDS and not family_members:
        try:
            pos = cand_ordered.index(head)
        except ValueError:
            return False, f"missing core product word '{head}'"
        if pos > MAX_GENERIC_HEAD_POSITION:
            return False, f"generic product word '{head}' appears too late in candidate title (position {pos})"

    return True, "accepted by identity/subtype rules"


def candidate_price(entry: dict) -> PriceChoice:
    try:
        minimum = entry["product"]["price_range"]["minimum_price"]
    except Exception:
        return PriceChoice(None, None, None, "", PRICE_BASIS, None)

    def read_price(key):
        try:
            p = minimum[key]
            return float(p["value"]), str(p.get("currency", "USD"))
        except Exception:
            return None, ""

    regular, c1 = read_price("regular_price")
    final, c2 = read_price("final_price")
    currency = c2 or c1

    discount_percent = None
    try:
        d = minimum.get("discount") or {}
        if d.get("percent_off") is not None:
            discount_percent = float(d["percent_off"])
    except Exception:
        pass

    if PRICE_BASIS == "regular":
        chosen = regular if regular is not None else final
        basis = "regular" if regular is not None else "final fallback"
    elif PRICE_BASIS == "final":
        chosen = final if final is not None else regular
        basis = "final" if final is not None else "regular fallback"
    else:
        raise ValueError('PRICE_BASIS must be "regular" or "final"')

    return PriceChoice(chosen, regular, final, currency, basis, discount_percent)


def choose_price(regular: float | None, final: float | None) -> tuple[float | None, str]:
    """Pick the regular or final price according to the current PRICE_BASIS."""
    if PRICE_BASIS == "final":
        if final is not None:
            return final, "final"
        return regular, "regular fallback"
    if regular is not None:
        return regular, "regular"
    return final, "final fallback"


def candidate_fingerprint(name: str, unit_kg: float | None) -> tuple[tuple[str, ...], float | None]:
    toks = tuple(sorted(set(semantic_tokens(name))))
    size = round(unit_kg, 3) if unit_kg is not None else None
    return toks, size


def token_jaccard(a: str, b: str) -> float:
    sa, sb = set(semantic_tokens(a)), set(semantic_tokens(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def relative_difference(a: float | None, b: float | None) -> float:
    if a is None or b is None or max(abs(a), abs(b)) == 0:
        return math.inf
    return abs(a - b) / max(abs(a), abs(b))


def are_near_duplicates(a: dict, b: dict) -> bool:
    if a["sku"] == b["sku"] and a.get("store") == b.get("store"):
        return True
    if a.get("kg") is None or b.get("kg") is None:
        return False
    if relative_difference(a["kg"], b["kg"]) > DUPLICATE_SIZE_TOLERANCE:
        return False
    if relative_difference(a.get("price_per_kg"), b.get("price_per_kg")) > DUPLICATE_PRICE_TOLERANCE:
        return False
    if candidate_fingerprint(a["name"], a["kg"]) == candidate_fingerprint(b["name"], b["kg"]):
        return True
    return token_jaccard(a["name"], b["name"]) >= DUPLICATE_TOKEN_JACCARD


def remove_near_duplicates(accepted: list[dict]) -> tuple[list[dict], list[dict]]:
    kept: list[dict] = []
    removed: list[dict] = []
    for item in sorted(accepted, key=lambda x: (x.get("price_per_kg") is None, x.get("sku", ""))):
        duplicate_of = next((k for k in kept if are_near_duplicates(item, k)), None)
        if duplicate_of is None:
            kept.append(item)
        else:
            item["accepted"] = False
            item["reason"] = (
                f"NEAR-DUPLICATE REMOVED: overlaps SKU {duplicate_of['sku']} "
                f"({duplicate_of['name']})"
            )
            removed.append(item)
    return kept, removed


def _closest_per_store(items: list[dict]) -> list[dict]:
    """Keep the MAX_FALLBACK_SIZE_MATCHES listings closest in size, per store."""
    items = sorted(items, key=lambda x: abs(math.log(x["size_ratio"])))
    kept, per_store = [], {}
    for x in items:
        store = x.get("store")
        if per_store.get(store, 0) < MAX_FALLBACK_SIZE_MATCHES:
            per_store[store] = per_store.get(store, 0) + 1
            kept.append(x)
    return kept


def filter_preferred_size_matches(accepted: list[dict]) -> tuple[list[dict], list[dict], str]:
    """Choose a coherent package-size peer group without killing bulk targets.

    Keeps the small-package protection while allowing bulk BAP targets to use
    the closest retail-size cluster when no supermarket pack is close to the
    BAP size. The robot applies this to the matches of ALL stores together, so
    every store is compared on the same package sizes.
    """
    neutral = []
    sized = [x for x in accepted if x.get("size_ratio") is not None and x["size_ratio"] > 0]
    if not sized:
        return accepted, [], "NO SIZE DATA"

    preferred = [x for x in sized if PREFERRED_SIZE_RATIO_MIN <= x["size_ratio"] <= PREFERRED_SIZE_RATIO_MAX]
    close = [x for x in sized if MIN_SIZE_RATIO <= x["size_ratio"] <= MAX_SIZE_RATIO]
    if len(preferred) >= MIN_PREFERRED_SIZE_MATCHES and (
        len(preferred) >= MIN_GOOD_MATCHES or len(close) <= len(preferred)
    ):
        keep_ids = {id(x) for x in preferred}
        strategy = f"PREFERRED {PREFERRED_SIZE_RATIO_MIN:.2f}-{PREFERRED_SIZE_RATIO_MAX:.2f}x"
    else:
        # Too few near-exact sizes: widen to the close range when it adds matches.
        if len(close) >= 2:
            keep_ids = {id(x) for x in close}
            strategy = f"CLOSE {MIN_SIZE_RATIO:.2f}-{MAX_SIZE_RATIO:.2f}x"
        else:
            # Zero or one close package (typically a bulk BAP size). Use the
            # retail size cluster nearest to the target that still holds a
            # reliable sample: prefer clusters with enough listings from 2+
            # stores, then enough listings, then the nearest size. A single
            # unusually large pack (e.g. one 3kg deli log for a 17kg box) must
            # not set the price alone.
            # Bulk target: products sold by weight can be bought in any
            # quantity, so they join the chosen group instead of choosing it.
            packaged = [x for x in sized if not x.get("size_neutral")]
            if packaged:
                neutral = [x for x in sized if x.get("size_neutral")]
                sized = packaged
            all_stores = {x.get("store") for x in sized}
            need_n = max(1, MIN_PREFERRED_SIZE_MATCHES)

            def cluster_key(item):
                a = item["size_ratio"]
                members = [x for x in sized if 1 / SIZE_CLUSTER_FACTOR <= x["size_ratio"] / a <= SIZE_CLUSTER_FACTOR]
                stores = {x.get("store") for x in members}
                multi = len(stores) >= min(2, len(all_stores))
                tier = 0
                if len(members) >= max(need_n, MIN_GOOD_MATCHES) and multi:
                    tier = 3
                elif len(members) >= need_n:
                    tier = 2 if multi else 1
                return (tier, -abs(math.log(a)))
            anchor_item = max(sized, key=cluster_key)
            anchor = anchor_item["size_ratio"]
            cluster = [
                x for x in sized
                if 1 / SIZE_CLUSTER_FACTOR <= x["size_ratio"] / anchor <= SIZE_CLUSTER_FACTOR
            ]
            cluster = _closest_per_store(cluster)
            keep_ids = {id(x) for x in cluster}
            strategy = f"FALLBACK NEAREST RETAIL SIZE around {anchor:.2f}x"

    kept, removed = [], []
    neutral_ids = {id(x) for x in neutral}
    for item in accepted:
        if id(item) in neutral_ids:
            continue
        if item.get("size_ratio") is None:
            # Quantity was usable for $/kg but unit-size comparison was not.
            # Keep it only when there are no sized peers at all (handled above).
            item["accepted"] = False
            item["reason"] = "SIZE PEER REMOVED: unit-size ratio unavailable while sized peers exist"
            removed.append(item)
        elif id(item) in keep_ids:
            item["reason"] = f"accepted; size strategy={strategy}; ratio={item['size_ratio']:.2f}"
            kept.append(item)
        else:
            item["accepted"] = False
            item["reason"] = f"SIZE-DISTANT MATCH REMOVED: ratio={item['size_ratio']:.2f}; strategy={strategy}"
            removed.append(item)
    # Products sold by weight can be bought in any quantity: keep them with
    # whichever package-size group was chosen.
    for item in neutral:
        item["reason"] = f"accepted; sold by weight (any quantity); size strategy={strategy}"
    return kept + neutral, removed, strategy


def remove_price_outliers(accepted: list[dict]) -> tuple[list[dict], list[dict]]:
    valid = [x for x in accepted if x.get("price_per_kg") is not None and x["price_per_kg"] > 0]
    if len(valid) < 3:
        return accepted, []

    prices = [x["price_per_kg"] for x in valid]
    med = median(prices)
    hard_low = med * HARD_OUTLIER_LOW_RATIO
    hard_high = med * HARD_OUTLIER_HIGH_RATIO

    log_med = None
    log_mad = None
    if len(prices) >= 5:
        logs = [math.log(p) for p in prices]
        log_med = median(logs)
        # Floor the spread at ~5% so a group of identical prices does not
        # turn a normal 20% difference into an "outlier".
        log_mad = max(median(abs(x - log_med) for x in logs), 0.05)

    kept, removed = [], []
    for item in accepted:
        p = item.get("price_per_kg")
        reason = None
        if p is not None and p > 0:
            if p < hard_low or p > hard_high:
                reason = (
                    f"PRICE OUTLIER REMOVED: ${p:.2f}/kg vs median ${med:.2f}/kg "
                    f"(hard band ${hard_low:.2f}-${hard_high:.2f})"
                )
            elif log_med is not None and log_mad and log_mad > 1e-12:
                z = 0.6745 * abs(math.log(p) - log_med) / log_mad
                if z > LOG_MAD_Z_THRESHOLD:
                    reason = (
                        f"ROBUST PRICE OUTLIER REMOVED: ${p:.2f}/kg vs median ${med:.2f}/kg "
                        f"(log-MAD z={z:.2f})"
                    )
        if reason:
            item["accepted"] = False
            item["reason"] = reason
            removed.append(item)
        else:
            kept.append(item)
    return kept, removed


def percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolated percentile (q between 0 and 1)."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * min(max(q, 0.0), 1.0)
    lo, hi = math.floor(k), math.ceil(k)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def price_level_value(values: list[float], level: str | None = None, economy_percentile: float | None = None) -> float | None:
    """One price per kg from a group of prices, for the chosen market price level."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    level = (level or MARKET_PRICE_LEVEL or "average").lower()
    if level == "median":
        return median(vals)
    if level == "economy":
        return percentile(vals, ECONOMY_PERCENTILE if economy_percentile is None else economy_percentile)
    return mean(vals)


def spread_ratio(values: list[float]) -> float:
    """Price spread used for the variation warning.

    With few prices this is max/min. With 5 or more it is the ratio between the
    10th and 90th percentiles, so one cheap store brand and one premium import
    in an otherwise tight group do not trigger the warning on their own (the
    CV test still catches a genuinely wide spread).
    """
    vals = sorted(v for v in values if v is not None and v > 0)
    if not vals:
        return 0.0
    if len(vals) < 5:
        return vals[-1] / vals[0]

    def pct(q):
        k = (len(vals) - 1) * q
        lo, hi = math.floor(k), math.ceil(k)
        return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)

    return pct(0.90) / pct(0.10)


def quality_summary(
    accepted: list[dict],
    query_confidence: str,
    duplicate_count: int,
    outlier_count: int,
    size_distant_count: int = 0,
):
    vals = [x["price_per_kg"] for x in accepted if x.get("price_per_kg") is not None]
    flags = []

    n = len(vals)
    if n == 0:
        flags.append("NO MATCHES")
    elif n <= 2:
        flags.append(f"VERY HIGH RISK: only {n} independent clean match(es); need {MIN_GOOD_MATCHES}")
    elif n < MIN_GOOD_MATCHES:
        flags.append(f"HIGH RISK: only {n} independent clean match(es); need {MIN_GOOD_MATCHES}")

    if query_confidence == "LOW":
        flags.append("LOW SEARCH CONFIDENCE")

    if size_distant_count:
        flags.append(f"{size_distant_count} size-distant listing(s) removed")
    if duplicate_count:
        flags.append(f"{duplicate_count} near-duplicate listing(s) removed")
    if outlier_count:
        flags.append(f"{outlier_count} price outlier(s) removed")

    if not vals:
        return None, None, None, None, " | ".join(flags)

    avg = mean(vals)
    med = median(vals)
    ratio = max(vals) / min(vals) if min(vals) > 0 else math.inf
    cv = pstdev(vals) / avg if len(vals) > 1 and avg else 0.0

    if spread_ratio(vals) >= PRICE_RATIO_WARNING or cv >= PRICE_CV_WARNING:
        flags.append(f"PRICE VARIATION WARNING: ratio={ratio:.2f}, CV={cv:.1%}")

    return avg, med, ratio, cv, " | ".join(flags) if flags else "OK"
