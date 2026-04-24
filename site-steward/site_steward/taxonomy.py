from __future__ import annotations

from dataclasses import dataclass


REVIEW_CATEGORIES = [
    "Messaging clarity",
    "Layout and hierarchy",
    "Navigation",
    "Readability",
    "Accessibility",
    "Performance basics",
    "SEO basics",
    "Brand consistency",
    "Ministry alignment",
    "Music-book integration",
    "Calls to action",
]

SCORE_DIMENSIONS = [
    "clarity",
    "trust",
    "warmth",
    "usefulness",
    "discoverability",
    "cohesion",
]


@dataclass(frozen=True)
class ReviewProfile:
    slug: str
    label: str
    rules: list[str]
    focus_areas: list[str]


MINISTRY_PROFILE = ReviewProfile(
    slug="ministry",
    label="Ministry",
    rules=[
        "Homepage should quickly explain music plus books.",
        "Homepage should offer a first next step.",
        "Site should feel warm, humble, and clear.",
        "Calls to action should serve ministry, not vanity.",
        "Music and books should not live as separate worlds.",
        "Testimony should support the message without dominating it.",
        "The visitor should understand within seconds what this work is for.",
    ],
    focus_areas=[
        "clarity of calling",
        "warmth and humility",
        "usefulness to suffering believers",
        "integration of music and books",
        "first-step clarity for new visitors",
    ],
)

PORTFOLIO_PROFILE = ReviewProfile(
    slug="portfolio",
    label="Portfolio",
    rules=[
        "Homepage should quickly identify the creator and type of work.",
        "Visitors should see a clear path to browse featured work.",
        "Calls to action should support trust and inquiry.",
    ],
    focus_areas=[
        "identity clarity",
        "work discoverability",
        "trust signals",
    ],
)

PROFILES = {
    MINISTRY_PROFILE.slug: MINISTRY_PROFILE,
    PORTFOLIO_PROFILE.slug: PORTFOLIO_PROFILE,
}

