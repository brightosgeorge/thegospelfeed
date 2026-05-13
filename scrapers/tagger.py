"""
The Gospel Feed — Topic Tagger
Auto-assigns topic tags to articles based on keyword matching.
"""

# Topic keyword definitions
# Each topic has a list of keywords that, if found in the title or summary,
# trigger that topic tag. More specific keywords are weighted higher.

TOPIC_KEYWORDS = {
    "marriage": {
        "strong": ["marriage", "husband", "wife", "wedding", "spouse", "divorce", "marital"],
        "moderate": ["relationship", "couple", "family", "love", "partner", "intimacy", "forgiveness in marriage"],
        "weight_strong": 3,
        "weight_moderate": 1,
    },
    "grief": {
        "strong": ["grief", "mourning", "bereavement", "loss", "death", "funeral", "lament", "widow"],
        "moderate": ["suffering", "pain", "sorrow", "crying", "tears", "comfort", "healing"],
        "weight_strong": 3,
        "weight_moderate": 1,
    },
    "leadership": {
        "strong": ["leadership", "pastor", "elder", "deacon", "church planting", "ministry leader", "senior pastor"],
        "moderate": ["team", "management", "vision", "delegation", "burnout", "authority", "mentor", "stewardship"],
        "weight_strong": 3,
        "weight_moderate": 1,
    },
    "youth": {
        "strong": ["gen z", "teenager", "youth group", "youth ministry", "young adult", "college student"],
        "moderate": ["student", "campus", "generation", "millennial", "tiktok", "social media", "dating"],
        "weight_strong": 3,
        "weight_moderate": 1,
    },
    "devotional": {
        "strong": ["devotional", "quiet time", "morning prayer", "evening prayer", "daily reading", "meditation"],
        "moderate": ["scripture reading", "reflection", "journaling", "psalm", "proverb", "spiritual discipline"],
        "weight_strong": 3,
        "weight_moderate": 1,
    },
    "sermon": {
        "strong": ["sermon", "preaching", "preach", "sunday message", "pulpit", "homily", "expository"],
        "moderate": ["church service", "worship service", "message series", "bible teaching"],
        "weight_strong": 3,
        "weight_moderate": 1,
    },
    "faith": {
        "strong": ["faith", "believe", "gospel", "salvation", "jesus", "christ", "god", "holy spirit"],
        "moderate": ["prayer", "worship", "bible", "scripture", "church", "christian", "theology", "grace",
                     "mercy", "redemption", "sin", "repentance", "forgiveness", "eternal", "heaven",
                     "resurrection", "cross", "baptism", "communion"],
        "weight_strong": 2,
        "weight_moderate": 1,
    },
}


def tag_topic(title: str, summary: str = "", default_topic: str = "faith") -> str:
    """
    Determine the best topic tag for an article based on its title and summary.

    Args:
        title: Article title
        summary: Article summary/description (optional)
        default_topic: Fallback topic from the source config

    Returns:
        The best matching topic string
    """
    text = f"{title} {summary}".lower()
    scores = {}

    for topic, config in TOPIC_KEYWORDS.items():
        score = 0

        # Check strong keywords
        for keyword in config["strong"]:
            if keyword.lower() in text:
                score += config["weight_strong"]

        # Check moderate keywords
        for keyword in config["moderate"]:
            if keyword.lower() in text:
                score += config["weight_moderate"]

        if score > 0:
            scores[topic] = score

    if not scores:
        return default_topic

    # Return the topic with the highest score
    # If there's a tie, prefer the more specific topic (non-faith)
    max_score = max(scores.values())
    best_topics = [t for t, s in scores.items() if s == max_score]

    # Prefer specific topics over "faith" in ties
    if len(best_topics) > 1 and "faith" in best_topics:
        best_topics.remove("faith")

    return best_topics[0]


def get_all_topics() -> list:
    """Return list of all valid topic names."""
    return list(TOPIC_KEYWORDS.keys())
