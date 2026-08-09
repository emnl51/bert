import html
import re
import unicodedata


_TAG_RE = re.compile(r"<[^>]+>")


def normalize_text(value: str) -> str:
    """Return comparable vacancy/CV text without HTML or Unicode surprises."""
    decoded = html.unescape(str(value or ""))
    without_tags = _TAG_RE.sub(" ", decoded)
    normalized = unicodedata.normalize("NFKC", without_tags).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def phrase_pattern(phrase: str) -> re.Pattern[str] | None:
    """Compile a phrase matcher with boundaries for word-like edges.

    Plain substring checks make short skills such as SAP match words like
    ``sapphire``. Internal whitespace is intentionally flexible so copied HTML
    and line-wrapped vacancy text still match multi-word terms.
    """
    normalized = normalize_text(phrase)
    if not normalized:
        return None
    parts = [re.escape(part) for part in normalized.split()]
    body = r"\s+".join(parts)
    left = r"(?<!\w)" if normalized[0].isalnum() else ""
    right = r"(?!\w)" if normalized[-1].isalnum() else ""
    return re.compile(left + body + right, re.IGNORECASE)


def find_phrase(text: str, phrase: str) -> re.Match[str] | None:
    pattern = phrase_pattern(phrase)
    return pattern.search(normalize_text(text)) if pattern else None


def contains_phrase(text: str, phrase: str) -> bool:
    return find_phrase(text, phrase) is not None


_NEGATION_RE = re.compile(
    r"(?:^|\s)(?:no|not|without|lack(?:ing)?(?:\s+of)?|kein(?:e|en|er|es)?|ohne)"
    r"(?:\s+\w+){0,3}\s*$",
    re.IGNORECASE,
)
_POST_NEGATION_RE = re.compile(
    r"^(?:\s+\w+){0,2}\s+(?:not\s+(?:required|necessary|needed)|nicht\s+erforderlich)",
    re.IGNORECASE,
)


def contains_affirmed_phrase(text: str, phrase: str) -> bool:
    """Return true when at least one occurrence is not locally negated."""
    normalized = normalize_text(text)
    pattern = phrase_pattern(phrase)
    if not pattern:
        return False
    for match in pattern.finditer(normalized):
        prefix = normalized[max(0, match.start() - 42) : match.start()]
        suffix = normalized[match.end() : match.end() + 42]
        if not _NEGATION_RE.search(prefix) and not _POST_NEGATION_RE.search(suffix):
            return True
    return False


def first_phrase(text: str, phrases) -> str | None:
    for phrase in phrases:
        if contains_phrase(text, str(phrase)):
            return str(phrase)
    return None
