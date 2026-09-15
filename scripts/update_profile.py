#!/usr/bin/env python3
"""Refresh the recent-writing block in the profile README from the blog RSS feed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import re
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SITE = "https://blog.mlxb.cc/"
FEED = f"{SITE}rss.xml"
USER_AGENT = "ALVIN-YANG-profile/1.0 (+https://github.com/ALVIN-YANG)"
START = "<!-- recent_posts starts -->"
END = "<!-- recent_posts ends -->"


@dataclass(frozen=True)
class Post:
    title: str
    url: str
    updated: datetime


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_post_url(value: str) -> str | None:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc != urlparse(SITE).netloc:
        return None
    encoded_path = quote(parsed.path, safe="/%")
    return f"{parsed.scheme}://{parsed.netloc}{encoded_path}"


def parse_feed(xml: str) -> list[Post]:
    root = ET.fromstring(xml)
    posts: list[Post] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        url = normalize_post_url(item.findtext("link") or "")
        published = (item.findtext("pubDate") or "").strip()
        if not title or not url or not published:
            continue
        try:
            updated = normalize_datetime(parsedate_to_datetime(published))
        except (TypeError, ValueError):
            continue
        posts.append(Post(title=title, url=url, updated=updated))
    return posts


def truncate(title: str, limit: int = 48) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) <= limit:
        return title
    keep = limit - 3
    left = (keep + 1) // 2
    right = keep // 2
    return f"{title[:left]}...{title[-right:]}"


def select_posts(posts: list[Post]) -> list[Post]:
    ordered = sorted(posts, key=lambda post: normalize_datetime(post.updated), reverse=True)
    return [post for post in ordered if "/ai-news/" not in post.url][:5]


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
    posts = parse_feed(fetch(FEED))
    selected = select_posts(posts)
    if len(selected) < 3:
        raise RuntimeError(f"Expected at least 3 posts, found {len(selected)}")
    update_readme(render(selected))


if __name__ == "__main__":
    main()
