"""
The Gospel Feed — RSS Content Scraper
Fetches articles from all configured RSS sources, normalizes them,
scores quality, auto-tags topics, deduplicates, and outputs clean JSON.

This script is designed to run as an AWS Lambda function triggered
by GitHub Actions or EventBridge at 6 AM UTC daily.

For local testing:
    pip install feedparser pyyaml
    python rss_scraper.py
"""

import json
import hashlib
import re
import os
import urllib.request
import ssl
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import yaml

from tagger import tag_topic
from scorer import score_article, estimate_read_time
from youtube_scraper import fetch_all_youtube


# ─── Configuration ───

SOURCES_FILE = Path(__file__).parent / "sources.yaml"
OUTPUT_FILE = Path(__file__).parent / "output" / "feed.json"
SEEN_FILE = Path(__file__).parent / "output" / "seen_urls.json"
MAX_AGE_HOURS = 72  # Include articles from the last 72 hours (3 days)
MIN_SCORE = 25      # Minimum quality score to include

# User-Agent string to identify as a real application (prevents 403 blocks)
USER_AGENT = "TheGospelFeed/1.0 (+https://thegospelfeed.com) Content Aggregator"


def load_sources() -> dict:
    """Load source configuration from YAML file."""
    with open(SOURCES_FILE, "r") as f:
        return yaml.safe_load(f)


def load_seen_urls() -> set:
    """Load previously seen URLs to deduplicate across runs."""
    if SEEN_FILE.exists():
        with open(SEEN_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("urls", []))
    return set()


def save_seen_urls(urls: set):
    """Save seen URLs for future deduplication."""
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_FILE, "w") as f:
        json.dump({"urls": list(urls), "updated": datetime.now(timezone.utc).isoformat()}, f)


def generate_id(url: str) -> str:
    """Generate a short unique ID from a URL."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def clean_html(text: str) -> str:
    """Strip HTML tags and clean up whitespace."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if len(clean) > 300:
        clean = clean[:297] + "..."
    return clean


def parse_date(entry) -> datetime:
    """Extract publication date from a feed entry."""
    for field in ['published_parsed', 'updated_parsed']:
        parsed = entry.get(field)
        if parsed:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError, OSError):
                continue

    for field in ['published', 'updated']:
        date_str = entry.get(field, '')
        if date_str:
            for fmt in [
                '%a, %d %b %Y %H:%M:%S %z',
                '%a, %d %b %Y %H:%M:%S %Z',
                '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%d %H:%M:%S',
            ]:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    continue

    return datetime.now(timezone.utc)


def fetch_feed_with_headers(url: str) -> str:
    """
    Fetch an RSS feed URL with proper headers to avoid 403 blocks.
    Returns the raw XML/text content of the feed.
    """
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    return resp.read()


def fetch_rss_source(source: dict) -> list:
    """
    Fetch and parse articles from a single RSS source.
    Uses custom headers to prevent 403 Forbidden errors.
    """
    articles = []
    name = source["name"]
    url = source["url"]
    trust_tier = source.get("trust_tier", 2)
    default_topic = source.get("default_topic", "faith")

    print(f"  Fetching: {name}...")

    try:
        # Fetch with proper User-Agent header
        raw_content = fetch_feed_with_headers(url)
        feed = feedparser.parse(raw_content)

        if feed.bozo and not feed.entries:
            print(f"  ⚠ Warning: {name} — feed parse error: {feed.bozo_exception}")
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = clean_html(entry.get("summary", entry.get("description", "")))
                author = entry.get("author", "").strip()
                published = parse_date(entry)

                if not title or not link:
                    continue

                if published < cutoff:
                    continue

                topic = tag_topic(title, summary, default_topic)
                score = score_article(
                    title=title,
                    summary=summary,
                    published_at=published,
                    trust_tier=trust_tier,
                )
                read_time = estimate_read_time(summary) if summary else "3 min"

                article = {
                    "id": generate_id(link),
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "source_name": name,
                    "author": author if author else name,
                    "topic": topic,
                    "score": score,
                    "read_time": read_time,
                    "published_at": published.isoformat(),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "trust_tier": trust_tier,
                    "is_live": score >= MIN_SCORE,
                    "is_editors_pick": False,
                }

                articles.append(article)

            except Exception as e:
                print(f"  ⚠ Skipping entry in {name}: {e}")
                continue

        print(f"  ✓ {name}: {len(articles)} articles found")

    except urllib.error.HTTPError as e:
        print(f"  ✗ {name}: HTTP {e.code} — {e.reason}")
    except urllib.error.URLError as e:
        print(f"  ✗ {name}: Connection failed — {e.reason}")
    except Exception as e:
        print(f"  ✗ {name}: Error — {e}")

    return articles


def deduplicate(articles: list, seen_urls: set) -> list:
    """Remove duplicate articles by URL."""
    unique = []
    current_urls = set()

    for article in articles:
        url = article["url"]
        if url not in seen_urls and url not in current_urls:
            unique.append(article)
            current_urls.add(url)

    return unique


def select_editors_pick(articles: list) -> list:
    """Mark the highest-scoring article as editor's pick."""
    if not articles:
        return articles

    sorted_articles = sorted(
        articles,
        key=lambda a: (a["score"], -a["trust_tier"]),
        reverse=True
    )
    sorted_articles[0]["is_editors_pick"] = True
    return sorted_articles


def calculate_time_ago(published_at: str) -> str:
    """Convert an ISO timestamp to a human-readable time ago string."""
    try:
        pub = datetime.fromisoformat(published_at)
        now = datetime.now(timezone.utc)
        diff = now - pub
        hours = int(diff.total_seconds() / 3600)

        if hours < 1:
            return "just now"
        elif hours == 1:
            return "1h ago"
        elif hours < 24:
            return f"{hours}h ago"
        elif hours < 48:
            return "yesterday"
        else:
            days = hours // 24
            return f"{days}d ago"
    except Exception:
        return "today"


def run_scraper():
    """
    Main scraper pipeline:
    1. Load sources
    2. Fetch all RSS feeds with proper headers
    3. Deduplicate
    4. Sort by score
    5. Select editor's pick
    6. Save output
    """
    print("=" * 50)
    print("The Gospel Feed — Daily Scraper")
    print(f"Run time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    sources = load_sources()
    seen_urls = load_seen_urls()

    all_articles = []
    rss_sources = sources.get("sources", {}).get("rss", [])
    success_count = 0
    fail_count = 0

    print(f"\nFetching from {len(rss_sources)} RSS sources...\n")

    for source in rss_sources:
        articles = fetch_rss_source(source)
        if articles:
            success_count += 1
        else:
            fail_count += 1
        all_articles.extend(articles)

    print(f"\nSources: {success_count} succeeded, {fail_count} failed")
    print(f"Total RSS articles: {len(all_articles)}")

    # Fetch from YouTube channels
    youtube_articles = fetch_all_youtube(sources)
    all_articles.extend(youtube_articles)

    print(f"Total articles (RSS + YouTube): {len(all_articles)}")

    unique_articles = deduplicate(all_articles, seen_urls)
    print(f"After deduplication: {len(unique_articles)}")

    quality_articles = [a for a in unique_articles if a["is_live"]]
    print(f"After quality filter (score >= {MIN_SCORE}): {len(quality_articles)}")

    quality_articles.sort(key=lambda a: a["score"], reverse=True)
    quality_articles = select_editors_pick(quality_articles)

    for article in quality_articles:
        article["time_ago"] = calculate_time_ago(article["published_at"])

    new_seen = seen_urls | {a["url"] for a in all_articles}
    save_seen_urls(new_seen)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_articles": len(quality_articles),
        "sources_fetched": success_count,
        "sources_failed": fail_count,
        "editors_pick": next((a for a in quality_articles if a["is_editors_pick"]), None),
        "articles": quality_articles,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(quality_articles)} articles to {OUTPUT_FILE}")

    if quality_articles:
        pick = next((a for a in quality_articles if a["is_editors_pick"]), None)
        if pick:
            print(f"\n★ Editor's Pick: \"{pick['title']}\"")
            print(f"  Source: {pick['source_name']} | Score: {pick['score']} | Topic: {pick['topic']}")

        topics = {}
        for a in quality_articles:
            topics[a["topic"]] = topics.get(a["topic"], 0) + 1

        print(f"\nTopic breakdown:")
        for topic, count in sorted(topics.items(), key=lambda x: -x[1]):
            print(f"  {topic}: {count}")

    print(f"\n{'=' * 50}")
    print("Scraper run complete!")
    print(f"{'=' * 50}")

    return output


def lambda_handler(event, context):
    """AWS Lambda entry point."""
    result = run_scraper()
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Scraper completed successfully",
            "articles_count": result["total_articles"],
            "generated_at": result["generated_at"],
        })
    }


if __name__ == "__main__":
    run_scraper()
