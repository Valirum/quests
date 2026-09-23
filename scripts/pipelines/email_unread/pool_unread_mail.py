#!/usr/bin/env python3
"""emit_pool_command for the daily unread-mail quest template.

Logs into WorldClient (MDaemon webmail) the same way the web UI does —
IMAP (993/143) is closed on this server, HTTP is the only option — lists
unread messages in the inbox, and prints a JSON array on stdout in the
shape quests' emit_pool expects:

  [{"title": "...", "description": "...", "weight": 1, "ref": "mail:<id>"}]

`ref` is the message id, so quests' own anti-repeat (picked_refs history
in templateemitroll) keeps already-surfaced mail from reappearing in a
later roll even if it's still unread server-side.

Deliberately does NOT fetch message bodies: opening a message via
View=Message marks it read server-side (confirmed by hand — this is not
a browser-only quirk, the webmail and this script hit the same endpoint),
so pulling bodies here would silently mark every listed message read just
for a description preview. Title-only (from/subject/date) keeps the read
count on the actual mailbox honest; open the real message to read it.

See note=6 in the quests journal for the endpoint reference this is
built from (login/list/body-fetch quirks, non-strict-JSON parsing, etc).

Requires a .env next to this file (see .env.example):
  MAIL_HOST, MAIL_USER, MAIL_PASSWORD
"""
import http.cookiejar
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def load_env(path=".env"):
    env = {}
    p = Path(__file__).parent / path
    if not p.exists():
        print(f"missing {p} — copy .env.example to .env and fill it in", file=sys.stderr)
        sys.exit(1)
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def make_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def login(opener, host, user, password):
    url = f"https://{host}/WorldClient.dll?View=Main"
    data = urllib.parse.urlencode({"User": user, "Password": password}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    resp = opener.open(req, timeout=15)
    body = resp.read().decode("utf-8", errors="replace")
    m = re.search(r"Session=([A-Za-z0-9]+)", resp.geturl()) or re.search(
        r"Session=([A-Za-z0-9]+)", body
    )
    if not m:
        print("login failed: no Session id in response — check credentials", file=sys.stderr)
        sys.exit(1)
    return m.group(1)


def fetch_unread(opener, host, session_id):
    url = (
        f"https://{host}/WorldClient.dll?Session={session_id}&View=List"
        f"&ReturnJavaScript=1&FolderID=0&Sort=RevDate&Page=1&ContentType=javascript&UTF8=1"
    )
    # Must be POST — GET with the same params returns an empty body.
    req = urllib.request.Request(url, data=b"", method="POST")
    resp = opener.open(req, timeout=15)
    body = resp.read().decode("utf-8", errors="replace")

    messages = []
    for block in re.findall(r"\{[^{}]*\"id\"[^{}]*\}", body):

        def field(name, cast=str):
            fm = re.search(rf'"{name}"\s*:\s*"?([^",}}]*)"?', block)
            return cast(fm.group(1)) if fm else None

        messages.append(
            {
                "id": field("id"),
                "unread": field("unr", int) == 1,
                "from": field("frm"),
                "subject": field("sbj"),
                "date": field("dt"),
            }
        )
    return [m for m in messages if m["unread"]]


def main():
    env = load_env()
    opener = make_opener()
    session_id = login(opener, env["MAIL_HOST"], env["MAIL_USER"], env["MAIL_PASSWORD"])
    unread = fetch_unread(opener, env["MAIL_HOST"], session_id)

    pool = [
        {
            "title": f"{m['from'] or '?'}: {m['subject'] or '(без темы)'}",
            "description": f"Получено: {m['date'] or '?'}",
            "weight": 1,
            "ref": f"mail:{m['id']}",
        }
        for m in unread
        if m["id"]
    ]
    print(json.dumps(pool, ensure_ascii=False))


if __name__ == "__main__":
    main()
