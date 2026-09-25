import re
import unicodedata
from html.parser import HTMLParser
from typing import Iterable


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return " ".join(self._parts)


def strip_html(html: str | None) -> str:
    if not html:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return re.sub(r"\s+", " ", parser.text()).strip()


def slugify(value: str, *, max_length: int = 180) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    if not value:
        value = "game"
    return value[:max_length].rstrip("-")


def unique_slug(base: str, suffix: str) -> str:
    combined = slugify(f"{base}-{suffix}")
    return combined[:180]


def parse_genre_labels(raw: str | None) -> list[str]:
    if not raw:
        return []
    labels: list[str] = []
    for part in raw.replace("/", ",").split(","):
        label = part.strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def build_rag_document(
    *,
    title: str,
    platform_name: str | None = None,
    summary: str | None = None,
    genres: Iterable[str] | None = None,
    developer: str | None = None,
    publisher: str | None = None,
    extra: str | None = None,
) -> str:
    lines = [f"Title: {title}"]
    if platform_name:
        lines.append(f"Platform: {platform_name}")
    if genres:
        lines.append(f"Genres: {', '.join(genres)}")
    if developer:
        lines.append(f"Developer: {developer}")
    if publisher:
        lines.append(f"Publisher: {publisher}")
    if summary:
        lines.append(f"Description: {summary}")
    if extra:
        lines.append(extra)
    return "\n".join(lines)
