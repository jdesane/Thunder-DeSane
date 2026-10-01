#!/usr/bin/env python3
"""Seed a rained-out evening's work: reps the players can do at home.

Checklists, not questions — they tap what they finished and send it, so the
coach sees who got their work in before the weekend. Every item is either a
volume the coach set ("100 swings off the tee"), one of his own practice-plan
notes (the ball-four bat drop, leads and secondaries), or a gap the Part 1
worksheet actually exposed (the outside pitch, driving it the other way).
Nothing here invents technique: it sets counts and intent, not mechanics.

    python3 scripts/seed_worksheet_tonight.py
"""
import json, os, urllib.request

SUPA = "https://zyonidiybzrgklrmalbt.supabase.co"
KEY = os.environ.get("SUPABASE_ANON_KEY") or (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5b25pZGl5YnpyZ2tscm1hbGJ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3MTY5NzUsImV4cCI6MjA4ODI5Mjk3NX0."
    "5See-qjLkXA4CoJi9tNfcLAX_cdvZhPaxw8iViKM8S8")


def req(path, method='GET', body=None):
    r = urllib.request.Request(SUPA + "/rest/v1/" + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None)
    for k, v in [('apikey', KEY), ('Authorization', 'Bearer ' + KEY),
                 ('Content-Type', 'application/json'), ('Prefer', 'return=representation')]:
        r.add_header(k, v)
    with urllib.request.urlopen(r) as resp:
        t = resp.read().decode()
        return json.loads(t) if t.strip() else None


def checklist(qid, lead, items):
    return {"id": qid, "type": "check", "q": lead, "options": items}


SECTIONS = [
  {
    "id": "swings", "title": "Swings — about 15 minutes",
    "lead": "Use a tee if you have one. No tee is fine — dry swings in front of a mirror count, "
            "same numbers. Go slower than you think you need to.",
    "questions": [checklist("c1", "Tap each one as you finish it:", [
        "25 swings middle — line drives back up the middle",
        "50 swings with the ball set back and outside — drive it the other way",
        "25 two-strike swings — choke up, shorter swing",
        "Before each set, say your plan out loud",
    ])],
  },
  {
    "id": "arm", "title": "Arm and glove — about 10 minutes",
    "lead": "Garage, carport, driveway under cover — anywhere you can throw without getting soaked. "
            "If nobody is around to catch, a wall works.",
    "questions": [checklist("c2", "Tap each one as you finish it:", [
        "Play catch for 10 minutes",
        "20 throws aimed at your partner's chest",
        "20 quick exchanges — glove to hand, no wasted motion",
        "No partner: 30 throws against a wall",
    ])],
  },
  {
    "id": "feet", "title": "Feet — about 5 minutes, no equipment",
    "lead": "Living room floor. Nobody needs to watch you do these.",
    "questions": [checklist("c3", "Tap each one as you finish it:", [
        "20 secondary leads — your shuffles as the pitch comes in",
    ])],
  },
  {
    "id": "head", "title": "Head — about 10 minutes",
    "lead": "This is the part that actually decides Saturday.",
    "questions": [checklist("c4", "Tap each one as you finish it:", [
        "Read your answer sheet from Part 1",
        "Watch the videos on it",
        "Get a parent to quiz you: “when I say ___, show me what you do”",
        "Pick one term you flagged and learn it properly",
    ])],
  },
  {
    "id": "back", "title": "Last thing",
    "lead": "",
    "questions": [
      {"id": "t1", "type": "text",
       "q": "Anything you could not do tonight? Tell me what and why.",
       "hint": "No problem at all if you missed some — I just want to know what you got through."},
      {"id": "t2", "type": "text",
       "q": "One thing you want to be better at on Saturday.",
       "hint": "Anything. One sentence."},
    ],
  },
]

INTRO = ("No practice tonight. This is what it is instead.\n\n"
         "All of it fits in about forty minutes and none of it needs a field. Tap each thing as you "
         "finish it, then send it to me so I know who got their work in before Saturday.\n\n"
         "If you only have time for one section, make it the swings.")

row = {
  "slug": "tonight-rained-out",
  "week_of": "2026-10-01",
  "title": "Tonight's Work — Rained Out",
  "intro": INTRO,
  "sections": SECTIONS,
}

if req("team_worksheets?slug=eq.%s&select=id" % row["slug"]):
    req("team_worksheets?slug=eq.%s" % row["slug"], 'PATCH', {k: v for k, v in row.items() if k != "slug"})
    print("updated", row["slug"])
else:
    req("team_worksheets", 'POST', [row])
    print("created", row["slug"])

w = req("team_worksheets?slug=eq.%s&select=title,week_of,sections,published_at" % row["slug"])[0]
items = sum(len(q.get("options", [])) for s in w["sections"] for q in s["questions"] if q["type"] == "check")
print("%s — %d sections, %d tick-off items, %s"
      % (w["title"], len(w["sections"]), items, "PUBLISHED" if w["published_at"] else "not published"))
for s in w["sections"]:
    print("   %-36s %s" % (s["title"], " / ".join(
        (q.get("q") or "")[:28] if q["type"] != "check" else "%d items" % len(q["options"])
        for q in s["questions"])))
