#!/usr/bin/env python3
"""Seed the two offense + mindset worksheets.

Every term and every definition here is the coach's, from the glossary he
supplied. The questions only rephrase his definitions into choices an 8- or
9-year-old can answer. Nothing about hitting philosophy is invented: the
approach section is his own on-deck / outside-pitch example, question by
question.

Part 1 is the twenty that cost the team runs right now — the approach, the
leads, and the two plays that gave away bases against West Boca. Part 2 is
the swing cues and the more situational reads, for the following week.

    python3 scripts/seed_worksheet_offense.py
"""
import json, os, urllib.request

SUPA = "https://zyonidiybzrgklrmalbt.supabase.co"
KEY = os.environ.get("SUPABASE_ANON_KEY") or (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5b25pZGl5YnpyZ2tscm1hbGJ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3MTY5NzUsImV4cCI6MjA4ODI5Mjk3NX0."
    "5See-qjLkXA4CoJi9tNfcLAX_cdvZhPaxw8iViKM8S8")
NOT_SURE = "I'm not sure yet"


def req(path, method='GET', body=None, prefer='return=representation'):
    r = urllib.request.Request(SUPA + "/rest/v1/" + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None)
    for k, v in [('apikey', KEY), ('Authorization', 'Bearer ' + KEY),
                 ('Content-Type', 'application/json'), ('Prefer', prefer)]:
        r.add_header(k, v)
    with urllib.request.urlopen(r) as resp:
        t = resp.read().decode()
        return json.loads(t) if t.strip() else None


def mc(qid, q, options, answer):
    return {"id": qid, "type": "choice", "q": q, "options": options + [NOT_SURE], "answer": answer}


def wr(qid, q, hint=''):
    return {"id": qid, "type": "text", "q": q, "hint": hint}


# ---------------------------------------------------------------- PART ONE
P1_PLATE = [
  mc("p1", "“Have an approach” means…", [
     "Walk up there and see what happens",
     "Go up with a plan for which pitch you want to swing at",
     "Swing at the first pitch every time"], 1),
  mc("p2", "“Two-strike approach” means…", [
     "Swing at every single pitch",
     "Simplify, compete, and be ready to hit anything that could be called a strike",
     "Stop swinging and hope for a walk"], 1),
  mc("p5", "“Protect the plate” with two strikes means…", [
     "Swing at everything no matter where it is",
     "Be ready to swing at anything close enough to be strike three — but not at everything",
     "Stand in front of home plate"], 1),
  mc("p6", "“Don’t chase” means…", [
     "Don’t run to first base",
     "Let pitches outside the strike zone go by",
     "Don’t swing at all"], 1),
  mc("p10", "“A quality at-bat” means…", [
     "You got a hit",
     "You made good decisions and competed — even if you made an out",
     "You didn’t strike out"], 1),
]

P1_APPROACH = [
  wr("a1", "You’re on deck. The pitcher is pitching to the batter in front of you. Name two things you should be watching.",
     "Think about what you could learn before you even step in."),
  wr("a2", "The pitcher has thrown 6 of his last 8 pitches outside. You’re up next. What is your plan when you step in the box?",
     "Where are you looking, and where are you trying to hit it?"),
  mc("a3", "It’s 0–0. Your plan is to look for the outside pitch and drive it the other way. He throws it inside for a strike. What do you do?", [
     "Swing — it was a strike",
     "Take it, and stay with the plan: keep looking for the outside pitch",
     "Step out and change your whole plan"], 1),
  wr("a4", "Now you have two strikes. What changes about your plan?",
     "What are you doing differently than you were at 0–0?"),
  wr("a6", "In your own words: what is the difference between having a good at-bat and getting a hit?"),
]

P1_BASES = [
  mc("b1", "Your “primary lead” is…", [
     "The steps you take after the pitch is on the way",
     "Your starting spot off the base before the pitch",
     "The first base you run to"], 1),
  mc("b2", "Your “secondary lead” is…", [
     "The lead you take before the pitcher starts",
     "Extra controlled steps toward the next base as the pitch comes in, ready to go or get back",
     "A second chance to steal"], 1),
  mc("b4", "You’re on third with one out. Fly ball to the outfield. What do you do?", [
     "Take off as soon as it’s hit",
     "Get back to the bag, tag up, and go when he catches it",
     "Go halfway and wait"], 1),
  mc("b8", "You hit a ground ball to the second baseman. What do you do?", [
     "Jog, in case he makes the play",
     "Run hard all the way through first base",
     "Slow down if it looks like an out"], 1),
  mc("b9", "Ball four. What do you do with your bat?", [
     "Walk toward the dugout so you can toss it in, then go to first",
     "Drop it right where you are and get down the line",
     "Carry it with you to first base"], 1),
  wr("b10", "Why does that matter? What could happen while you’re worrying about your bat?"),
]

P1_MIND = [
  mc("m3", "“Flush it” or “reset” means…", [
     "Keep thinking about the mistake so you don’t do it again",
     "Let the last play go and get ready for the next one",
     "Go get a drink of water"], 1),
  mc("m4", "“Control what you can control” means…", [
     "Try to control the umpire’s calls",
     "Focus on your effort, your preparation, your decisions and your attitude",
     "Control the other team"], 1),
]

P1_TERMS = [
  "Have an approach", "Two-strike approach", "Hitter's count", "Pitcher's count", "Know the count",
  "Full count", "Protect the plate", "Hunt your pitch", "Be aggressive", "Be selective", "Don't chase",
  "Take a pitch", "Green light", "Quality at-bat", "Put the ball in play", "Make an adjustment",
  "Get your lead / primary lead", "Secondary lead", "Get a good jump", "Tag up", "Go halfway",
  "Run through first", "Pick up your coach", "Find the ball", "Back!", "Get down!", "Run it out",
  "Don't get doubled up", "Stay on the bag",
  "On deck", "In the hole", "Get your sign", "Stay in the game", "Pick up your teammate",
  "Reset / flush it", "Next-pitch mentality", "Control what you can control", "Good body language",
  "Be coachable",
]

# ---------------------------------------------------------------- PART TWO
P2_PLATE = [
  mc("p3", "Which one of these is a hitter’s count?", ["0–2", "2–0 or 3–1", "1–2"], 1),
  mc("p4", "Which one of these is a pitcher’s count?", ["3–1", "0–2 or 1–2", "3–0"], 1),
  mc("p7", "“Let it travel” means…", [
     "Swing as early as you can",
     "Let the pitch get deeper before you hit it — usually on an outside pitch",
     "Let the ball go all the way past you"], 1),
  mc("p8", "“Stay back” means…", [
     "Stand farther away from the plate",
     "Don’t lunge forward before you’re ready to swing",
     "Stay behind the batter’s box"], 1),
  mc("p9", "You bat right-handed. “Go the other way” means you’re trying to hit it…", [
     "To left field", "To right field", "Straight back up the middle"], 1),
  mc("p11", "“Battle” or “fight it off” with two strikes means…", [
     "Argue with the umpire",
     "Keep competing — even a foul ball keeps your at-bat alive",
     "Swing as hard as you possibly can"], 1),
]

P2_BASES = [
  mc("b3", "“Read the pitcher” means…", [
     "Read the number on his jersey",
     "Watch what his body does so you know if he’s pitching or throwing over",
     "Guess when he’s going to throw"], 1),
  mc("b5", "You’re on second. Line drive hit right at the shortstop. What do you do?", [
     "Take off for third",
     "Freeze until you see whether he catches it",
     "Go halfway"], 1),
  mc("b6", "You’re on second. Ground ball to the third baseman. What do you do?", [
     "Go right away",
     "Wait until it gets past him, then go",
     "Freeze and stay at second no matter what"], 1),
  mc("b7", "“Pick up your coach” means…", [
     "Help him carry the bucket",
     "Look at your base coach so you know what to do",
     "Cheer him up"], 1),
  mc("b11", "“Don’t get doubled up” means…", [
     "Don’t let two runners end up on the same base",
     "Don’t get so far off the bag that you can’t get back if a fly ball is caught",
     "Don’t get to two strikes"], 1),
  mc("b12", "Your coach yells “Get down!” That means…", [
     "Duck — the ball is coming at you",
     "Slide into the base",
     "Stop running"], 1),
  mc("b14", "You’re on first. The pitcher is staring at you and steps off the rubber. What is probably happening?", [
     "He’s tired and taking a break",
     "He might try to pick you off — be ready to get back",
     "Nothing, it doesn’t mean anything"], 1),
]

P2_MIND = [
  mc("m1", "“On deck” means…", [
     "You’re batting right now",
     "You’re the next batter up",
     "You bat after the next guy"], 1),
  mc("m5", "“Play with intent” means…", [
     "Play hard when the game is close",
     "Know what you’re trying to do on every rep and every play",
     "Play to win"], 1),
  wr("m6", "You strike out looking and you think the pitch was a ball. What do you do walking back to the dugout?"),
  wr("m7", "Your teammate makes an error and he’s upset about it. What do you do?"),
  wr("m8", "“Be coachable.” What does that actually look like from you at practice?"),
]

P2_TERMS = [
  "Load", "Be on time / get started earlier", "Get your foot down", "Stay back", "Let it travel",
  "Catch it out front", "Shorten up", "Choke up", "Stay inside the ball",
  "Stay through it / finish your swing", "Don't pull off", "Stay balanced", "Barrel it up",
  "Use your lower half", "Go up the middle", "Go the other way / opposite field", "Find a gap",
  "Battle / fight it off", "Move the runner", "Hit behind the runner", "Productive out", "Do a job",
  "Read the pitcher", "Read the ball", "Read the dirt", "Down angle", "Freeze on a line drive",
  "Make it get through", "Go on contact", "Round the bag", "Make a hard turn", "Hold / stay",
  "Shut it down", "Go on the throw", "Take the extra base", "Think first to third",
  "Play with intent",
]


def honest(terms, extra):
    return {
      "id": "honest",
      "title": "Be honest with me",
      "lead": ("This is the most important part of the whole sheet. Tap every one you have heard us say "
               "but you are still not totally sure about. Nobody is in trouble for tapping these — "
               "you are helping me know what to teach. Tapping nothing when you are not sure is the only "
               "wrong answer."),
      "questions": [
        {"id": "h1", "type": "check", "q": "Tap every one you're still not sure about:", "options": terms},
        wr("h2", "Anything you want us to explain at practice? Write it here.",
           "Any question at all — nothing is a dumb question." + extra),
      ],
    }


INTRO = ("These are things you hear us yell during games. This is not a test and it is not for a grade.\n\n"
         "The only thing I care about is finding out which ones we have explained well and which ones we "
         "have not. If you are not sure about one, say you are not sure — that helps me more than a guess. "
         "Take your time and answer like you would tell it to a teammate.")

SHEETS = [
  {
    "slug": "offense-part-1",
    "week_of": "2026-09-28",
    "title": "Know What We're Saying — Part 1",
    "intro": INTRO,
    "sections": [
      {"id": "plate", "title": "At the plate",
       "lead": "Words you hear from us before and during an at-bat. Pick what it means.",
       "questions": P1_PLATE},
      {"id": "approach", "title": "Your approach — write these out",
       "lead": "This is the big one. Take your time and answer honestly. There is no trick here.",
       "questions": P1_APPROACH},
      {"id": "bases", "title": "On the bases",
       "lead": "Leads, and what to do the moment the ball is hit.", "questions": P1_BASES},
      {"id": "mindset", "title": "Mindset",
       "lead": "How we want you thinking — hitting, running, or sitting on the bench.",
       "questions": P1_MIND},
      honest(P1_TERMS, ""),
    ],
  },
  {
    "slug": "offense-part-2",
    "week_of": "2026-10-05",
    "title": "Know What We're Saying — Part 2",
    "intro": INTRO,
    "sections": [
      {"id": "plate", "title": "At the plate",
       "lead": "Counts, and the swing cues you hear from the dugout.", "questions": P2_PLATE},
      {"id": "bases", "title": "On the bases",
       "lead": "Reads: what the ball and the pitcher are telling you.", "questions": P2_BASES},
      {"id": "mindset", "title": "Mindset and the dugout",
       "lead": "The part nobody sees in the scorebook.", "questions": P2_MIND},
      honest(P2_TERMS, ""),
    ],
  },
]

for sheet in SHEETS:
    n = sum(len(s["questions"]) for s in sheet["sections"])
    assert n == 20, "%s has %d questions, want 20" % (sheet["slug"], n)

ids = [q["id"] for sh in SHEETS for s in sh["sections"] for q in s["questions"]]
assert len(ids) == len(set(ids)) + 2, "question ids must be unique inside a sheet (h1/h2 repeat once each)"
terms = P1_TERMS + P2_TERMS
assert len(terms) == len(set(terms)), "a term is on both sheets"
print("%d questions total, %d terms across both check lists" % (len(ids), len(terms)))

for sheet in SHEETS:
    if req("team_worksheets?slug=eq.%s&select=id" % sheet["slug"]):
        req("team_worksheets?slug=eq.%s" % sheet["slug"], 'PATCH',
            {k: v for k, v in sheet.items() if k != "slug"})
        print("updated", sheet["slug"])
    else:
        req("team_worksheets", 'POST', [sheet])
        print("created", sheet["slug"])

for w in req("team_worksheets?select=slug,title,week_of,published_at,sections&order=week_of"):
    n = sum(len(s["questions"]) for s in w["sections"])
    print("  %-16s %-34s week of %s  %2d questions  %s"
          % (w["slug"], w["title"], w["week_of"], n,
             "PUBLISHED" if w["published_at"] else "not published"))
