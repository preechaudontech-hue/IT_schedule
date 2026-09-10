"""LINE Messaging API client (push message)."""
from __future__ import annotations

import requests

PUSH_URL = "https://api.line.me/v2/bot/message/push"
REPLY_URL = "https://api.line.me/v2/bot/message/reply"


class LineError(RuntimeError):
    pass


def push_text(channel_access_token: str, to: str, text: str) -> None:
    """Push a single text message to a user/group/room id."""
    # LINE limits a single text message to 5000 characters.
    if len(text) > 5000:
        text = text[:4990] + "\n…(ตัดข้อความ)"

    resp = requests.post(
        PUSH_URL,
        headers={
            "Authorization": f"Bearer {channel_access_token}",
            "Content-Type": "application/json",
        },
        json={"to": to, "messages": [{"type": "text", "text": text}]},
        timeout=30,
    )
    if resp.status_code != 200:
        raise LineError(f"LINE push failed {resp.status_code}: {resp.text}")
