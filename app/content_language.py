import re
from dataclasses import dataclass


GERMAN_WORDS = {
    "aber",
    "als",
    "auch",
    "auf",
    "aus",
    "bei",
    "bereich",
    "bewerbung",
    "bieten",
    "das",
    "deine",
    "deutsch",
    "dich",
    "die",
    "du",
    "eine",
    "einem",
    "einen",
    "einer",
    "erfahrung",
    "für",
    "ihre",
    "kenntnisse",
    "mit",
    "oder",
    "sind",
    "sie",
    "und",
    "unser",
    "von",
    "wir",
    "werden",
    "zu",
}
ENGLISH_WORDS = {
    "and",
    "are",
    "as",
    "at",
    "be",
    "business",
    "candidate",
    "company",
    "experience",
    "for",
    "from",
    "in",
    "is",
    "job",
    "knowledge",
    "of",
    "or",
    "our",
    "responsibilities",
    "skills",
    "team",
    "the",
    "this",
    "to",
    "we",
    "with",
    "you",
    "your",
}


@dataclass(frozen=True)
class ContentLanguage:
    code: str
    confidence: float


def detect_content_language(title: str, description: str) -> ContentLanguage:
    """Detect the dominant German/English language without external services.

    Description evidence counts four times as much as title evidence. Mixed and
    unknown keep low-confidence or genuinely bilingual ads from being mislabeled.
    """
    title_tokens = _tokens(title)
    description_tokens = _tokens(description)
    if len(title_tokens) + len(description_tokens) < 8:
        return ContentLanguage("unknown", 0.0)

    de = 0.2 * _score(title_tokens, GERMAN_WORDS) + 0.8 * _score(description_tokens, GERMAN_WORDS)
    en = 0.2 * _score(title_tokens, ENGLISH_WORDS) + 0.8 * _score(description_tokens, ENGLISH_WORDS)
    total = de + en
    if total < 2.0:
        return ContentLanguage("unknown", min(0.49, total / 4))

    de_share = de / total
    en_share = en / total
    confidence = round(max(de_share, en_share), 3)
    if de >= 2 and en >= 2 and max(de_share, en_share) < 0.7:
        return ContentLanguage("mixed", confidence)
    if de_share >= 0.7:
        return ContentLanguage("de", confidence)
    if en_share >= 0.7:
        return ContentLanguage("en", confidence)
    return ContentLanguage("mixed", confidence)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zäöüß]+", (text or "").lower())


def _score(tokens: list[str], markers: set[str]) -> int:
    return sum(token in markers for token in tokens)
