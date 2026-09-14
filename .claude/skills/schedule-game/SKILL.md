---
name: schedule-game
description: Schedule a game (or doubleheader) on GameChanger for SFL Thunder Black 9U by driving the user's logged-in Chrome via the claude-in-chrome MCP. Use when the user pastes game details (opponent, date, time, location) and asks to schedule, add, or book the game in GameChanger. Also triggers on "add to GC", "put on the schedule", "schedule this game".
---

# Schedule a GameChanger game

Automates creating a Game event on the SFL Thunder Black 9U GameChanger schedule.

## Input format the user will paste

```
Opponent: <team name>
Date: YYYY-MM-DD
Time: <HH:MM AM/PM>[, <HH:MM AM/PM>]   # second time = doubleheader
Location: <address>
Duration: <e.g. 1 hr 45 min>            # optional, default 1 hr 45 min
```

If any required field is missing (opponent, date, time, location), ask before proceeding.

## Rules (do not skip)

- **Event Type:** Game
- **Home/Away:** always TBD
- **Duration default:** 1 hr 45 min
- **Arrive:**
  - First (or only) game → 60 min before start
  - Doubleheader 2nd game → No arrival time
- **Opponent search:** type the name. If an EXACT string match appears in Search Results, click it. Otherwise click the "Add \"<query>\"" button to create a new team.
- **Message team about this event update:** leave UNCHECKED.
- **Doubleheader:** create two separate events, back-to-back, same opponent, same location.

## Steps

1. Load the browser tools in ONE call (also grab `browser_batch` — everything below assumes batched actions):
   `ToolSearch({query: "select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__find,mcp__claude-in-chrome__form_input,mcp__claude-in-chrome__browser_batch,mcp__claude-in-chrome__tabs_create_mcp"})`
2. `tabs_context_mcp({createIfEmpty: true})` to get/create a tab, then navigate to `https://web.gc.com/teams` and click **SFL Thunder Black 9U**. Team URL: `https://web.gc.com/teams/OXmME6loAwzT/2026-fall-sfl-thunder-black-9u` (season slug changes each season).
3. Click **SCHEDULE** tab → **Add Event**.
4. `read_page({filter: "interactive"})` to get refs for the form. **Event Type** = Game and **Home/Away** = TBD are defaults — verify but don't re-click.
5. Use `form_input` for: date (`08/23/26`), time (`10:00 AM`), duration (option value `{"hours":1,"minutes":45}`), arrive (`{"minutes":60}` for first/only game, `{}` for doubleheader game 2).
6. **Location — CRITICAL:** DO NOT use `form_input` for the location field. It sets text but doesn't register with GameChanger's autocomplete, and the event saves with location = TBD. Instead:
   - `computer left_click` the location textbox.
   - `computer type` the address (e.g. `6000 Northtree Blvd, Lake Worth`).
   - Wait 2s, screenshot to see the dropdown. Two possible options appear:
     - A Google Places autocomplete suggestion (click it if it matches).
     - A `+ ...` button ("use custom text") — click this if the Google suggestion is wrong or missing. This commits the typed text as the location.
7. **Opponent:** click the opponent textbox → the field opens a quick dropdown. Click **Add/Search Opponents** to open the search modal. In the modal search input, `triple_click` first to clear any stray text, then type the full opponent name, wait 2s, and click the exact match in Search Results. If no exact match, click the `+ Add "<name>"` button above the results to create a new team.
8. Confirm **Message team about this event update** is UNCHECKED (default).
9. Show the user a summary and wait for their "go" before clicking **Save & Close** (or **Save & Add Another** for the first game of a doubleheader).
10. For a doubleheader, repeat 4–9 for the 2nd game. Note: after saving game 1 and reopening the modal for game 2 via Save & Add Another, clicking the opponent field may auto-select the just-used team without needing the search modal — verify with a screenshot.
11. After saving all events, screenshot the Schedule page to confirm.

## Editing an event after saving

There is **no visible "Edit event" button** on the event Info page. Two ways in:
- Navigate directly to `.../schedule/<event-id>/edit` — this URL 404s but seems to trigger the Edit Event modal on the underlying `/info` page (observed in practice).
- Reliable fallback: **delete + recreate**. Use the red **Delete** button inside the Edit Event modal. Only safe when there are no RSVPs yet.

The Edit Event modal is the same form as Add Event, minus the Repeats field and with a Delete button.

## Common failure modes

- **Escape closes the whole modal and DISCARDS all values.** Never press Escape to dismiss the date-picker popup — click another field instead.
- **Setting a location via `form_input` saves as "TBD".** Always use the click-type-pick-suggestion flow (step 6).
- **Aug 23, 2026 is Sunday.** Confirm the weekday the user probably means matches the date they typed — if the user says "Sat 8/23" but 8/23 is Sunday, flag it before saving.

## Safety

- Do NOT click Save & Close without the user confirming the summary. Creating a team event notifies parents' calendars downstream — treat submission as visible-to-others action per the safety rules.
- If team-search returns ambiguous results (e.g. multiple exact matches across seasons), stop and ask the user which to pick.
- If "Add \"<query>\"" would create a new team, mention it explicitly in the summary so the user knows to revise later.
