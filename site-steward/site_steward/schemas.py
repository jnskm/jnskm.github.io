from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high", "critical"]
Owner = Literal["content", "design", "engineering", "shared"]
ArtifactKind = Literal["screenshot", "text", "log", "report"]


class ScreenshotArtifact(BaseModel):
    kind: ArtifactKind = "screenshot"
    label: str
    path: str
    viewport: str | None = None
    available: bool = True
    note: str | None = None


class AgentFinding(BaseModel):
    agent: str
    summary: str
    category: str
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    suggested_fix: str
    owner: Owner


class Issue(BaseModel):
    id: str
    title: str
    category: str
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    suggested_fix: str
    owner: Owner
    source_agents: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    priority: int = Field(ge=1, le=10)
    action: str
    rationale: str
    owner: Owner
    linked_issue_ids: list[str] = Field(default_factory=list)


class ExtractedContent(BaseModel):
    url: str
    fetched_at: datetime
    title: str | None = None
    meta_description: str | None = None
    headings: list[str] = Field(default_factory=list)
    navigation_labels: list[str] = Field(default_factory=list)
    button_labels: list[str] = Field(default_factory=list)
    paragraph_copy: list[str] = Field(default_factory=list)
    footer_copy: list[str] = Field(default_factory=list)
    image_alts_present: int = 0
    image_alts_missing: int = 0
    raw_text_excerpt: str = ""


class ScoreCard(BaseModel):
    clarity: int = Field(ge=1, le=5)
    trust: int = Field(ge=1, le=5)
    warmth: int = Field(ge=1, le=5)
    usefulness: int = Field(ge=1, le=5)
    discoverability: int = Field(ge=1, le=5)
    cohesion: int = Field(ge=1, le=5)
    overall_homepage_score: float
    message_score: float
    ux_score: float
    ministry_score: float


class FinalReport(BaseModel):
    executive_summary: str
    messaging_review: str
    ux_and_layout_review: str
    navigation_review: str
    theology_alignment_review: str
    seo_basics_review: str
    accessibility_review: str
    screenshot_gallery: list[ScreenshotArtifact] = Field(default_factory=list)
    annotated_issues: list[Issue] = Field(default_factory=list)
    prioritized_action_plan: list[Recommendation] = Field(default_factory=list)
    optional_patch_suggestions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ReviewRun(BaseModel):
    run_id: str
    target_url: str
    repo_path: str | None = None
    project_type: str = "other"
    profile: str
    started_at: datetime
    output_dir: str
    extracted_content: ExtractedContent
    findings: list[AgentFinding] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    screenshots: list[ScreenshotArtifact] = Field(default_factory=list)
    scores: ScoreCard
    final_report: FinalReport

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

