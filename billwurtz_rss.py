import os
import re
import requests
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString

URL = "https://billwurtz.com/questions/questions.html"

print("Downloading page...")
html = requests.get(URL, timeout=30).text
soup = BeautifulSoup(html, "html.parser")

def norm(s):
    return re.sub(r"\s+", " ", s).strip()

def tag_kind(tag):
    name = (tag.name or "").lower()
    if name in {"dco", "qco", "white", "green"}:
        return name
    cls = tag.get("class") or []
    cls = [c.lower() for c in cls]
    if "dco" in cls: return "dco"
    if "qco" in cls: return "qco"
    if "white" in cls: return "white"
    if "green" in cls: return "green"
    return None

def is_timeish(s):
    s2 = s.lower().strip()
    return bool(re.match(r"^\d{1,2}:\d{2}(\s*(am|pm))?\.{0,2}$", s2))

items = []

current_dt = ""
q_parts = []
a_parts = []
has_link = False
mode = "seek_dt"

def flush():
    global current_dt, q_parts, a_parts, has_link, mode, items
    q = norm(" ".join(q_parts))
    a = norm(" ".join(a_parts))
    d = norm(current_dt)

    # remove duplicated question at start of answer
    if a.lower().startswith(q.lower()):
        a = a[len(q):].strip()

    # only save if no link inside
    if q and a and not has_link:
        items.append((d, q, a))

    current_dt = ""
    q_parts = []
    a_parts = []
    has_link = False
    mode = "seek_dt"

root = soup.body if soup.body else soup

for node in root.descendants:
    if isinstance(node, Tag):
        # detect real links
        if node.name == "a":
            has_link = True

        kind = tag_kind(node)
        if not kind:
            continue

        text = norm(node.get_text(" ", strip=True))
        if not text:
            continue

        if kind == "green":
            has_link = True
            continue

        if kind == "dco":
            if q_parts or a_parts:
                flush()
            current_dt = text
            mode = "seek_q"

        elif kind == "qco":
            q_parts.append(text)
            mode = "seek_a"

        elif kind == "white":
            a_parts.append(text)
            mode = "seek_a"

    elif isinstance(node, NavigableString):
        text = norm(str(node))
        if not text:
            continue
        if text.upper() == "PREVIOUS QUESTIONS":
            continue
        if is_timeish(text):
            continue
        if mode == "seek_a" and q_parts:
            a_parts.append(text)

if q_parts or a_parts:
    flush()

print("Parsed entries:", len(items))

fg = FeedGenerator()
fg.title("Bill Wurtz – Questions")
fg.link(href=URL)
fg.description("Unofficial RSS feed for Bill Wurtz questions")

for d, q, a in items[:2000]:
    fe = fg.add_entry()
    fe.title(q)
    if d:
        fe.description(f"{d}\n\nQ: {q}\n\nA: {a}")
    else:
        fe.description(f"Q: {q}\n\nA: {a}")
    fe.link(href=URL)
    fe.pubDate(datetime.now(timezone.utc))

out_path = os.path.join(os.getcwd(), "billwurtz_questions.xml")
fg.rss_file(out_path)

print("DONE. File created:", out_path)
