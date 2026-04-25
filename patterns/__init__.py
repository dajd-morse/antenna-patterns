from .s1528 import S1528Pattern
from .s672 import S672Pattern
from .s580 import S580Pattern
from .s465 import S465Pattern

PATTERN_REGISTRY: list = [
    S1528Pattern(),
    S672Pattern(),
    S580Pattern(),
    S465Pattern(),
]

PATTERN_BY_NAME: dict = {p.name: p for p in PATTERN_REGISTRY}
