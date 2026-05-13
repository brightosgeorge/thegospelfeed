"""
The Gospel Feed — Content Scorer
Ranks articles by quality using recency, source trust, and content signals.
"""

import math
from datetime import datetime, timezone


# Trust tier score bonuses
TRUST_BONUS = {
    1: 20,  # Premier sources (Desiring God, TGC, etc.)
    2: 10,  # Trusted sources
    3: 0,   # New/unvetted sources
}

# Maximum possible score is ~100


def score_article(
    title: str,
    summary: str,
    published_at: datetime,
    trust_tier: int = 2,
    engagement: int = 0,
) -> int:
    """
    Calculate a quality score (0-100) for an article.

    Scoring breakdown:
    - Recency (0-40 points): Newer articles score higher, decays over 48 hours
    - Source trust (0-20 points): Based on trust tier from sources.yaml
    - Title quality (0-20 points): Length, no clickbait, has substance
    - Content signals (0-20 points): Has summary, engagement, read time indicators

    Args:
        title: Article title
        summary: Article summary/description
        published_at: When the article was published (timezone-aware)
        trust_tier: Source trust tier (1=premier, 2=trusted, 3=new)
        engagement: External engagement count if available (likes, shares, etc.)

    Returns:
        Integer score from 0-100
    """
    score = 0.0

    # ─── Recency score (0-40 points) ───
    now = datetime.now(timezone.utc)
    hours_old = max(0, (now - published_at).total_seconds() / 3600)

    if hours_old <= 6:
        recency = 40  # Fresh content gets full marks
    elif hours_old <= 24:
        recency = 40 - (hours_old - 6) * (20 / 18)  # Linear decay: 40 → 20
    elif hours_old <= 48:
        recency = 20 - (hours_old - 24) * (15 / 24)  # Slower decay: 20 → 5
    else:
        recency = max(0, 5 - (hours_old - 48) * 0.05)  # Trickle down to 0

    score += recency

    # ─── Source trust score (0-20 points) ───
    score += TRUST_BONUS.get(trust_tier, 0)

    # ─── Title quality score (0-20 points) ───
    title_score = 0

    # Good title length (40-100 chars is ideal)
    title_len = len(title)
    if 40 <= title_len <= 100:
        title_score += 8
    elif 20 <= title_len < 40:
        title_score += 5
    elif title_len > 100:
        title_score += 4
    else:
        title_score += 2

    # Penalize clickbait patterns
    clickbait_patterns = [
        "you won't believe", "shocking", "click here", "!!!",
        "this one trick", "doctors hate", "number 5 will",
        "what happens next", "gone wrong", "exposed",
    ]
    is_clickbait = any(p in title.lower() for p in clickbait_patterns)
    if is_clickbait:
        title_score -= 5

    # Bonus for substantive titles (contain colons or dashes = structured)
    if ":" in title or " — " in title or " - " in title:
        title_score += 4

    # Bonus for question titles (engaging)
    if title.strip().endswith("?"):
        title_score += 3

    # Bonus for capitalized properly (not ALL CAPS)
    if title == title.upper() and len(title) > 10:
        title_score -= 3  # ALL CAPS penalty

    title_score = max(0, min(20, title_score))
    score += title_score

    # ─── Content signals score (0-20 points) ───
    content_score = 0

    # Has a summary
    if summary and len(summary) > 50:
        content_score += 8
    elif summary and len(summary) > 20:
        content_score += 4

    # Engagement bonus (logarithmic scale)
    if engagement > 0:
        content_score += min(8, int(math.log10(engagement + 1) * 3))

    # Summary suggests depth (longer = more substantial)
    if summary and len(summary) > 200:
        content_score += 4
    elif summary and len(summary) > 100:
        content_score += 2

    content_score = min(20, content_score)
    score += content_score

    # ─── Final score ───
    return max(0, min(100, int(round(score))))


def estimate_read_time(text: str) -> str:
    """
    Estimate reading time from text content.
    Average reading speed: ~200 words per minute.

    Returns string like "5 min"
    """
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return f"{minutes} min"
