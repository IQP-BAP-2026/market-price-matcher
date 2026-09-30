from .super99 import Super99Parser
from .superxtra import SuperXtraParser
from .rey import ReyParser
from .ribasmith import RibaSmithParser

PARSER_REGISTRY = {
    "super99": Super99Parser,
    "superxtra": SuperXtraParser,
    "rey": ReyParser,
    "ribasmith": RibaSmithParser,
}

STORE_ALIASES = {
    "elrey": "rey",
    "smrey": "rey",
    "riba": "ribasmith",
    "riba-smith": "ribasmith",
    "riba_smith": "ribasmith",
    "xtra": "superxtra",
    "99": "super99",
}


def canonical_store_id(value: str) -> str:
    key = str(value).strip().lower()
    return STORE_ALIASES.get(key, key)


def available_stores():
    return sorted(PARSER_REGISTRY)
