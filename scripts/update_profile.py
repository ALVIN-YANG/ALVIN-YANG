#!/usr/bin/env python3
"""Refresh the recent-writing block in the profile README."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SITE = "https://ilovestudy.club/"
USER_AGENT = "ALVIN-YANG-profile/1.0 (+https://github.com/ALVIN-YANG)"
START = "<!-- recent_posts starts -->"
END = "<!-- recent_posts ends -->"


@dataclass(frozen=True)
class Post:
    title: str
    url: str
    updated: datetime


class HomeLinksParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_main = False
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "main":
            self.in_main = True
        elif self.in_main and tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self.in_main = False


class PostParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.updated_raw = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "time" and values.get("datetime") and not self.updated_raw:
            self.updated_raw = values["datetime"] or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def candidate_urls() -> list[str]:
    parser = HomeLinksParser()
    parser.feed(fetch(SITE))

    excluded = {"/", "/about/", "/ai-news/", "/model-arena/"}
    urls: list[str] = []
    for href in parser.links:
        url = urljoin(SITE, href)
        parsed = urlparse(url)
        if parsed.netloc != urlparse(SITE).netloc or parsed.path in excluded:
            continue
        if not parsed.path.endswith("/"):
            continue
        encoded_path = quote(parsed.path, safe="/%")
        normalized = f"{parsed.scheme}://{parsed.netloc}{encoded_path}"
        if normalized not in urls:
            urls.append(normalized)
    return urls[:80]


def parse_post(url: str) -> Post | None:
    try:
        parser = PostParser()
        parser.feed(fetch(url))
        title = "".join(parser.title_parts).removesuffix(" | Alvin Yang").strip()
        if not title or not parser.updated_raw:
            return None
        updated = datetime.fromisoformat(parser.updated_raw.replace("Z", "+00:00"))
        return Post(title=title, url=url, updated=updated)
    except Exception as error:
        print(f"Skipping {url}: {error}")
        return None


def truncate(title: str, limit: int = 48) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) <= limit:
        return title
    keep = limit - 3
    left = (keep + 1) // 2
    right = keep // 2
    return f"{title[:left]}...{title[-right:]}"


def select_posts(posts: list[Post]) -> list[Post]:
    ordered = sorted(posts, key=lambda post: post.updated, reverse=True)
    articles = [post for post in ordered if "/ai-news/" not in post.url][:4]
    weekly = [post for post in ordered if "/ai-news/" in post.url][:1]
    return sorted(articles + weekly, key=lambda post: post.updated, reverse=True)


def render(posts: list[Post]) -> str:
    return "<br>\n".join(
        f"• [{truncate(post.title)}]({post.url}) — {post.updated:%Y-%m-%d}"
        for post in posts
    )


def update_readme(block: str) -> None:
    content = README.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        flags=re.DOTALL,
    )
    rewritten, count = pattern.subn(f"{START}\n{block}\n{END}", content)
    if count != 1:
        raise RuntimeError("README recent-post markers are missing or duplicated")
    README.write_text(rewritten, encoding="utf-8")


def main() -> None:
    with ThreadPoolExecutor(max_workers=8) as executor:
        posts = [post for post in executor.map(parse_post, candidate_urls()) if post]
    selected = select_posts(posts)
    if len(selected) < 3:
        raise RuntimeError(f"Expected at least 3 posts, found {len(selected)}")
    update_readme(render(selected))


if __name__ == "__main__":
    main()
