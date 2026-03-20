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

RECOMMENDATION_THRESHOLD = 90


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

    def compute_grade(self) -> None:
        """Compute overall_score and grade from category scores and weights.

        NFR-4.2: When a category is omitted, its weight is redistributed
        proportionally across the remaining categories (normalization).
        """
        weighted_sum = 0.0
        total_weight = 0.0
        for cat in self.categories:
            weight = CATEGORY_WEIGHTS.get(cat.name, 0.0)
            weighted_sum += cat.score * weight
            total_weight += weight
        self.overall_score = round(weighted_sum / total_weight, 1) if total_weight else 0.0
        for threshold, letter in GRADE_THRESHOLDS:
            if self.overall_score >= threshold:
                self.grade = letter
                break
