#!/usr/bin/env python3
"""Bump the build stamp in index.html and version.txt together.

    python3 scripts/bump_build.py            # next stamp for today
    python3 scripts/bump_build.py 2026-10-01.3

The two must always match: the installed app compares the <meta name="build">
tag in the page it is running against version.txt fetched from the server, and
offers a reload when they differ. If version.txt moves and the meta tag does
not, every reload serves a page that still disagrees and the update banner
never goes away — pressing "Update now" can never fix it. That has happened
once, from a hand-edit that searched for a stamp another session had already
changed. This writes both or fails, so they cannot drift.
"""
import datetime, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX, VERSION = ROOT / "index.html", ROOT / "version.txt"
TAG = re.compile(r'(<meta name="build" content=")([^"]*)(">)')

html = INDEX.read_text()
m = TAG.search(html)
if not m:
    sys.exit("No <meta name=\"build\"> tag in index.html — cannot bump.")
current = m.group(2)
old_version = VERSION.read_text().strip()

if len(sys.argv) > 1:
    new = sys.argv[1]
else:
    today = datetime.date.today().isoformat()
    used = [s for s in (current, old_version) if s.startswith(today + ".")]
    n = max((int(s.rsplit(".", 1)[1]) for s in used if s.rsplit(".", 1)[1].isdigit()), default=0)
    new = f"{today}.{n + 1}"

INDEX.write_text(TAG.sub(lambda _: m.group(1) + new + m.group(3), html, count=1))
VERSION.write_text(new + "\n")

check = TAG.search(INDEX.read_text()).group(2)
if check != new or VERSION.read_text().strip() != new:
    sys.exit(f"Write-back check failed: meta={check!r} version.txt={VERSION.read_text().strip()!r}")
print(f"index.html  {current} -> {new}")
print(f"version.txt {old_version} -> {new}")
if current != old_version:
    print(f"(they had drifted apart — the page said {current}, version.txt said {old_version})")
