# SFL Thunder Black — Team Manager

Single-file static web app (`index.html`) deployed by Vercel from `main` at
https://thunder-desane.vercel.app. Data lives in Supabase (project
`zyonidiybzrgklrmalbt`, tables prefixed `team_`), read and written from the
browser through the REST API with the anon key (`supa()` helper near the top
of the script). No build step, no framework, no bundler. The coach runs it
installed to an iPhone home screen; `coach.html` and `scout.html` are legacy.

## Every deploy — do all three

1. Bump the build stamp in **both** places to the same new value
   (`YYYY-MM-DD.N`): the `<meta name="build">` tag in `index.html` and
   `version.txt`. The installed app compares them and offers a reload;
   if they drift, phones silently run stale code.
2. Syntax-check the inline script before committing:
   extract `<script>…</script>` and run `node --check` on it.
3. Push to `main`. Vercel deploys in about a minute.

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
  later tournament day.
- **Team rotation rules** (auto-fill and the rule check): every available
  player takes the field; bench time follows tiers, top < middle < bottom;
  nobody sits two innings in a row; a must-play player goes to their
  best-rated open position, never the first premium spot in fill order.
  After any manual change to an inning, `repairNextInning` reseats anyone
  benched there in the next inning.
- **Recorded beats planned**: when a game has `fielding` /
  `pitching_stats` / `batting_stats` / `fielding_stats` (imported from
  GameChanger), those drive Playing Time, pitching history and the Review,
  not the planned `defense` grid. Innings are stored as **outs**.
- **Game length**: 9U games are time-capped; plans build for the longest
  game seen (`planningInnings()`), demand estimates use the typical length
  (`inningsProfile()`), both from Settings → Game length.

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
- `team_games` — `game_number` 1–12 are imported GameChanger games.
  **Game 8 (Sep 6, WBT Cobras Blue, W 19-10) is score-only**: the export
  supplied for it was a byte-identical copy of the Billygoats file. Ask for
  a fresh export; import with the script below.
- `team_reviews` — notes per review scope (`scope_key` → `notes` jsonb).
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
