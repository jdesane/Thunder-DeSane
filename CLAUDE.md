# SFL Thunder Black — Team Manager

Single-file static web app (`index.html`) deployed by Vercel from `main` at
https://thunder-desane.vercel.app. Data lives in Supabase (project
`zyonidiybzrgklrmalbt`, tables prefixed `team_`), read and written from the
browser through the REST API with the anon key (`supa()` helper near the top
of the script). No build step, no framework, no bundler. The coach runs it
installed to an iPhone home screen; `coach.html` and `scout.html` are legacy.

## Every deploy — do all three

1. Bump the build stamp with `python3 scripts/bump_build.py` — it writes
   the same new `YYYY-MM-DD.N` to **both** the `<meta name="build">` tag in
   `index.html` and `version.txt`, or fails. Never hand-edit them: a search
   for a stamp another session already changed silently does nothing, and a
   version.txt ahead of the meta tag means the update banner returns on
   every reload and "Update now" can never clear it. Drift the other way
   leaves phones on stale code.
2. Syntax-check the inline script before committing:
   extract `<script>…</script>` and run `node --check` on it.
3. Push to `main`. Vercel deploys in about a minute.

## Look

Team colours: black and Steeltown gold `#FFB612` (`--gold`, also `--warn`
and `--info`). Green/red stay for good/bad signals. The mark is `logo.svg`
(a vector redraw of the team logo); `scripts/make_icons.py` rasterises it
onto black tiles for the home-screen icons and favicon — rerun it if the
mark changes. Printed pages stay white with gold accents.

## Where things are in index.html

CSS at the top, one `<section id="section-…">` per screen, then the script
in labelled blocks: CONFIG · STATE · SUPABASE · CACHE · LOAD FROM CLOUD ·
GAME PLANNER (model / auto-fill / rule check / CRUD / render / position
chart / print) · PLAYING TIME · LIVE GAME (+ dictation, undo) ·
TOURNAMENT PLANNER · REVIEW · PITCHING · DASHBOARD · ROSTER · FINANCES ·
UNIFORMS · SETTINGS · UPDATE CHECK · KEYBOARD SHORTCUTS · BOOT.

Adding a screen means: nav markup in the sidebar, a `<section>`, a case in
`navigate()`, a label in `SECTION_LABEL`, and a line in the boot re-render
list. Two functions with the same name silently shadow each other — it has
happened once (`renderPitching`); grep before naming.

## Rules the code enforces — do not weaken

- **USSSA 9U pitching**: 6 IP max in a day; more than 3 IP in a day means a
  required rest day; 8 IP max in any 3 consecutive days. A partial inning
  charges a full inning. One implementation, used everywhere:
  `pitcherFindingsOn` / `wouldExceedOn` / `remainingCapacity` /
  `availabilityOn`. Auto-fill holds every arm at 3 IP on any day that has a
  later tournament day. The Tournament Planner's Per-arm cap row is a stepper
  (`PITCH_UI.armCap[date]`, `armCapFor()`): the coach can set a day *lower*
  than the default to spread the work across more arms, never higher — the
  rest-day rule is still the ceiling. Both that and the games-per-day stepper
  persist on `team_tournaments.planning` (`{gamesPerDay, armCap}`, keyed by
  date) via `savePlanning()` / `loadPlanning()` — they used to be memory-only,
  so a refresh lost them and the other coaches never saw the plan. Game times are text ("11:00 AM"), so
  sort them with `byGameTime` / `gameTimeMinutes`; a string compare puts the
  1:00 PM game before the 11:00 AM one.
- **Team rotation rules** (auto-fill and the rule check): every available
  player takes the field; bench time follows tiers, top < middle < bottom;
  nobody sits two innings in a row; a must-play player goes to their
  best-rated open position, never the first premium spot in fill order.
  After any manual change to an inning, `repairNextInning` reseats anyone
  benched there in the next inning. In any mode other than `have_to_win`,
  nobody sits a second time until every available player has sat once — a
  have-to-win game leans on the tiers instead.
- **Recorded beats planned**: when a game has `fielding` /
  `pitching_stats` / `batting_stats` / `fielding_stats` (imported from
  GameChanger), those drive Playing Time, pitching history and the Review,
  not the planned `defense` grid. Innings are stored as **outs**, so
  `playingTimeData()` and `seasonInnings()` tally in outs and convert to
  innings **once, at the end**. Rounding each position as it is added credits
  a player who moves inside an inning with a whole inning at every spot he
  touched, and the bench column — whatever is left of the game — swallows the
  whole error. That hid half of Easton's bench time and three-quarters of
  Ryder's over one weekend. A spot touched for only an out or two still shows
  as 1 so position variety stays visible; totals and bench come off the outs.
- **Coach corrections beat the export**: GameChanger credits a whole inning to
  a player who only came on for part of it — the usual cause is a pitching
  change mid-inning — which hides his bench time. `team_games.fielding_corrections`
  (`{player_id: {POS: outs}}`, replacing that player's whole row) is the coach's
  word on what really happened; it is written into `fielding` and re-applied by
  `scripts/import_gamechanger.py` after every import, so re-importing the same
  export never silently undoes him. Game 17 holds one: Easton came on at third
  for the end of an inning, so his SS outs there are 9, not the exported 11.
- **Game length**: 9U games are time-capped with a run rule at both ends, so
  how long one runs is mostly about how even it is. `planningInnings(game)`
  takes the opponent's rank where the coach has set one — Tough 6, Middle 5,
  Weaker 4 (`OPP_TIER_INNINGS`, plan the top of each band) — and otherwise
  falls back to the longest game seen, from Settings → Game length. Demand
  estimates use the typical length (`inningsProfile()`). The rank lives on
  `team_games.opponent_tier` and is remembered per opponent in
  `team_settings.opponent_tiers`, keyed by `oppKey()` so "WBT Cobras Blue" and
  "WBT Cobras 9U Blue" are one club. **The rank is the coach's**, like tiers and
  ratings — never infer it from a scoreline. Note `TIER_LABEL` is already taken
  by player tiers; the opponent ones are `OPP_TIER_*`.

## Multi-tenancy (groundwork laid, not switched on)

The app serves one team today but is being built to serve many, so new work
must not assume a single team. Every `team_*` table carries a `team_id` ->
`teams(id)`, backfilled to `sfl-thunder-black` and defaulted to it, so the
current client — which knows nothing about the column — keeps writing correct
rows. `teams` holds name/slug/age_division/season; `team_members`
(team_id, user_id, role: manager/coach/viewer) says who may act on a team and
fills up when auth lands.

Still single-tenant, and each flips in the same change that updates the client,
because the client upserts against single-column conflict targets
(`?on_conflict=key` / `scope_key` / `worksheet_id`):

| table | today | becomes |
|---|---|---|
| `team_config` | `PRIMARY KEY (key)` | `(team_id, key)` |
| `team_reviews` | `UNIQUE (scope_key)` | `(team_id, scope_key)` |
| `team_worksheets` | `UNIQUE (slug)` | `(team_id, slug)` |
| `team_secrets` | `PRIMARY KEY (name)` | `(team_id, name)` |

`team_id` columns are nullable with a default only while one team exists. Drop
the defaults, make them NOT NULL and have the client send `team_id` explicitly
as part of onboarding the second team.

## Who can see what

The app is one file serving two audiences, so the boot path splits before it
fetches anything:

- **Public routes** (`/worksheet`, `/review/*`) call `loadPublicData(kind)`,
  which selects only the columns that page renders — for a worksheet that is
  `id, jersey_number, name`, nothing else — strips `review_pin` from the
  settings it keeps, and **never calls `saveCache()`**. Do not make a public
  page call `loadFromCloud()`: that pulls home addresses, dates of birth,
  parent phone numbers and the books, and writes them to the visitor's
  localStorage. A kid's iPad must never hold any of it.
- **The coach app** fetches `team_config` alone, checks `appLocked()`, and
  shows the PIN screen before loading anything else. `startApp()` is the only
  path that calls `loadFromCloud()`.

Guessed URLs must not reveal anything: an unpublished worksheet never renders
from its slug (`wsPick` requires `published_at`; `WS_PREVIEW` is set in memory
from the Homework screen, never from the URL), `/review/<slug>/reports` falls
back to the assessment unless the device holds the PIN, and a player's page
fetches only that player's answer row. `managerDevice()` fails closed on any
shared link — never infer "manager" from a missing PIN, which is what happens
on a public page where the PIN was stripped.

This is defence in depth, not a security boundary. The anon key is in the page
source and RLS still lets `anon` read every table, so anyone who opens devtools
can query the lot. Closing that properly needs real auth for the coach app plus
restrictive RLS — not done yet.

## Judgement stays with the coach

Never invent position ratings, tiers, opponent quality, or coach notes.
The Position Chart and every "Coach thoughts" box are the coach's. If data
is missing, say so in the UI rather than fill it in. The one place text is
generated is the Review's **published write-up** (`pub:<section>`), and
only through the `review-draft` Edge Function on the manager's request:
it drafts from the numbers plus his own private note, he revises it in the
app, and nothing goes to the staff until he presses Send. The function's
system prompt forbids inventing stats or observations — keep it that way.

## Data notes

- `team_players.positions` — 0–5 per position (0 = never); `tier` —
  top / middle / bottom. #10 is **Funzy** Travaglini (was Alfonso).
- `team_games` — `game_number` 1–18 are imported GameChanger games (13 is
  West Boca Orange; 14–18 are the Treasure Coast Triple Play, Oct 3–4).
  **Game 8 (Sep 6, WBT Cobras Blue, W 19-10) is score-only**: the export
  supplied for it was a byte-identical copy of the Billygoats file. Ask for
  a fresh export; import with the script below.
- `team_reviews` — notes per review scope (`scope_key` → `notes` jsonb).
  Scopes are `tournament:<id>`, `season`, and `game:<id>` — one per final
  game, newest first, so a standalone game gets the same review. A
  single-game review drops the "Game by game" section and its nav entry.
  Each section key (`overview`, `hitting`, `player:<pid>`, …) holds
  `{ "<coach name>": { text, at, draft? } }`. Every coach — the manager
  included — types a `draft`; Submit appends it to `text`, stamps `at`,
  and clears the box. Nothing sent is ever shown back on the page; the
  manager reads it with "Show submitted notes", a per-device switch gated
  by `team_settings.review_pin` when set. Coach order comes from
  `team_settings.coaches`, manager first. `report:<pid>:{why,plan,message,home}` and
  `report:team:focus` are plain strings — the parent-facing Player
  Report copy. A bare string under a section key is a legacy manager note.
  Reports print one page per player; empty report fields are omitted, never
  filled in. `#review` and `#reports` in the URL open straight to those views.
- **Published write-ups and drafting**: `pub:<section>` (overview, games,
  hitting, pitching, defense, player:<pid>, playingtime, practice, next) are plain
  strings everyone reads; `pub:_sent` is the ISO time the manager sent the
  review — the coach URL shows "still working on it" until then. Manager
  controls (draft / rewrite / edit / send, the coach-status strip, and
  "Show submitted notes") appear only on a device unlocked with the review
  PIN (`localStorage.thunder_rv_pin_ok`). Drafting calls
  `supabase/functions/review-draft` (source in the repo; deploy with the
  Supabase MCP `deploy_edge_function`, `verify_jwt: false` — the PIN is the
  auth). The Anthropic key sits in `team_secrets` (RLS: anon can insert,
  never select; the function reads it with the service role). Rotating it:
  delete the row by SQL, then a plain POST insert with the anon key — an
  upsert fails because anon can't SELECT. `claude-opus-5`, ~1–2¢ a draft.
- **Submit notifications**: each coach Submit calls
  `supabase/functions/review-notify`, which reads the note back from
  `team_reviews`, emails it to `team_settings.review_notify_email` through
  Resend (`team_secrets.resend_api_key`, from `onboarding@resend.dev` — only
  the Resend account's own address can receive until a domain is verified),
  and stamps `notified` on the entry so the same submission isn't mailed twice.
- **Homework worksheets**: `team_worksheets` (slug, week_of, title, intro,
  `sections` jsonb of questions, `published_at`) and `team_worksheet_answers`
  (one row per worksheet per player, `answers` jsonb keyed by question id).
  Question types: `choice` (options with the coach's meaning as `answer`, the
  last option is always "I'm not sure yet"), `text`, and `check` (multi-select
  — the "which terms are you still unsure about" list, the most useful answer
  on the sheet). `/worksheet` is the players' standalone route: no chrome, no
  login, they tap their own name, answers save as they type to localStorage
  and Supabase so a sleeping iPad loses nothing. Nothing is graded on their
  screen. Players see nothing until the coach presses Publish (`published_at`).
  With more than one sheet published the player page shows a menu after they
  tap their name (`wsMenuHTML` / `wsOpenSheet`, `WS_CHOSEN`), so the single
  `/worksheet` link still reaches all of them; `/worksheet/<slug>` goes
  straight to one. A `check` question is also how a reps checklist is built —
  see `scripts/seed_worksheet_tonight.py`.
  The Homework screen shows who's done it, what they wrote, and the two
  aggregates that matter: terms the team flagged and questions they missed.
  "Print every player's sheet" swaps the screen for a pack (`HW_UI.pack`): one
  page per player with every question, their answer marked right / wrong / not
  sure / blank, what we meant where they missed, and the terms they flagged.
  `afterprint` puts the screen back.
- **Answer sheets**: each question can carry `why` (the coach's explanation)
  and `video` (a TikTok / YouTube / Instagram URL, embedded by `videoEmbed()`
  — anything unrecognised falls back to a link, never dropped). Both are
  edited in the Homework screen's "Answer sheet" panel. A player sees the
  answers only when `answers_published_at` is set **and** he has submitted his
  own, so nobody reads them instead of doing the work. An explanation that
  only restates the right answer is suppressed rather than printed twice.
  Seeded by `scripts/seed_worksheet_offense.py` — every term and definition in
  it is the coach's, never invented.
- **Standalone review URLs** (vercel.json rewrites `/review/*` to
  index.html): `/review/<tournament-slug>` is the assessment on its own
  for the staff, `/review/<slug>/reports` all player reports,
  `/review/<slug>/<player-slug>` one family's report with nothing else
  reachable (`body.standalone`, `.sa-parent`). Slugs come from `slugify()`
  of the tournament name / player name; `season` is the season scope. The
  Review header's Coach link / Parent link buttons copy these.
- Importing a game: `python3 scripts/import_gamechanger.py <export.csv>
  --game-number N` updates that game; `--create` inserts one. The script
  fingerprints the file and refuses one already imported under another
  game. GameChanger's per-game export contains batting, pitching and
  fielding in one file — the four "category" downloads are duplicates.

## Verify locally

`python3 -m http.server 8123` and open
http://localhost:8123/index.html (also in `.claude/launch.json`). Add
`?v=<anything>` to defeat a cached copy. Every screen should navigate
without console errors; the planner rule check on a fresh Auto-fill
should be 8 of 8.
