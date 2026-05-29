"""
The Gospel Feed — Weekly Digest Sender
Compiles the top 7 articles from feed.json and sends them
as a formatted email newsletter via Brevo (Sendinblue) API.

Triggered by GitHub Actions every Sunday at 7 AM UTC.

Requires BREVO_API_KEY environment variable.
"""

import json
import os
import urllib.request
import ssl
from datetime import datetime, timezone
from pathlib import Path


# ─── Configuration ───

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_API_URL = "https://api.brevo.com/v3/emailCampaigns"
FEED_FILE = Path(__file__).parent / "output" / "feed.json"
LIST_ID = 3  # Your Brevo contact list ID
SENDER_NAME = "The Gospel Feed"
SENDER_EMAIL = "digest@thegospelfeed.com"  # Must be verified in Brevo


def load_feed() -> dict:
    """Load the current feed.json."""
    with open(FEED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_top_articles(feed: dict, count: int = 7) -> list:
    """Get the top N articles by score."""
    articles = feed.get("articles", [])
    # Filter to live articles and sort by score
    live = [a for a in articles if a.get("is_live", True)]
    live.sort(key=lambda a: a.get("score", 0), reverse=True)
    return live[:count]


def build_email_html(articles: list) -> str:
    """
    Build a beautiful HTML email template for the weekly digest.
    Uses inline styles for maximum email client compatibility.
    """
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Topic color mapping
    topic_colors = {
        "faith": "#1D4ED8",
        "devotional": "#047857",
        "leadership": "#B45309",
        "marriage": "#6D28D9",
        "grief": "#BE123C",
        "youth": "#15803D",
        "sermon": "#1D4ED8",
    }

    # Build article cards
    article_cards = ""
    for i, article in enumerate(articles):
        topic = article.get("topic", "faith")
        color = topic_colors.get(topic, "#1D4ED8")
        is_pick = article.get("is_editors_pick", False)

        pick_badge = ""
        if is_pick:
            pick_badge = '''
            <span style="display:inline-block;background:#D4AF37;color:#0A1628;font-size:10px;font-weight:600;
            letter-spacing:0.08em;text-transform:uppercase;padding:3px 10px;border-radius:50px;margin-bottom:8px;">
            Editor's Pick</span><br>
            '''

        article_cards += f'''
        <tr>
          <td style="padding:20px 0;border-bottom:1px solid #EDEAE3;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="width:32px;vertical-align:top;padding-right:12px;">
                  <span style="font-family:Georgia,serif;font-size:24px;font-weight:300;color:#D8D4CC;line-height:1;">
                    {i + 1}
                  </span>
                </td>
                <td>
                  {pick_badge}
                  <span style="display:inline-block;font-size:10px;font-weight:600;letter-spacing:0.08em;
                  text-transform:uppercase;color:{color};margin-bottom:6px;">{topic}</span>
                  <br>
                  <a href="{article['url']}" style="font-family:Georgia,serif;font-size:17px;color:#1A1814;
                  text-decoration:none;line-height:1.4;display:block;margin:4px 0 8px;">
                    {article['title']}
                  </a>
                  <span style="font-size:13px;color:#8A8480;">
                    {article.get('source_name', '')} &middot; {article.get('read_time', '5 min')}
                  </span>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        '''

    # Full email template
    html = f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin:0;padding:0;background-color:#FDFBF7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#FDFBF7;">
        <tr>
          <td align="center" style="padding:20px 16px;">
            <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

              <!-- Header -->
              <tr>
                <td style="background:#0A1628;border-radius:16px 16px 0 0;padding:32px 28px;text-align:center;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td align="center">
                        <span style="display:inline-block;width:36px;height:36px;background:linear-gradient(135deg,#D4AF37,#F0D675);
                        border-radius:8px;line-height:36px;text-align:center;font-size:18px;color:#0A1628;font-weight:bold;">✝</span>
                      </td>
                    </tr>
                    <tr>
                      <td align="center" style="padding-top:12px;">
                        <span style="font-size:22px;font-weight:500;color:#FFFFFF;font-family:Georgia,serif;">
                          The Sunday Digest
                        </span>
                      </td>
                    </tr>
                    <tr>
                      <td align="center" style="padding-top:6px;">
                        <span style="font-size:13px;color:rgba(255,255,255,0.45);">
                          The 7 best Christian reads this week &middot; {today}
                        </span>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- Greeting -->
              <tr>
                <td style="background:#FFFFFF;padding:28px 28px 16px;">
                  <span style="font-size:15px;color:#4A453E;line-height:1.7;">
                    Good morning! Here are the 7 most impactful pieces of Christian content from this week,
                    handpicked from the world's most trusted sources. Click any article to read the full piece.
                  </span>
                </td>
              </tr>

              <!-- Articles -->
              <tr>
                <td style="background:#FFFFFF;padding:0 28px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    {article_cards}
                  </table>
                </td>
              </tr>

              <!-- CTA -->
              <tr>
                <td style="background:#FFFFFF;padding:28px;text-align:center;">
                  <a href="https://thegospelfeed.com" style="display:inline-block;background:linear-gradient(135deg,#D4AF37,#F0D675);
                  color:#0A1628;font-size:14px;font-weight:600;padding:12px 32px;border-radius:50px;text-decoration:none;">
                    See the full daily feed →
                  </a>
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="background:#0A1628;border-radius:0 0 16px 16px;padding:24px 28px;text-align:center;">
                  <span style="font-size:12px;color:rgba(255,255,255,0.35);line-height:1.7;">
                    You're receiving this because you subscribed to The Sunday Digest.<br>
                    <a href="{{{{unsubscribe}}}}" style="color:#D4AF37;text-decoration:underline;">Unsubscribe</a>
                    &middot;
                    <a href="https://thegospelfeed.com" style="color:#D4AF37;text-decoration:underline;">Visit The Gospel Feed</a>
                  </span>
                  <br><br>
                  <span style="font-size:11px;color:rgba(255,255,255,0.2);">
                    © 2026 The Gospel Feed &middot; Made with faith in Lagos, Nigeria
                  </span>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    '''

    return html


def build_plain_text(articles: list) -> str:
    """Build a plain text version of the digest."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    lines = [
        f"THE SUNDAY DIGEST — {today}",
        "The 7 best Christian reads this week",
        "=" * 40,
        "",
        "Good morning! Here are this week's top picks:",
        "",
    ]

    for i, article in enumerate(articles):
        pick = " ★ EDITOR'S PICK" if article.get("is_editors_pick") else ""
        lines.append(f"{i+1}. [{article.get('topic', '').upper()}]{pick}")
        lines.append(f"   {article['title']}")
        lines.append(f"   {article.get('source_name', '')} · {article.get('read_time', '')}")
        lines.append(f"   Read: {article['url']}")
        lines.append("")

    lines.extend([
        "─" * 40,
        "See the full daily feed: https://thegospelfeed.com",
        "",
        "You're receiving this because you subscribed to The Sunday Digest.",
        "Unsubscribe: {{unsubscribe}}",
    ])

    return "\n".join(lines)


def create_and_send_campaign(articles: list):
    """
    Create and immediately send an email campaign via Brevo API.
    """
    if not BREVO_API_KEY:
        print("✗ BREVO_API_KEY not set — cannot send digest")
        return False

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = f"The Sunday Digest — {today}"

    html_content = build_email_html(articles)
    text_content = build_plain_text(articles)

    # Create the campaign
    campaign_data = {
        "name": f"Sunday Digest {today}",
        "subject": subject,
        "sender": {
            "name": SENDER_NAME,
            "email": SENDER_EMAIL,
        },
        "recipients": {
            "listIds": [LIST_ID],
        },
        "htmlContent": html_content,
        "textContent": text_content,
        "inlineImageActivation": False,
        "sendAtBestTime": False,
    }

    ctx = ssl.create_default_context()
    headers = {
        "Content-Type": "application/json",
        "api-key": BREVO_API_KEY,
        "Accept": "application/json",
    }

    # Step 1: Create campaign
    print("Creating email campaign...")
    try:
        req = urllib.request.Request(
            BREVO_API_URL,
            data=json.dumps(campaign_data).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))
        campaign_id = result.get("id")
        print(f"✓ Campaign created: ID {campaign_id}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"✗ Failed to create campaign: HTTP {e.code}")
        print(f"  Error: {error_body}")
        return False

    # Step 2: Send the campaign immediately
    print("Sending campaign...")
    try:
        send_url = f"{BREVO_API_URL}/{campaign_id}/sendNow"
        req = urllib.request.Request(
            send_url,
            headers=headers,
            method="POST",
        )
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        print(f"✓ Campaign sent successfully!")
        return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"✗ Failed to send campaign: HTTP {e.code}")
        print(f"  Error: {error_body}")
        return False


def run_digest():
    """Main digest pipeline."""
    print("=" * 50)
    print("The Gospel Feed — Sunday Digest Sender")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    # Load feed
    if not FEED_FILE.exists():
        print("✗ No feed.json found — run the scraper first")
        return

    feed = load_feed()
    print(f"\nFeed has {feed.get('total_articles', 0)} articles")

    # Get top 7
    top_articles = get_top_articles(feed, 7)
    print(f"Selected top {len(top_articles)} articles for digest")

    if not top_articles:
        print("✗ No articles to send — skipping digest")
        return

    # Print preview
    print("\nDigest preview:")
    for i, a in enumerate(top_articles):
        pick = " ★" if a.get("is_editors_pick") else ""
        print(f"  {i+1}. [{a['topic']}] {a['title'][:60]}...{pick}")
        print(f"     {a['source_name']} · Score: {a['score']}")

    # Send
    print()
    success = create_and_send_campaign(top_articles)

    if success:
        print(f"\n{'=' * 50}")
        print("Sunday Digest sent successfully! 🙏")
        print(f"{'=' * 50}")
    else:
        print(f"\n{'=' * 50}")
        print("Digest send failed — check errors above")
        print(f"{'=' * 50}")


# ─── Lambda handler ───

def lambda_handler(event, context):
    """AWS Lambda entry point."""
    run_digest()
    return {"statusCode": 200, "body": "Digest sent"}


if __name__ == "__main__":
    run_digest()
