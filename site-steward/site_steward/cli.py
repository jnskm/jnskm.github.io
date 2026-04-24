from __future__ import annotations

from pathlib import Path

import typer

from .reporters import write_outputs
from .reviewer import review_homepage
from .taxonomy import PROFILES


app = typer.Typer(help="Local-first homepage reviewer.", no_args_is_help=True)


def default_output_root() -> Path:
    return Path(__file__).resolve().parents[1] / "runs"


@app.command("review")
def review(
    url: str = typer.Option(..., "--url", help="Target homepage URL to review."),
    profile: str = typer.Option("ministry", "--profile", help=f"Review profile: {', '.join(sorted(PROFILES))}"),
    repo_path: str | None = typer.Option(None, "--repo-path", help="Optional local repository path."),
    output_root: Path = typer.Option(default_output_root(), "--output-root", help="Directory for run artifacts."),
) -> None:
    review_run = review_homepage(
        url=url,
        profile_slug=profile,
        output_root=output_root,
        repo_path=repo_path,
    )
    outputs = write_outputs(review_run)

    typer.echo(f"Created review run: {review_run.run_id}")
    typer.echo(f"Output directory: {review_run.output_dir}")
    typer.echo(f"Markdown report: {outputs['report_md']}")
    typer.echo(f"JSON report: {outputs['report_json']}")
    typer.echo(f"Issues CSV: {outputs['issues_csv']}")
    typer.echo(f"Issues found: {len(review_run.issues)}")
    typer.echo(f"Overall homepage score: {review_run.scores.overall_homepage_score}/5")


@app.callback()
def callback() -> None:
    """Expose subcommands even when only one command exists."""


def main() -> None:
    app()


if __name__ == "__main__":
    main()
