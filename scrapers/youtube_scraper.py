"""
The Gospel Feed — YouTube Sermon Scraper
Fetches latest videos from configured Christian YouTube channels
using the YouTube Data API v3.

Requires YOUTUBE_API_KEY environment variable.
"""

import json
import os
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timezone, timedelta
from pathlib import Path

from tagger import tag_topic
from scorer import score_article

# ─── Configuration ───

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
MAX_AGE_HOURS = 72  # Include videos from the last 72 hours
MIN_SCORE = 25


def fetch_youtube_channel(channel_config: dict) -> list:
    """
    Fetch latest videos from a single YouTube channel.

    Args:
        channel_config: Dict with name, channel_id, trust_tier, default_topic

    Returns:
        List of normalized article dicts matching the RSS scraper format
    """
    if not API_KEY:
        print("  ⚠ YOUTUBE_API_KEY not set — skipping YouTube sources")
        return []

    name = channel_config["name"]
    channel_id = channel_config["channel_id"]
    trust_tier = channel_config.get("trust_tier", 2)
    default_topic = channel_config.get("default_topic", "sermon")

    print(f"  Fetching: {name} (YouTube)...")

    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        # Build the API request URL
        params = urllib.parse.urlencode({
            "key": API_KEY,
            "channelId": channel_id,
            "part": "snippet",
            "order": "date",
            "maxResults": 10,
            "publishedAfter": cutoff_str,
            "type": "video",
        })

        url = f"{YOUTUBE_API_BASE}/search?{params}"

        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={
            "User-Agent": "TheGospelFeed/1.0",
            "Accept": "application/json",
        })

        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        data = json.loads(resp.read().decode("utf-8"))

        items = data.get("items", [])

        for item in items:
            try:
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId", "")

                if not video_id:
                    continue

                title = snippet.get("title", "").strip()
                description = snippet.get("description", "").strip()
                published_str = snippet.get("publishedAt", "")
                channel_title = snippet.get("channelTitle", name)

                if not title:
                    continue

                # Parse publish date
                try:
                    published = datetime.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ")
                    published = published.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    published = datetime.now(timezone.utc)

                if published < cutoff:
                    continue

                # Truncate description for summary
                summary = description[:300] + "..." if len(description) > 300 else description

                # Auto-tag topic
                topic = tag_topic(title, summary, default_topic)

                # Score the video
                score = score_article(
                    title=title,
                    summary=summary,
                    published_at=published,
                    trust_tier=trust_tier,
                )

                # Estimate video duration (not available from search API, use defaults)
                read_time = "video"

                # Build the article object (same format as RSS scraper)
                video_url = f"https://www.youtube.com/watch?v={video_id}"

                article = {
                    "id": f"yt-{video_id[:10]}",
                    "title": title,
                    "summary": summary,
                    "url": video_url,
                    "source_name": name,
                    "author": channel_title,
                    "topic": topic,
                    "score": score,
                    "read_time": read_time,
                    "published_at": published.isoformat(),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "trust_tier": trust_tier,
                    "is_live": score >= MIN_SCORE,
                    "is_editors_pick": False,
                    "is_video": True,
                    "video_id": video_id,
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                }

                articles.append(article)

            except Exception as e:
                print(f"  ⚠ Skipping video in {name}: {e}")
                continue

        print(f"  ✓ {name}: {len(articles)} videos found")

    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"  ✗ {name}: API quota exceeded or key invalid")
        else:
            print(f"  ✗ {name}: HTTP {e.code} — {e.reason}")
    except urllib.error.URLError as e:
        print(f"  ✗ {name}: Connection failed — {e.reason}")
    except Exception as e:
        print(f"  ✗ {name}: Error — {e}")

    return articles


def fetch_all_youtube(sources_config: dict) -> list:
    """
    Fetch videos from all configured YouTube channels.

    Args:
        sources_config: The full sources.yaml config dict

    Returns:
        List of all video articles
    """
    all_videos = []
    youtube_sources = sources_config.get("sources", {}).get("youtube", [])

    if not youtube_sources:
        print("  No YouTube sources configured")
        return []

    if not API_KEY:
        print("  ⚠ YOUTUBE_API_KEY environment variable not set")
        print("  ⚠ Skipping all YouTube sources")
        return []

    print(f"\nFetching from {len(youtube_sources)} YouTube channels...\n")

    for source in youtube_sources:
        videos = fetch_youtube_channel(source)
        all_videos.extend(videos)

    print(f"\nTotal YouTube videos: {len(all_videos)}")
    return all_videos


# ─── For standalone testing ───

if __name__ == "__main__":
    import yaml

    sources_file = Path(__file__).parent / "sources.yaml"
    with open(sources_file, "r") as f:
        sources = yaml.safe_load(f)

    videos = fetch_all_youtube(sources)

    for v in videos:
        print(f"  [{v['topic']}] {v['title']}")
        print(f"    {v['url']} | Score: {v['score']}")
        print()
