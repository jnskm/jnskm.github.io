from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from .schemas import ExtractedContent


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def _text_list(elements: Iterable[Tag], limit: int | None = None) -> list[str]:
    values: list[str] = []
    for element in elements:
        text = normalize_text(element.get_text(" ", strip=True))
        if text and text not in values:
            values.append(text)
        if limit is not None and len(values) >= limit:
            break
    return values


def _visible_text_nodes(soup: BeautifulSoup) -> list[str]:
    blocked = {"script", "style", "noscript", "template", "svg"}
    values: list[str] = []
    for node in soup.find_all(string=True):
        if not isinstance(node, NavigableString):
            continue
        parent = node.parent
        if parent is None or parent.name in blocked:
            continue
        text = normalize_text(str(node))
        if text:
            values.append(text)
    return values


def extract_content(url: str, html: str) -> ExtractedContent:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else None

    meta_description = None
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        meta_description = normalize_text(meta["content"])

    headings = _text_list(soup.find_all(["h1", "h2", "h3"]))
    navigation_labels = _text_list(soup.select("nav a, header a"), limit=20)
    button_labels = _text_list(
        soup.select(
            "button, input[type='submit'], input[type='button'], a[role='button'], a.button, a.btn"
        ),
        limit=20,
    )
    paragraph_copy = _text_list(soup.find_all("p"), limit=20)
    footer_copy = _text_list(soup.select("footer, footer p, footer a"), limit=20)

    image_alts_present = 0
    image_alts_missing = 0
    for image in soup.find_all("img"):
        if image.get("alt") is None:
            image_alts_missing += 1
        else:
            image_alts_present += 1

    raw_text = " ".join(_visible_text_nodes(soup))

    return ExtractedContent(
        url=url,
        fetched_at=datetime.now(timezone.utc),
        title=title,
        meta_description=meta_description,
        headings=headings,
        navigation_labels=navigation_labels,
        button_labels=button_labels,
        paragraph_copy=paragraph_copy,
        footer_copy=footer_copy,
        image_alts_present=image_alts_present,
        image_alts_missing=image_alts_missing,
        raw_text_excerpt=raw_text[:1500],
    )

