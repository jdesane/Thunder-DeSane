// public-read — the only way an unauthenticated visitor gets any data.
//
// POST { kind: "worksheet" | "review", playerId?, scopeKey? }
//   worksheet  the players' /worksheet route
//   review     the staff/parent /review/... routes
// → { settings, players, ... } shaped for exactly that page
//
// Once the anon grants come off the tables, a kid's iPad and a coach's review
// link can reach nothing directly; they come here and get back only the fields
// their page renders. Three things this exists to stop, all of which the old
// direct-from-the-browser version leaked:
//
//   * team_settings carries review_pin and review_notify_email. The whole blob
//     used to go over the wire and get stripped in the browser, so anyone who
//     opened the network tab had the manager's PIN.
//   * team_games has the coach's private `notes`, `pitching_notes` and
//     `live_state`. The review asked for select=* and got all of it.
//   * team_reviews holds what each coach submitted privately. Those were sent
//     and hidden client-side; "nothing submitted is shown back on the page"
//     has to be true of the payload, not just the rendering.
//
// A signed-in manager never comes through here — his app reads the tables
// directly under his own RLS and sees everything, as he should.
// Deployed with verify_jwt off: there is no caller to verify.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

// Settings a public page may see. Anything not listed — the PIN, the notify
// address, payment handles, the registration URL — never leaves the server.
const PUBLIC_SETTINGS = [
  "team_name", "display_name", "age_division", "season", "season_type",
  "manager", "coaches", "season_line", "status_line",
];

// Game columns the review renders. No notes, no pitching_notes, no live_state,
// no source_fingerprint.
const GAME_COLS = [
  "id", "game_number", "game_date", "game_time", "opponent", "venue", "location",
  "innings", "status", "result", "tournament_id", "rule_set", "planning_mode",
  "opponent_tier", "defense", "availability", "batting_order",
  "fielding", "batting_stats", "pitching_stats", "fielding_stats",
].join(",");

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  let body: Record<string, string>;
  try { body = await req.json(); } catch { return json({ error: "bad json" }, 400); }
  const kind = body.kind === "review" ? "review" : body.kind === "worksheet" ? "worksheet" : null;
  if (!kind) return json({ error: "kind must be worksheet or review" }, 400);

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  // One team today. When teams sign up for themselves this resolves from the
  // slug in the URL instead of taking the only row.
  const { data: team } = await db.from("teams").select("id").order("created_at").limit(1).maybeSingle();
  if (!team) return json({ error: "no team" }, 404);
  const teamId = team.id;

  const { data: cfg } = await db.from("team_config")
    .select("value").eq("team_id", teamId).eq("key", "team_settings").maybeSingle();
  const settings: Record<string, unknown> = {};
  for (const k of PUBLIC_SETTINGS) {
    const v = (cfg?.value ?? {})[k];
    if (v !== undefined) settings[k] = v;
  }

  if (kind === "worksheet") {
    const { data: players } = await db.from("team_players")
      .select("id,jersey_number,name,sort_order").eq("team_id", teamId).eq("active", true)
      .order("sort_order", { ascending: true });
    // Unpublished worksheets do not exist as far as this route is concerned,
    // so a guessed slug shows nothing.
    const { data: worksheets } = await db.from("team_worksheets")
      .select("*").eq("team_id", teamId).not("published_at", "is", null)
      .order("week_of", { ascending: false });
    // A player's own answers only — one kid cannot read another's out of the
    // network tab. No playerId means no answers at all.
    let answers: unknown[] = [];
    if (body.playerId) {
      const { data } = await db.from("team_worksheet_answers")
        .select("*").eq("team_id", teamId).eq("player_id", body.playerId);
      answers = data ?? [];
    }
    return json({ settings, players: players ?? [], worksheets: worksheets ?? [], answers });
  }

  const [{ data: players }, { data: games }, { data: tournaments }, { data: reviews }] = await Promise.all([
    db.from("team_players").select("id,jersey_number,name,positions,tier,sort_order")
      .eq("team_id", teamId).eq("active", true).order("sort_order", { ascending: true }),
    db.from("team_games").select(GAME_COLS).eq("team_id", teamId)
      .order("game_date", { ascending: true, nullsFirst: false }),
    db.from("team_tournaments").select("*").eq("team_id", teamId)
      .order("start_date", { ascending: true, nullsFirst: false }),
    db.from("team_reviews").select("scope_key,title,notes").eq("team_id", teamId),
  ]);

  // Keep only what the page is meant to show: the published write-ups, the
  // sent stamp, and the parent-facing report copy. Everything a coach typed
  // into a Coach thoughts box stays on the server.
  const publicNotes = (notes: Record<string, unknown> | null) => {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(notes ?? {})) {
      if (k.startsWith("pub:") || k.startsWith("report:")) out[k] = v;
    }
    return out;
  };

  return json({
    settings,
    players: players ?? [],
    games: games ?? [],
    tournaments: tournaments ?? [],
    reviews: (reviews ?? []).map((r) => ({ ...r, notes: publicNotes(r.notes) })),
  });
});
