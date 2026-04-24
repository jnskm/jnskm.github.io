from __future__ import annotations

import csv
import json
from pathlib import Path

from .schemas import ReviewRun


def render_markdown(review_run: ReviewRun) -> str:
    report = review_run.final_report
    lines = [
        f"# Site Steward Review",
        "",
        f"- Run ID: `{review_run.run_id}`",
        f"- URL: `{review_run.target_url}`",
        f"- Profile: `{review_run.profile}`",
        f"- Overall homepage score: `{review_run.scores.overall_homepage_score}/5`",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
        "## Messaging Review",
        "",
        report.messaging_review,
        "",
        "## UX and Layout Review",
        "",
        report.ux_and_layout_review,
        "",
        "## Navigation Review",
        "",
        report.navigation_review,
        "",
        "## Theology and Ministry Alignment Review",
        "",
        report.theology_alignment_review,
        "",
        "## SEO Basics Review",
        "",
        report.seo_basics_review,
        "",
        "## Accessibility Review",
        "",
        report.accessibility_review,
        "",
        "## Extracted Content Snapshot",
        "",
        f"- Title: {review_run.extracted_content.title or 'None'}",
        f"- Meta description: {review_run.extracted_content.meta_description or 'None'}",
        f"- Headings: {', '.join(review_run.extracted_content.headings[:8]) or 'None'}",
        f"- Navigation labels: {', '.join(review_run.extracted_content.navigation_labels[:12]) or 'None'}",
        f"- CTA labels: {', '.join(review_run.extracted_content.button_labels[:12]) or 'None'}",
        "",
        "## Screenshot Gallery",
        "",
    ]

    if report.screenshot_gallery:
        for artifact in report.screenshot_gallery:
            rel_path = Path(artifact.path).relative_to(review_run.output_path)
            lines.append(f"- {artifact.label}: `{rel_path}`")
    else:
        lines.append("- No screenshots captured in this run.")

    lines.extend(
        [
            "",
            "## Annotated Issues",
            "",
        ]
    )

    if report.annotated_issues:
        for issue in report.annotated_issues:
            lines.append(
                f"### {issue.title}\n"
                f"- Category: {issue.category}\n"
                f"- Severity: {issue.severity}\n"
                f"- Confidence: {issue.confidence}\n"
                f"- Owner: {issue.owner}\n"
                f"- Evidence: {' | '.join(issue.evidence) or 'None'}\n"
                f"- Suggested fix: {issue.suggested_fix}\n"
            )
    else:
        lines.append("No major issues detected.")

    lines.extend(["", "## Prioritized Action Plan", ""])
    if report.prioritized_action_plan:
        for recommendation in report.prioritized_action_plan:
            lines.append(
                f"{recommendation.priority}. {recommendation.action} "
                f"(owner: {recommendation.owner}; why: {recommendation.rationale})"
            )
    else:
        lines.append("No actions generated.")

    lines.extend(["", "## Optional Patch Suggestions", ""])
    for suggestion in report.optional_patch_suggestions:
        lines.append(f"- {suggestion}")

    if report.notes:
        lines.extend(["", "## Notes", ""])
        for note in report.notes:
            lines.append(f"- {note}")

    return "\n".join(lines).strip() + "\n"


def write_outputs(review_run: ReviewRun) -> dict[str, Path]:
    output_dir = review_run.output_path
    report_md = output_dir / "report.md"
    report_json = output_dir / "report.json"
    issues_csv = output_dir / "issues.csv"

    report_md.write_text(render_markdown(review_run), encoding="utf-8")
    report_json.write_text(
        json.dumps(review_run.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    with issues_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "title",
                "category",
                "severity",
                "confidence",
                "owner",
                "suggested_fix",
                "evidence",
            ],
        )
        writer.writeheader()
        for issue in review_run.issues:
            writer.writerow(
                {
                    "id": issue.id,
                    "title": issue.title,
                    "category": issue.category,
                    "severity": issue.severity,
                    "confidence": issue.confidence,
                    "owner": issue.owner,
                    "suggested_fix": issue.suggested_fix,
                    "evidence": " | ".join(issue.evidence),
                }
            )

    return {
        "report_md": report_md,
        "report_json": report_json,
        "issues_csv": issues_csv,
    }

