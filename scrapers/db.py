"""
The Gospel Feed — DynamoDB Helper
Handles all read/write operations to the gospel-feed-articles table.
"""

import json
import boto3
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key


TABLE_NAME = "gospel-feed-articles"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def put_article(article: dict):
    """
    Write a single article to DynamoDB.

    Partition key: date (YYYY-MM-DD)
    Sort key: score_id (zero-padded score descending + article id)
    This makes querying "today's articles sorted by score" a single query.
    """
    # Extract date from published_at
    try:
        pub_date = article["published_at"][:10]  # "2026-05-31"
    except (KeyError, TypeError):
        pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Sort key: inverted score (so highest score comes first in DynamoDB)
    # DynamoDB sorts ascending, so 999 - score puts high scores first
    inverted_score = 999 - article.get("score", 50)
    score_id = f"{inverted_score:03d}#{article['id']}"

    item = {
        "date": pub_date,
        "score_id": score_id,
        "id": article["id"],
        "title": article["title"],
        "summary": article.get("summary", ""),
        "url": article["url"],
        "source_name": article["source_name"],
        "author": article.get("author", ""),
        "topic": article.get("topic", "faith"),
        "score": article.get("score", 50),
        "read_time": article.get("read_time", "3 min"),
        "published_at": article.get("published_at", ""),
        "scraped_at": article.get("scraped_at", ""),
        "trust_tier": article.get("trust_tier", 2),
        "is_live": article.get("is_live", True),
        "is_editors_pick": article.get("is_editors_pick", False),
        "is_video": article.get("is_video", False),
        "time_ago": article.get("time_ago", "today"),
    }

    # Remove empty strings (DynamoDB doesn't allow empty string attributes)
    item = {k: v for k, v in item.items() if v != ""}

    table.put_item(Item=item)


def put_articles(articles: list):
    """
    Write multiple articles to DynamoDB using batch writer.
    Much faster than individual put_item calls.
    """
    count = 0
    with table.batch_writer() as batch:
        for article in articles:
            try:
                # Extract date
                try:
                    pub_date = article["published_at"][:10]
                except (KeyError, TypeError):
                    pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                inverted_score = 999 - article.get("score", 50)
                score_id = f"{inverted_score:03d}#{article['id']}"

                item = {
                    "date": pub_date,
                    "score_id": score_id,
                    "id": article["id"],
                    "title": article["title"],
                    "url": article["url"],
                    "source_name": article["source_name"],
                    "topic": article.get("topic", "faith"),
                    "score": article.get("score", 50),
                    "read_time": article.get("read_time", "3 min"),
                    "published_at": article.get("published_at", ""),
                    "is_live": article.get("is_live", True),
                    "is_editors_pick": article.get("is_editors_pick", False),
                    "is_video": article.get("is_video", False),
                    "time_ago": article.get("time_ago", "today"),
                }

                # Add optional fields only if they have values
                if article.get("summary"):
                    item["summary"] = article["summary"]
                if article.get("author"):
                    item["author"] = article["author"]
                if article.get("scraped_at"):
                    item["scraped_at"] = article["scraped_at"]
                if article.get("trust_tier"):
                    item["trust_tier"] = article["trust_tier"]

                batch.put_item(Item=item)
                count += 1
            except Exception as e:
                print(f"  ⚠ Failed to write article {article.get('id', '?')}: {e}")

    return count


def get_articles_by_date(date_str: str, topic: str = None, limit: int = 50) -> list:
    """
    Get articles for a specific date, sorted by score (highest first).

    Args:
        date_str: Date string like "2026-05-31"
        topic: Optional topic filter
        limit: Max articles to return
    """
    response = table.query(
        KeyConditionExpression=Key("date").eq(date_str),
        Limit=limit,
    )

    articles = response.get("Items", [])

    # Convert DynamoDB number types to Python int
    for a in articles:
        a["score"] = int(a.get("score", 0))
        a["trust_tier"] = int(a.get("trust_tier", 2))
        a["is_live"] = a.get("is_live", True)
        a["is_editors_pick"] = a.get("is_editors_pick", False)
        a["is_video"] = a.get("is_video", False)

    # Filter by topic if specified
    if topic and topic != "all":
        articles = [a for a in articles if a.get("topic") == topic]

    # Filter to live articles only
    articles = [a for a in articles if a.get("is_live", True)]

    return articles


def get_articles_multi_day(days: int = 3, topic: str = None, limit: int = 50) -> list:
    """
    Get articles from the last N days, sorted by score.
    This ensures the feed always has content even if today's scrape is thin.
    """
    from datetime import timedelta

    all_articles = []
    today = datetime.now(timezone.utc)

    for i in range(days):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        day_articles = get_articles_by_date(date_str, topic)
        all_articles.extend(day_articles)

    # Sort by score descending
    all_articles.sort(key=lambda a: a.get("score", 0), reverse=True)

    # Deduplicate by URL (same article might appear on multiple dates)
    seen = set()
    unique = []
    for a in all_articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)

    return unique[:limit]


def get_editors_pick(days: int = 3) -> dict:
    """Get the current editor's pick (highest scoring article marked as pick)."""
    articles = get_articles_multi_day(days=days, limit=100)

    # First try to find an explicitly marked pick
    for a in articles:
        if a.get("is_editors_pick"):
            return a

    # Fallback to highest scoring article
    if articles:
        return articles[0]

    return None
