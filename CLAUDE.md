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

## Signing in

The coach app signs in with email and password (Supabase Auth); the public
worksheet and review pages never do. `SESSION` lives in
`localStorage.thunder_session` and `supa()` sends that access token when there
is one, falling back to the anon key otherwise — which is what still makes the
public pages work, and what stops working the moment the anon grants come off.

**Never put a login screen in front of a coach in a dugout.** `refreshSession()`
returns true — carry on — for a network failure *and* a 5xx, keeping the stored
session so the app comes up on its cache with no signal. Only a 4xx, Supabase
actually refusing the token, clears it. The token is also topped up on
`visibilitychange`, which is when a backgrounded home-screen app is most likely
to hold a stale one. Changing any of that risks locking him out at a field.

`handle_new_user()` links a new `auth.users` row to the one team in
`team_members` — the first account is `manager`, later ones `coach` (extra coach
seats are a paid add-on, which is why the role is stored rather than inferred).
`my_team_ids()` is the helper the RLS policies will use.

The old team PIN still works as a fallback (`appLocked()` checks the session
first, then the PIN) so nobody is locked out mid-transition. **Remove the PIN
path, and the `review_pin` setting with it, in the same change that revokes the
anon grants** — the review PIN is currently sent in full to every visitor of a
`/review/...` link, so it is not a secret and manager controls must key off the
session instead.

## Schedule sync

`schedule-sync` (verify_jwt on) pulls the team's GameChanger iCal feed. The URL
carries a token, so it is a **secret** — `team_secrets.schedule_ics_url`, saved
and read only by the function, never back into the page. Settings → Schedule
sync pastes it and runs it.

The feed carries more than games: `SUMMARY` is `"<team> vs X"` for home and
`"<team> @ X"` for away, `DESCRIPTION` often holds the uniform of the day, and
there are **47 practices** with times and addresses — which is why
`team_practices` now exists. Birthdays, fundraisers and tournament placeholders
are ignored.

**What it must never do**, and the reasons are from the real feed:

- **Never change a played game** (one with a `result` or recorded stats). The
  feed's bracket entries are placeholders made when the draw happens and often
  never corrected: on Oct 4 it still had the 1:00 PBG game at 4:00 and the 3:00
  championship listed as the earlier of the two. Disagreements are returned as
  `conflicts` and the coach's version stands.
- **Never touch the plan** — defense, batting order, opponent rank, planning
  mode, notes, availability. It writes date, time, opponent, venue, home/away.

**Tournaments are offered, never created.** A multi-day all-day block
(`DTSTART:20261021` with no time) is what a tournament looks like in this feed
— but so is "Off Weekend 🎃" and so is a week-long fundraiser. The sync returns
them as `candidates` and the coach taps Add on the real ones, the same reason
opponent rank and tier are his. Single-day all-day events and anything with a
time (birthdays, fundraiser nights) are not offered. Note `localParts()` only
reads timestamps; `dateOnly()` reads all-day events, and leaving that out
silently dropped every tournament block in the calendar.

**The uniform** comes out of the event description — GameChanger holds it as a
`UNIFORM:` line with `* item` bullets, and about half the games have one.
`team_games.uniform` is one item per line; it shows as a picker in the Game
Planner and on the printed plan, which is the copy that reaches the dugout. The
combinations in `team_settings.uniforms` are **the coach's, stored exactly as he
wrote them** — never tidy the spelling and never invent a kit. A sync fills the
uniform on a played game only when it is empty, since it is a note about what to
wear rather than a record of what happened.

`source_uid` (the feed's event id, unique per team) is what makes a re-sync
update rather than duplicate. Games entered before the feed was connected are
**adopted** by it: same date, then an exact `oppKey` match, then
`nameOverlap() >= 0.5`, then — if exactly one unclaimed game and one unclaimed
event share the date — that one. The feed and the app almost never spell a club
the same way ("PBG Storm 9U" / "Palm Beach Gardens Storm", "Fort Sluggers 9U" /
"Fort Slugger", "West Boca Panthers 9U-Orange" / "West Boca Orange"); exact
matching alone adopted 11 of 18 and would have created 6 duplicates, the
ladder above adopts 16.

## Who can see what

Two audiences, two completely separate paths to the data.

- **The coach app signs in.** `supa()` sends the session token, RLS lets
  `authenticated` reach rows whose `team_id` is in `my_team_ids()`, and that is
  the only way the private columns — addresses, dates of birth, parent phone
  numbers, the books — are reachable at all.
- **Public routes** (`/worksheet`, `/review/*`) sign in to nothing and touch no
  table. They call `public-read` / `public-write`, which run on the service role
  and return only the fields that page renders. `loadPublicData()` branches on
  `signedIn()`; `saveCoachNote()` and the worksheet answer save do the same.

**`anon` has no policies and no grants.** The key in the page source is inert:
every table answers it 401, reads and writes alike. It had ALL on everything
until Oct 7 2026, which meant anyone who opened devtools on a link the coach
had sent could read the lot and delete it too. Do not add an `anon` policy to
solve a problem — if a public page needs something, widen the function.

What the functions deliberately withhold, each of which used to cross the wire
and get hidden in the browser instead:

- `team_settings` is filtered to `PUBLIC_SETTINGS`. The old `review_pin` was
  sent to every visitor of a review link, so it authenticated nothing and has
  been deleted; `review_notify_email` and the payment handles stay server-side.
- `team_games` is filtered to `GAME_COLS` — no `notes`, `pitching_notes` or
  `live_state`, all of which are the coach's.
- `team_reviews` notes are filtered to `pub:` and `report:` keys. "Nothing
  submitted is shown back on the page" has to be true of the payload, not the
  rendering.

`public-write` accepts exactly two things and validates both: an answer row
only for a **published** worksheet and only for that player, and a coach note
only under a coach the team lists, merged into that coach's own entry, never
under a `pub:` or `report:` key.

Guessed URLs still reveal nothing: an unpublished worksheet is not in the
payload at all, and a player's page asks for one player's answers.

**Manager = signed in.** `managerDevice()` is `signedIn()`, and `review-draft`
runs with `verify_jwt` on. There is no shared secret left anywhere in the
client.

**Roles are enforced in the database**, not the client:

| | reads | writes | contacts & money | addresses / DOB |
|---|---|---|---|---|
| `manager` | all | all | yes | yes |
| `coach` | all | all | yes | yes |
| `viewer` | games, roster, reviews, practices | **none** | no | no |

`my_team_ids()` gates reads, `my_writable_team_ids()` (manager/coach only) gates
writes, and `my_role(team)` answers which. Postgres RLS is row-level and cannot
hide a column, so the app reads the roster through **`team_players_scoped`**, a
view that blanks `address` and `dob` for a viewer with the owner's rights —
not the client politely omitting fields. `handle_new_user()` makes the first
account `manager` and **every later one `viewer`**: an account that appears
from nowhere can look, not touch, and is promoted deliberately.

Reviews are read through **`team_reviews_scoped`**, which hands back the
published write-ups and the parent report copy and **strips every coach's
private submission unless you are the manager**. Coaches are told "nothing you
submit is shown back on the page"; that has to be true of the payload, not the
rendering. Reading the table directly handed a viewer 38 sections of four
coaches' private assessments of nine-year-olds. `saveCoachNote()` still writes
to the table — it needs the real notes to merge into.

`managerDevice()` is manager-only, so drafting and sending a review is not a
coach's to do. `applyRoleToChrome()` hides Finances and Uniforms from a viewer
and bands the top of the screen — the database is the boundary, that is so the
app reads as deliberate rather than broken.

A viewer is the account to hand someone who wants to see the app. Extra *coach*
seats are the intended paid add-on; coach and manager are deliberately still
the same rights until that split is designed.

On backups: the project is on Supabase **Pro**, which already takes a daily
backup and keeps 7 days. Point-in-time recovery is a paid add-on on top of
that and buys restore-to-the-second instead of restore-to-last-night — not
worth it at this size. A local export is the cheaper belt and braces.

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
