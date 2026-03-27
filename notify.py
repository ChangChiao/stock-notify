import json
import os
import sys
from datetime import datetime, timedelta

import requests

WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


def load_stocks():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "matched_stocks.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_egift_ids():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "egift.json")
    with open(path, encoding="utf-8") as f:
        return {item["id"] for item in json.load(f)}


def deduplicate(stocks):
    seen = set()
    result = []
    for s in stocks:
        key = (s["id"], s["meeting_start"], s["meeting_end"])
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def filter_stocks(stocks, today):
    upcoming = []
    in_progress = []

    for s in stocks:
        start = datetime.strptime(s["meeting_start"], "%Y-%m-%d").date()
        end = datetime.strptime(s["meeting_end"], "%Y-%m-%d").date()

        if today < start <= today + timedelta(days=7):
            upcoming.append(s)
        elif start <= today <= end:
            in_progress.append(s)

    upcoming.sort(key=lambda s: s["meeting_start"])
    in_progress.sort(key=lambda s: s["meeting_end"])

    return upcoming, in_progress


def format_stock(s, egift_ids):
    text = f"📌 {s['id']} {s['name']}\n🎁 {s['gift']}\n📆 買進期間：{s['meeting_start']} ~ {s['meeting_end']}"
    if s["id"] in egift_ids:
        text += "\n⚠️支援eGift"
    return text


def format_message(upcoming, in_progress, today, egift_ids):
    weekday = WEEKDAYS[today.weekday()]
    lines = [
        f"📋 股東會紀念品通知",
        f"📅 {today.strftime('%Y-%m-%d')}（{weekday}）",
    ]

    if upcoming:
        lines.append("")
        lines.append("⏰ 即將開始（7日內）")
        lines.append("—————————————")
        for s in upcoming:
            lines.append(format_stock(s, egift_ids))
            lines.append("")

    if in_progress:
        lines.append("")
        lines.append("🔔 進行中（可買進）")
        lines.append("—————————————")
        for s in in_progress:
            lines.append(format_stock(s, egift_ids))
            lines.append("")

    total = len(upcoming) + len(in_progress)
    lines.append(f"✅ 本期共 {total} 檔符合通知條件")

    return "\n".join(lines)


def send_line_message(text, token, user_id):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Split into chunks if message exceeds LINE's 5000 char limit
    if len(text) <= 5000:
        messages = [{"type": "text", "text": text}]
    else:
        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > 4800:
                chunks.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line
        if current:
            chunks.append(current)
        messages = [{"type": "text", "text": chunk} for chunk in chunks]

    # LINE push API allows max 5 messages per request
    for i in range(0, len(messages), 5):
        batch = messages[i : i + 5]
        body = {"to": user_id, "messages": batch}
        resp = requests.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            print(f"LINE API error: {resp.status_code} {resp.text}")
            sys.exit(1)


def main():
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")

    if not token or not user_id:
        print("Error: LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID must be set")
        sys.exit(1)

    stocks = load_stocks()
    stocks = deduplicate(stocks)
    egift_ids = load_egift_ids()
    today = datetime.now().date()

    upcoming, in_progress = filter_stocks(stocks, today)

    if not upcoming and not in_progress:
        print("No stocks match notification criteria. Skipping notification.")
        return

    message = format_message(upcoming, in_progress, today, egift_ids)
    send_line_message(message, token, user_id)
    print(f"Notification sent. Upcoming: {len(upcoming)}, In progress: {len(in_progress)}")


if __name__ == "__main__":
    main()
