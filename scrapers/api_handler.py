"""
The Gospel Feed — API Lambda Handler
Serves articles from DynamoDB to the frontend.

Endpoints (via API Gateway):
  GET /feed              — all articles from last 3 days
  GET /feed?topic=faith  — filtered by topic
  GET /pick              — editor's pick
"""

import json
from db import get_articles_multi_day, get_editors_pick


def lambda_handler(event, context):
    """
    Main API handler. Routes based on path and query parameters.
    """
    # Get the request path and query params
    path = event.get("rawPath", event.get("path", "/feed"))
    params = event.get("queryStringParameters") or {}

    # CORS headers (required for frontend to call the API)
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    # Handle OPTIONS preflight
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        if "/pick" in path:
            # GET /pick — return editor's pick
            pick = get_editors_pick(days=3)
            if pick:
                body = {"editors_pick": pick}
            else:
                body = {"editors_pick": None, "message": "No editor's pick available"}

        else:
            # GET /feed — return all articles (optionally filtered)
            topic = params.get("topic", "all")
            limit = min(int(params.get("limit", "50")), 100)

            articles = get_articles_multi_day(days=3, topic=topic, limit=limit)

            # Find editor's pick from the results
            pick = None
            for a in articles:
                if a.get("is_editors_pick"):
                    pick = a
                    break
            if not pick and articles:
                pick = articles[0]

            body = {
                "total_articles": len(articles),
                "topic": topic,
                "editors_pick": pick,
                "articles": articles,
            }

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(body, default=str),
        }

    except Exception as e:
        print(f"API error: {e}")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Internal server error"}),
        }
