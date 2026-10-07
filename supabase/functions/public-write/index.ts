// public-write — the only way an unauthenticated visitor writes anything.
//
// POST { kind: "worksheet-answer", worksheetId, playerId, answers, unsure?, submitted? }
// POST { kind: "coach-note",       scopeKey, key, coach, entry }
// → { ok: true } | { error }
//
// Two things need to work without a login: a player filling in his homework,
// and an assistant coach submitting a note on the review. Everything else a
// visitor might want to do, they may not.
//
// Until now both went straight at the tables with the shared anon key, which
// had ALL on everything — so the same key that let a nine-year-old save his
// homework also let anyone rewrite the roster, delete the books, or overwrite
// the manager's published write-ups. This narrows those two paths to exactly
// what they are:
//
//   * an answer row may only be written for a PUBLISHED worksheet, and only
//     for the one player it belongs to;
//   * a coach note may only be merged under that coach's own name, only for a
//     coach the team actually lists, and never under a pub: or report: key —
//     those are the manager's published words and are not writable from here.
//
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

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  // deno-lint-ignore no-explicit-any
  let body: any;
  try { body = await req.json(); } catch { return json({ error: "bad json" }, 400); }

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const { data: team } = await db.from("teams").select("id").order("created_at").limit(1).maybeSingle();
  if (!team) return json({ error: "no team" }, 404);
  const teamId = team.id;

  if (body.kind === "worksheet-answer") {
    const { worksheetId, playerId } = body;
    if (!worksheetId || !playerId) return json({ error: "worksheetId and playerId required" }, 400);

    const { data: ws } = await db.from("team_worksheets")
      .select("id,published_at").eq("team_id", teamId).eq("id", worksheetId).maybeSingle();
    if (!ws || !ws.published_at) return json({ error: "not open for answers" }, 403);

    const { data: player } = await db.from("team_players")
      .select("id").eq("team_id", teamId).eq("id", playerId).maybeSingle();
    if (!player) return json({ error: "unknown player" }, 403);

    const row: Record<string, unknown> = {
      team_id: teamId,
      worksheet_id: worksheetId,
      player_id: playerId,
      answers: body.answers ?? {},
      updated_at: new Date().toISOString(),
    };
    if (Array.isArray(body.unsure)) row.unsure = body.unsure;
    if (body.submitted) row.submitted_at = new Date().toISOString();

    const { error } = await db.from("team_worksheet_answers")
      .upsert(row, { onConflict: "worksheet_id,player_id" });
    if (error) return json({ error: error.message }, 500);
    return json({ ok: true });
  }

  if (body.kind === "coach-note") {
    const { scopeKey, key, coach, entry } = body;
    if (!scopeKey || !key || !coach) return json({ error: "scopeKey, key and coach required" }, 400);
    if (String(key).startsWith("pub:") || String(key).startsWith("report:")) {
      return json({ error: "that section is not writable here" }, 403);
    }

    const { data: cfg } = await db.from("team_config")
      .select("value").eq("team_id", teamId).eq("key", "team_settings").maybeSingle();
    // deno-lint-ignore no-explicit-any
    const roster: string[] = ((cfg?.value?.coaches ?? []) as any[]).map((c) => String(c?.name ?? ""));
    if (!roster.includes(String(coach))) return json({ error: "unknown coach" }, 403);

    const { data: row } = await db.from("team_reviews")
      .select("id,notes").eq("team_id", teamId).eq("scope_key", scopeKey).maybeSingle();
    if (!row) return json({ error: "unknown review" }, 404);

    // Merge this coach's entry and nothing else, so a submission can never
    // clobber another coach's note or anything the manager wrote.
    const notes = (row.notes ?? {}) as Record<string, unknown>;
    const existing = notes[key];
    const section: Record<string, unknown> =
      existing && typeof existing === "object" && !Array.isArray(existing)
        ? { ...(existing as Record<string, unknown>) }
        : {};
    section[String(coach)] = entry ?? null;
    notes[key] = section;

    const { error } = await db.from("team_reviews")
      .update({ notes, updated_at: new Date().toISOString() }).eq("id", row.id);
    if (error) return json({ error: error.message }, 500);
    return json({ ok: true });
  }

  return json({ error: "unknown kind" }, 400);
});
