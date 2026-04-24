from __future__ import annotations

from pathlib import Path

from .schemas import ScreenshotArtifact


VIEWPORTS = [
    ("desktop", {"width": 1440, "height": 1800}),
    ("tablet", {"width": 834, "height": 1400}),
    ("mobile", {"width": 390, "height": 1200}),
]


def capture_screenshots(url: str, output_dir: Path) -> tuple[list[ScreenshotArtifact], list[str]]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return (
            [],
            [
                "Screenshots skipped because Playwright is not installed in the current environment.",
            ],
        )

    screenshot_dir = output_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[ScreenshotArtifact] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for label, viewport in VIEWPORTS:
            page = browser.new_page(viewport=viewport)
            page.goto(url, wait_until="networkidle", timeout=30000)
            path = screenshot_dir / f"{label}.png"
            page.screenshot(path=str(path), full_page=True)
            artifacts.append(
                ScreenshotArtifact(
                    label=label,
                    path=str(path),
                    viewport=f"{viewport['width']}x{viewport['height']}",
                )
            )

            body = page.locator("body")
            box = body.bounding_box() or {"x": 0, "y": 0, "width": viewport["width"], "height": viewport["height"]}
            hero_height = min(900, max(300, box["height"] * 0.35))
            footer_y = max(0, box["height"] - min(500, box["height"] * 0.2))

            hero_path = screenshot_dir / f"{label}-hero.png"
            page.screenshot(
                path=str(hero_path),
                clip={
                    "x": 0,
                    "y": 0,
                    "width": viewport["width"],
                    "height": hero_height,
                },
            )
            artifacts.append(
                ScreenshotArtifact(
                    label=f"{label} hero",
                    path=str(hero_path),
                    viewport=f"{viewport['width']}x{int(hero_height)}",
                )
            )

            footer_path = screenshot_dir / f"{label}-footer.png"
            page.screenshot(
                path=str(footer_path),
                clip={
                    "x": 0,
                    "y": footer_y,
                    "width": viewport["width"],
                    "height": min(500, box["height"] - footer_y),
                },
            )
            artifacts.append(
                ScreenshotArtifact(
                    label=f"{label} footer",
                    path=str(footer_path),
                    viewport=f"{viewport['width']}x{min(500, int(box['height'] - footer_y))}",
                )
            )
            page.close()
        browser.close()

    return artifacts, []

