from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_profile import Post, parse_feed, select_posts


class ProfileUpdateTests(unittest.TestCase):
    def test_select_posts_handles_mixed_timezone_values(self) -> None:
        posts = [
            Post("带时区", "https://blog.mlxb.cc/ai/aware/", datetime(2026, 9, 15, tzinfo=timezone.utc)),
            Post("无时区", "https://blog.mlxb.cc/ai/naive/", datetime(2026, 9, 14)),
            Post("第三篇", "https://blog.mlxb.cc/ai/third/", datetime(2026, 9, 13, tzinfo=timezone.utc)),
        ]

        self.assertEqual([post.title for post in select_posts(posts)], ["带时区", "无时区", "第三篇"])

    def test_parse_feed_reads_posts_and_normalizes_dates(self) -> None:
        rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
          <item>
            <title>最新文章</title>
            <link>https://blog.mlxb.cc/ai/latest/</link>
            <pubDate>Tue, 15 Sep 2026 00:00:00 GMT</pubDate>
          </item>
          <item>
            <title>周报</title>
            <link>https://blog.mlxb.cc/ai-news/2026-09-07-weekly/</link>
            <pubDate>Sun, 13 Sep 2026 00:00:00 +0800</pubDate>
          </item>
        </channel></rss>"""

        posts = parse_feed(rss)

        self.assertEqual([post.title for post in posts], ["最新文章", "周报"])
        self.assertTrue(all(post.updated.tzinfo is not None for post in posts))

    def test_select_posts_uses_five_latest_articles_not_ai_news_index(self) -> None:
        posts = [
            Post("AI News", "https://blog.mlxb.cc/ai-news/", datetime(2026, 9, 16, tzinfo=timezone.utc)),
            *[
                Post(
                    f"文章 {day}",
                    f"https://blog.mlxb.cc/ai/post-{day}/",
                    datetime(2026, 9, day, tzinfo=timezone.utc),
                )
                for day in range(15, 9, -1)
            ],
        ]

        selected = select_posts(posts)

        self.assertEqual(len(selected), 5)
        self.assertNotIn("AI News", [post.title for post in selected])


if __name__ == "__main__":
    unittest.main()
