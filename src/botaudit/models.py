"""Data models for botaudit analysis results and grading."""

from dataclasses import dataclass, field
from enum import Enum


GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
    (0, "F"),
]

CATEGORY_WEIGHTS: dict[str, float] = {
    "Content Availability": 0.27,
    "Semantic HTML": 0.23,
    "Link Discoverability": 0.18,
    "Structured Data": 0.13,
    "Metadata & Discoverability": 0.09,
    "LLM Discoverability": 0.10,
}

# SPEC-custom-weights FR-1.3: case-insensitive aliases for category names.
CATEGORY_ALIASES: dict[str, str] = {
    "content": "Content Availability",
    "content-availability": "Content Availability",
    "semantic": "Semantic HTML",
    "semantic-html": "Semantic HTML",
    "links": "Link Discoverability",
    "link-discoverability": "Link Discoverability",
    "structured": "Structured Data",
    "structured-data": "Structured Data",
    "llm": "LLM Discoverability",
    "llm-discoverability": "LLM Discoverability",
    "metadata": "Metadata & Discoverability",
    "meta": "Metadata & Discoverability",
}

# SPEC-custom-weights FR-2.2: built-in weight profiles.
PROFILE_ECOMMERCE: dict[str, float] = {
    "Content Availability": 0.20,
    "Semantic HTML": 0.15,
    "Link Discoverability": 0.15,
    "Structured Data": 0.25,
    "Metadata & Discoverability": 0.15,
    "LLM Discoverability": 0.10,
}

PROFILE_DOCS: dict[str, float] = {
    "Content Availability": 0.30,
    "Semantic HTML": 0.25,
    "Link Discoverability": 0.25,
    "Structured Data": 0.05,
    "Metadata & Discoverability": 0.05,
    "LLM Discoverability": 0.10,
}

PROFILE_AI_READY: dict[str, float] = {
    "Content Availability": 0.20,
    "Semantic HTML": 0.15,
    "Link Discoverability": 0.10,
    "Structured Data": 0.20,
    "Metadata & Discoverability": 0.10,
    "LLM Discoverability": 0.25,
}

# NFR-3.4: registry — add a new profile by adding a dict + one entry here.
WEIGHT_PROFILES: dict[str, tuple[str, dict[str, float]]] = {
    "default": ("Standard weights", CATEGORY_WEIGHTS),
    "ecommerce": ("Emphasizes structured data and metadata for product pages", PROFILE_ECOMMERCE),
    "docs": ("Prioritizes content and navigation for documentation sites", PROFILE_DOCS),
    "ai-ready": ("Maximizes AI/LLM accessibility signals", PROFILE_AI_READY),
}

RECOMMENDATION_THRESHOLD = 90


def resolve_weights(
    *,
    profile: str | None = None,
    overrides: list[str] | None = None,
) -> dict[str, float]:
    """Resolve final category weights from profile and/or CLI overrides.

    SPEC-custom-weights NFR-3.3 / NFR-4.1.

    1. Start from *profile* weights (or CATEGORY_WEIGHTS if None).
    2. Apply each *overrides* entry (``"CATEGORY=VALUE"`` strings) on top.
    3. Validate: all non-negative, at least one > 0.
    4. Return the resolved (un-normalized) weight dict.

    Raises ValueError on unrecognized category/profile or invalid value.
    """
    # 1. Start from profile or defaults
    if profile is not None:
        key = profile.lower()
        if key not in WEIGHT_PROFILES:
            names = ", ".join(sorted(WEIGHT_PROFILES))
            raise ValueError(
                f"Unknown weight profile '{profile}'. "
                f"Available profiles: {names}"
            )
        weights = dict(WEIGHT_PROFILES[key][1])
    else:
        weights = dict(CATEGORY_WEIGHTS)

    # 2. Apply overrides
    if overrides:
        # Build case-insensitive lookup: canonical names + aliases
        lookup: dict[str, str] = {k.lower(): k for k in CATEGORY_WEIGHTS}
        for alias, canonical in CATEGORY_ALIASES.items():
            lookup[alias.lower()] = canonical

        seen: set[str] = set()
        for entry in overrides:
            if "=" not in entry:
                raise ValueError(
                    f"Invalid --weight format '{entry}'. "
                    f"Expected CATEGORY=VALUE (e.g. 'Structured Data=0.30')"
                )
            name_raw, value_raw = entry.split("=", 1)
            name_key = name_raw.strip().lower()

            if name_key not in lookup:
                valid = ", ".join(sorted(CATEGORY_WEIGHTS))
                raise ValueError(
                    f"Unknown category '{name_raw.strip()}'. "
                    f"Valid categories: {valid}"
                )

            canonical = lookup[name_key]

            # FR-1.6: warn on duplicate (last wins)
            if canonical in seen:
                import sys
                print(
                    f"Warning: duplicate --weight for '{canonical}', "
                    f"using last value.",
                    file=sys.stderr,
                )
            seen.add(canonical)

            # FR-1.4: parse decimal or percentage
            value_str = value_raw.strip()
            try:
                if value_str.endswith("%"):
                    value = float(value_str[:-1]) / 100.0
                else:
                    value = float(value_str)
            except ValueError:
                raise ValueError(
                    f"Invalid weight value '{value_str}' for '{canonical}'. "
                    f"Expected a number (e.g. 0.30) or percentage (e.g. 30%)"
                )

            if value < 0:
                raise ValueError(
                    f"Weight for '{canonical}' must be non-negative, got {value}"
                )

            weights[canonical] = value

    # 3. Validate at least one weight > 0
    if all(v == 0 for v in weights.values()):
        raise ValueError("All category weights are zero — at least one must be positive")

    return weights


def format_profiles() -> str:
    """Return a human-readable listing of all built-in weight profiles.

    SPEC-custom-weights FR-5.2.
    """
    lines = ["Available weight profiles:", ""]
    for name, (description, weights) in WEIGHT_PROFILES.items():
        lines.append(f"  {name:<14s}{description}")
        pairs = [f"{cat}: {w * 100:.0f}%" for cat, w in weights.items()]
        # Two categories per line
        for i in range(0, len(pairs), 2):
            chunk = "  ".join(pairs[i:i + 2])
            lines.append(f"{'':16s}{chunk}")
        lines.append("")
    return "\n".join(lines)


class Severity(Enum):
    """§7.2.2 — Recommendation severity levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Recommendation:
    """§7.2.1 — A single actionable recommendation."""

    message: str
    severity: Severity
    category: str


@dataclass
class CategoryResult:
    """Score and findings for a single analysis category."""

    name: str
    score: float  # 0–100
    findings: list[str] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)


@dataclass
class Report:
    """Complete analysis report for a URL."""

    url: str
    categories: list[CategoryResult]
    overall_score: float = 0.0
    grade: str = ""

    def compute_grade(
        self, weights: dict[str, float] | None = None,
    ) -> None:
        """Compute overall_score and grade from category scores and weights.

        NFR-4.2: When a category is omitted, its weight is redistributed
        proportionally across the remaining categories (normalization).

        SPEC-custom-weights: *weights* overrides CATEGORY_WEIGHTS when
        provided.  Falls back to the module-level default when ``None``.
        """
        effective = weights if weights is not None else CATEGORY_WEIGHTS
        weighted_sum = 0.0
        total_weight = 0.0
        for cat in self.categories:
            weight = effective.get(cat.name, 0.0)
            weighted_sum += cat.score * weight
            total_weight += weight
        self.overall_score = round(weighted_sum / total_weight, 1) if total_weight else 0.0
        for threshold, letter in GRADE_THRESHOLDS:
            if self.overall_score >= threshold:
                self.grade = letter
                break
