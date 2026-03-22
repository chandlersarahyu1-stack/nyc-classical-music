#!/usr/bin/env python3
"""
Fetches upcoming classical music events in NYC from the Ticketmaster Discovery API
and saves them to events.json for the website to display.

Run locally:  TICKETMASTER_API_KEY=your_key python fetch_events.py
Runs automatically via GitHub Actions every 6 hours.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("TICKETMASTER_API_KEY")
if not API_KEY:
    print("Error: TICKETMASTER_API_KEY environment variable is not set.")
    sys.exit(1)

BASE_URL = "https://app.ticketmaster.com/discovery/v2/events.json"


def fetch_all_events():
    all_events = []
    seen_ids = set()
    page = 0
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    while True:
        params = {
            "apikey": API_KEY,
            "genreName": "Classical",
            "city": "New York",
            "stateCode": "NY",
            "countryCode": "US",
            "size": 200,
            "page": page,
            "sort": "date,asc",
            "startDateTime": now_utc,
        }

        try:
            response = requests.get(BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"API request failed on page {page}: {e}")
            break

        if "_embedded" not in data or "events" not in data["_embedded"]:
            print(f"No more events found (page {page}).")
            break

        raw_events = data["_embedded"]["events"]
        print(f"Page {page}: received {len(raw_events)} events")

        for event in raw_events:
            event_id = event.get("id", "")
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)

            parsed = parse_event(event)
            if parsed:
                all_events.append(parsed)

        page_info = data.get("page", {})
        total_pages = page_info.get("totalPages", 1)
        if page >= total_pages - 1:
            break
        page += 1

    return all_events


def parse_event(event):
    try:
        name = event.get("name", "Untitled Event")
        ticket_url = event.get("url", "")
        event_id = event.get("id", "")

        # Date and time
        dates = event.get("dates", {})
        start = dates.get("start", {})
        date_str = start.get("localDate", "")
        time_str = start.get("localTime", "")
        time_tbd = start.get("timeTBA", False) or start.get("noSpecificTime", False)

        # Venue
        embedded = event.get("_embedded", {})
        venues = embedded.get("venues", [])
        venue_name = ""
        venue_address = ""
        if venues:
            v = venues[0]
            venue_name = v.get("name", "")
            addr = v.get("address", {})
            venue_address = addr.get("line1", "")

        # Performers / attractions
        attractions = embedded.get("attractions", [])
        performers = [a.get("name", "") for a in attractions if a.get("name")]

        # Price range
        price_ranges = event.get("priceRanges", [])
        min_price = None
        max_price = None
        if price_ranges:
            min_price = price_ranges[0].get("min")
            max_price = price_ranges[0].get("max")

        # Best image: prefer 16:9 ratio, 400-1200px wide
        images = event.get("images", [])
        image_url = ""
        best_width = 0
        for img in images:
            if img.get("ratio") == "16_9":
                w = img.get("width", 0)
                if 400 <= w <= 1200 and w > best_width:
                    image_url = img["url"]
                    best_width = w
        if not image_url and images:
            image_url = images[0].get("url", "")

        # Sub-genre (e.g., Symphony, Opera, Chamber Music)
        classifications = event.get("classifications", [])
        subgenre = ""
        if classifications:
            sg = classifications[0].get("subGenre", {})
            if sg:
                subgenre = sg.get("name", "")

        return {
            "id": event_id,
            "name": name,
            "date": date_str,
            "time": time_str,
            "time_tbd": time_tbd,
            "venue": venue_name,
            "venue_address": venue_address,
            "performers": performers,
            "min_price": min_price,
            "max_price": max_price,
            "ticket_url": ticket_url,
            "image_url": image_url,
            "subgenre": subgenre,
        }
    except Exception as e:
        print(f"Failed to parse event {event.get('id', '?')}: {e}")
        return None


if __name__ == "__main__":
    print("Fetching NYC classical music events from Ticketmaster...")
    events = fetch_all_events()
    print(f"\nTotal events fetched: {len(events)}")

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "count": len(events),
        "events": events,
    }

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("Saved to events.json")
