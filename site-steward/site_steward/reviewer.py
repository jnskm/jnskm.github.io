from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from .browser import capture_screenshots
from .extractors import extract_content, normalize_text
from .schemas import (
    AgentFinding,
    FinalReport,
    Issue,
    Recommendation,
    ReviewRun,
    ScoreCard,
)
from .taxonomy import PROFILES, ReviewProfile


USER_AGENT = "site-steward/0.1 (+local review tool)"


def fetch_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    response.raise_for_status()
    return response.text


def _evidence_snippet(text: str, max_len: int = 180) -> str:
    return text if len(text) <= max_len else f"{text[: max_len - 3]}..."


def _make_issue(
    slug: str,
    title: str,
    category: str,
    severity: str,
    confidence: float,
    evidence: list[str],
    suggested_fix: str,
    owner: str,
) -> tuple[AgentFinding, Issue]:
    finding = AgentFinding(
        agent="site-steward-mvp",
        summary=title,
        category=category,
        severity=severity,
        confidence=confidence,
        evidence=evidence,
        suggested_fix=suggested_fix,
        owner=owner,
    )
    issue = Issue(
        id=slug,
        title=title,
        category=category,
        severity=severity,
        confidence=confidence,
        evidence=evidence,
        suggested_fix=suggested_fix,
        owner=owner,
        source_agents=[finding.agent],
    )
    return finding, issue


def _contains_any(haystack: str, needles: list[str]) -> bool:
    return any(needle in haystack for needle in needles)


def analyze_content(content, profile: ReviewProfile) -> tuple[list[AgentFinding], list[Issue], list[str]]:
    findings: list[AgentFinding] = []
    issues: list[Issue] = []
    notes: list[str] = []

    combined_head = normalize_text(" ".join(content.headings[:3] + content.paragraph_copy[:3])).lower()
    all_text = normalize_text(
        " ".join(
            [
                content.title or "",
                content.meta_description or "",
                *content.headings,
                *content.navigation_labels,
                *content.button_labels,
                *content.paragraph_copy,
                *content.footer_copy,
            ]
        )
    ).lower()

    if not any(heading.strip() for heading in content.headings[:1]):
        finding, issue = _make_issue(
            slug="missing-h1",
            title="Homepage lacks a clear opening headline",
            category="Layout and hierarchy",
            severity="high",
            confidence=0.9,
            evidence=["No H1 heading was detected in the homepage structure."],
            suggested_fix="Add a plain-language H1 that states who JNSKM is and what visitors can do first.",
            owner="content",
        )
        findings.append(finding)
        issues.append(issue)

    if not content.button_labels:
        finding, issue = _make_issue(
            slug="missing-cta",
            title="Homepage does not surface a strong first next step",
            category="Calls to action",
            severity="high",
            confidence=0.82,
            evidence=["No clear button-style CTA labels were extracted."],
            suggested_fix="Add a primary CTA near the top of the page such as start here, listen now, or read first.",
            owner="shared",
        )
        findings.append(finding)
        issues.append(issue)

    if profile.slug == "ministry":
        has_music = _contains_any(all_text, ["music", "song", "songs", "listen", "album"])
        has_books = _contains_any(all_text, ["book", "books", "read", "reading", "study", "studies"])
        if not (has_music and has_books):
            finding, issue = _make_issue(
                slug="music-book-gap",
                title="Homepage does not clearly connect music and books",
                category="Music-book integration",
                severity="high",
                confidence=0.78,
                evidence=[
                    _evidence_snippet(
                        combined_head or "The opening headings and paragraphs do not mention both music and books."
                    )
                ],
                suggested_fix="Make the hero or opening section explicitly explain how the music and books work together in one ministry.",
                owner="content",
            )
            findings.append(finding)
            issues.append(issue)

        if not _contains_any(all_text, ["suffering", "hope", "encourage", "comfort", "help", "ministry", "christ"]):
            finding, issue = _make_issue(
                slug="ministry-purpose-unclear",
                title="Ministry purpose is not obvious within the opening content",
                category="Ministry alignment",
                severity="medium",
                confidence=0.7,
                evidence=[
                    _evidence_snippet(
                        combined_head or "The opening section does not clearly describe the ministry purpose."
                    )
                ],
                suggested_fix="Add one sentence near the top explaining who this ministry serves and why the work exists.",
                owner="content",
            )
            findings.append(finding)
            issues.append(issue)

    if not content.meta_description:
        finding, issue = _make_issue(
            slug="missing-meta-description",
            title="Homepage is missing a meta description",
            category="SEO basics",
            severity="medium",
            confidence=0.95,
            evidence=["No `<meta name=\"description\">` tag was found."],
            suggested_fix="Add a concise meta description summarizing the site mission and the main paths for visitors.",
            owner="engineering",
        )
        findings.append(finding)
        issues.append(issue)

    if content.image_alts_missing > 0:
        finding, issue = _make_issue(
            slug="missing-image-alt",
            title="Some images are missing alt text",
            category="Accessibility",
            severity="medium",
            confidence=0.92,
            evidence=[f"{content.image_alts_missing} image(s) were missing alt text."],
            suggested_fix="Add purposeful alt text to informative images and empty alt attributes to decorative ones.",
            owner="engineering",
        )
        findings.append(finding)
        issues.append(issue)

    if len(content.navigation_labels) < 3:
        notes.append("Navigation labels are sparse, which may reduce discoverability for first-time visitors.")

    if content.title and len(content.title) < 20:
        notes.append("The page title is short enough that it may undersell the site's purpose in search results.")

    return findings, issues, notes


def score_run(issues: list[Issue], profile: ReviewProfile) -> ScoreCard:
    penalties = Counter(issue.category for issue in issues)
    severity_weights = {"low": 0.2, "medium": 0.45, "high": 0.9, "critical": 1.2}

    base = {
        "clarity": 5.0,
        "trust": 5.0,
        "warmth": 5.0,
        "usefulness": 5.0,
        "discoverability": 5.0,
        "cohesion": 5.0,
    }

    for issue in issues:
        weight = severity_weights[issue.severity]
        if issue.category in {"Messaging clarity", "Layout and hierarchy", "Calls to action"}:
            base["clarity"] -= weight
        if issue.category in {"Navigation", "SEO basics", "Calls to action"}:
            base["discoverability"] -= weight
        if issue.category in {"Accessibility", "Performance basics"}:
            base["trust"] -= weight * 0.7
        if issue.category in {"Ministry alignment"}:
            base["warmth"] -= weight
            base["usefulness"] -= weight * 0.8
        if issue.category in {"Music-book integration", "Brand consistency"}:
            base["cohesion"] -= weight

    if profile.slug == "ministry":
        base["warmth"] -= penalties["Music-book integration"] * 0.2
        base["usefulness"] -= penalties["Ministry alignment"] * 0.2

    rounded = {key: max(1, min(5, round(value))) for key, value in base.items()}

    message_score = round((rounded["clarity"] + rounded["cohesion"]) / 2, 1)
    ux_score = round((rounded["discoverability"] + rounded["trust"]) / 2, 1)
    ministry_score = round((rounded["warmth"] + rounded["usefulness"]) / 2, 1)
    overall = round(
        (message_score + ux_score + ministry_score + rounded["trust"]) / 4,
        1,
    )

    return ScoreCard(
        clarity=rounded["clarity"],
        trust=rounded["trust"],
        warmth=rounded["warmth"],
        usefulness=rounded["usefulness"],
        discoverability=rounded["discoverability"],
        cohesion=rounded["cohesion"],
        overall_homepage_score=overall,
        message_score=message_score,
        ux_score=ux_score,
        ministry_score=ministry_score,
    )


def build_recommendations(issues: list[Issue]) -> list[Recommendation]:
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ordered = sorted(issues, key=lambda issue: (severity_rank[issue.severity], issue.category, issue.title))
    recommendations: list[Recommendation] = []
    for index, issue in enumerate(ordered[:5], start=1):
        recommendations.append(
            Recommendation(
                priority=index,
                action=issue.suggested_fix,
                rationale=issue.title,
                owner=issue.owner,
                linked_issue_ids=[issue.id],
            )
        )
    return recommendations


def build_report_text(content, issues: list[Issue], recommendations: list[Recommendation], notes: list[str], scores: ScoreCard) -> FinalReport:
    top_issue_titles = ", ".join(issue.title for issue in issues[:3]) if issues else "no major issues detected"
    messaging_review = (
        f"Opening headings and copy suggest: {_evidence_snippet(' | '.join(content.headings[:3] + content.paragraph_copy[:2]) or 'limited messaging evidence found.')}"
    )
    ux_review = (
        f"The page exposes {len(content.navigation_labels)} navigation labels and {len(content.button_labels)} CTA/button labels."
    )
    navigation_review = (
        "Navigation labels: " + (", ".join(content.navigation_labels[:8]) if content.navigation_labels else "none detected")
    )
    theology_review = (
        "Ministry profile rules were checked against the opening content, CTA language, and evidence of music/book integration."
    )
    seo_review = (
        f"Title present: {'yes' if content.title else 'no'}. Meta description present: {'yes' if content.meta_description else 'no'}."
    )
    accessibility_review = (
        f"Images with alt text: {content.image_alts_present}. Images missing alt text: {content.image_alts_missing}."
    )

    patch_suggestions = [
        "Rewrite the hero so it names the audience, ministry purpose, and first action in one compact section.",
        "Add or refine a primary CTA above the fold and a secondary path for music and books.",
        "Tighten metadata and image alt text to improve baseline SEO and accessibility.",
    ]

    return FinalReport(
        executive_summary=(
            f"Homepage score: {scores.overall_homepage_score}/5. The review surfaced {len(issues)} issue(s), with the most important theme(s): {top_issue_titles}."
        ),
        messaging_review=messaging_review,
        ux_and_layout_review=ux_review,
        navigation_review=navigation_review,
        theology_alignment_review=theology_review,
        seo_basics_review=seo_review,
        accessibility_review=accessibility_review,
        annotated_issues=issues,
        prioritized_action_plan=recommendations,
        optional_patch_suggestions=patch_suggestions,
        notes=notes,
    )


def make_run_id(url: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    host = urlparse(url).netloc.replace(":", "_") or "local"
    return f"{timestamp}_{host}"


def review_homepage(url: str, profile_slug: str, output_root: Path, repo_path: str | None = None) -> ReviewRun:
    if profile_slug not in PROFILES:
        raise ValueError(f"Unsupported profile '{profile_slug}'. Available: {', '.join(sorted(PROFILES))}")

    profile = PROFILES[profile_slug]
    run_id = make_run_id(url)
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    html = fetch_html(url)
    content = extract_content(url, html)
    findings, issues, notes = analyze_content(content, profile)
    scores = score_run(issues, profile)
    recommendations = build_recommendations(issues)
    screenshots, screenshot_notes = capture_screenshots(url, output_dir)
    notes.extend(screenshot_notes)
    report = build_report_text(content, issues, recommendations, notes, scores)
    report.screenshot_gallery = screenshots

    return ReviewRun(
        run_id=run_id,
        target_url=url,
        repo_path=repo_path,
        profile=profile.slug,
        started_at=datetime.now(timezone.utc),
        output_dir=str(output_dir),
        extracted_content=content,
        findings=findings,
        issues=issues,
        recommendations=recommendations,
        screenshots=screenshots,
        scores=scores,
        final_report=report,
    )

