from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Job:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    created_at: str = ""
    remote: bool = False
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    language_score: int = 55
    overall_score: int = 0
    role_relevant: bool = True
    match_tier: str = "match"
    language_label: str = "unclear"
    language_reasons: list[str] = field(default_factory=list)
    discovered_queries: list[str] = field(default_factory=list)
    source_options: list[dict[str, str]] = field(default_factory=list)
    semantic_score: int | None = None

    @property
    def key(self) -> str:
        return f"{self.source}:{self.external_id}"

    @property
    def seen_at(self) -> str:
        return datetime.now(timezone.utc).isoformat()
