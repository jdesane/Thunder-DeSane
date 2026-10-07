// schedule-sync — pulls the team's schedule from its GameChanger iCal feed.
//
// POST { url? }  (url only when saving a new feed; otherwise it reads the
//                 stored one from team_secrets)
// → { games: {created, updated, adopted, skipped}, practices: {...}, conflicts: [...] }
//
// What it writes: date, time, opponent, venue, home/away, the uniform — and
// practices, which the app has never had anywhere to put.
//
// What it will not touch, ever:
//   * a game that has been played (it has a result or recorded stats). The
//     feed's bracket entries are placeholders created when the draw is made
//     and frequently never corrected — on Oct 4 it still had the 1:00 PBG game
//     at 4:00 and the 3:00 championship as the earlier of the two. A feed does
//     not get to rewrite what happened.
//   * the plan: defense, batting order, opponent rank, planning mode, notes,
//     availability, pitching notes. Those are the coach's.
// Where the feed disagrees with a played game it is reported as a conflict and
// left alone, the same way a coach's fielding correction beats the stats export.
//
// Deployed with verify_jwt ON: this is a coach action.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (b: unknown, s = 200) =>
  new Response(JSON.stringify(b), { status: s, headers: { ...CORS, "Content-Type": "application/json" } });

const TZ = "America/New_York";

/** Split "<our team> @ <them>" or "<our team> vs <them>" into side and club.
 *  The feed writes the age division into the title ("SFL Thunder Black 9U @ …")
 *  and teams.name does not carry it, so the separator is found rather than
 *  assumed from the stored name's length — getting that wrong silently ignored
 *  every game in the calendar. */
function splitFixture(summary: string, teamName: string) {
  if (!summary.toLowerCase().startsWith(teamName.toLowerCase())) return null;
  const after = summary.slice(teamName.length);
  const m = after.match(/^\s*(?:\d+\s*u)?\s*(@|vs\.?)\s*(.+)$/i);
  if (!m) return null;
  const opponent = m[2].trim();
  if (!opponent || /^tbd$/i.test(opponent)) return null;
  return { home: /^vs/i.test(m[1]), opponent };
}

/** Loose opponent key: "WBT Cobras 9U Blue" and "WBT Cobras Blue" are one club. */
const oppKey = (s: string) =>
  String(s || "").toLowerCase().replace(/\b\d+\s*u\b/g, "").replace(/[^a-z0-9]+/g, " ").trim();

/** How much two club names overlap, 0..1, ignoring word order and plurals.
 *  The feed and the app rarely spell a club the same way: "Original Florida
 *  Pokers White" against "Original FL Pokers White", "Fort Sluggers 9U"
 *  against "Fort Slugger", "West Boca Panthers 9U-Orange" against "West Boca
 *  Orange". Exact keys miss every one of those and a duplicate game is the
 *  result. */
function nameOverlap(a: string, b: string) {
  const stem = (w: string) => w.replace(/s$/, "");
  const A = new Set(oppKey(a).split(" ").filter(Boolean).map(stem));
  const B = new Set(oppKey(b).split(" ").filter(Boolean).map(stem));
  if (!A.size || !B.size) return 0;
  let hit = 0;
  for (const w of A) if (B.has(w)) hit++;
  return hit / Math.min(A.size, B.size);
}

/** Pull the uniform out of an event description. GameChanger holds it as a
 *  "UNIFORM:" line followed by "* item" bullets, with stray text either side
 *  ("Sunday" before, "Field 2" after). Returns one item per line, or null. */
function uniformFrom(desc: string) {
  if (!desc) return null;
  const lines = desc.split("\n").map((l) => l.trim());
  const at = lines.findIndex((l) => /^uniform\s*:/i.test(l));
  if (at < 0) return null;
  const items: string[] = [];
  for (const l of lines.slice(at + 1)) {
    if (!l) continue;
    if (!l.startsWith("*")) break;
    const item = l.replace(/^\*\s*/, "").trim();
    if (item) items.push(item);
  }
  return items.length ? items.join("\n") : null;
}

/** ICS escapes commas and newlines; unfold continuation lines first. */
const unesc = (s: string) => s.replace(/\\n/g, "\n").replace(/\\,/g, ",").replace(/\\;/g, ";").replace(/\\\\/g, "\\");

function parseICS(raw: string) {
  const text = raw.replace(/\r?\n[ \t]/g, "");
  return text.split("BEGIN:VEVENT").slice(1).map((chunk) => {
    const ev: Record<string, string> = {};
    for (const line of chunk.split(/\r?\n/)) {
      if (line.startsWith("END:VEVENT")) break;
      const i = line.indexOf(":");
      if (i < 0) continue;
      ev[line.slice(0, i).split(";")[0]] = unesc(line.slice(i + 1));
    }
    return ev;
  });
}

/** 20261004T190000Z -> { date: "2026-10-04", time: "3:00 PM" } in the team's zone. */
function localParts(stamp: string) {
  const m = stamp?.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z?$/);
  if (!m) return null;
  const utc = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]));
  const f = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "numeric", minute: "2-digit", hour12: true,
  }).formatToParts(utc);
  const p: Record<string, string> = {};
  for (const x of f) p[x.type] = x.value;
  return {
    date: `${p.year}-${p.month}-${p.day}`,
    time: `${p.hour}:${p.minute} ${p.dayPeriod.toUpperCase()}`,
    iso: utc.toISOString(),
  };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  // deno-lint-ignore no-explicit-any
  let body: any = {};
  try { body = await req.json(); } catch { /* url is optional */ }

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const { data: team } = await db.from("teams").select("id,name").order("created_at").limit(1).maybeSingle();
  if (!team) return json({ error: "no team" }, 404);
  const teamId = team.id;

  // The feed URL carries a token, so it is a secret, not a setting.
  let url: string = String(body.url || "").trim();
  if (url) {
    await db.from("team_secrets")
      .upsert({ team_id: teamId, name: "schedule_ics_url", value: url }, { onConflict: "name" });
  } else {
    const { data: sec } = await db.from("team_secrets")
      .select("value").eq("team_id", teamId).eq("name", "schedule_ics_url").maybeSingle();
    url = String(sec?.value || "");
  }
  if (!url) return json({ error: "no calendar link saved yet" }, 400);

  let raw: string;
  try {
    const res = await fetch(url.replace(/^webcal:\/\//i, "https://"), {
      headers: { "User-Agent": "thunder-team-manager/1.0" },
    });
    if (!res.ok) return json({ error: `calendar fetch failed (${res.status})` }, 502);
    raw = await res.text();
  } catch (e) {
    return json({ error: "could not reach the calendar: " + (e as Error).message }, 502);
  }

  const events = parseICS(raw);
  if (!events.length) return json({ error: "no events in that calendar" }, 422);

  const { data: existing } = await db.from("team_games")
    .select("id,game_date,game_time,opponent,venue,location,uniform,source_uid,result,fielding,pitching_stats")
    .eq("team_id", teamId);
  const games = existing ?? [];
  const byUid = new Map(games.filter((g) => g.source_uid).map((g) => [g.source_uid, g]));

  const played = (g: Record<string, unknown>) =>
    !!(g.result && Object.keys(g.result as object).length) ||
    !!(g.fielding && Object.keys(g.fielding as object).length) ||
    !!(g.pitching_stats && Object.keys(g.pitching_stats as object).length);

  // How many game events the feed has on each date, for the last-resort
  // "one unclaimed game, one unclaimed event" match.
  const dayFeedCount: Record<string, number> = {};
  for (const ev of events) {
    const s = ev.SUMMARY || "";
    if (/\bpractice\b/i.test(s) || !splitFixture(s, team.name)) continue;
    const w = localParts(ev.DTSTART || "");
    if (w) dayFeedCount[w.date] = (dayFeedCount[w.date] || 0) + 1;
  }

  const out = {
    games: { created: 0, updated: 0, adopted: 0, skipped: 0 },
    practices: { created: 0, updated: 0 },
    conflicts: [] as string[],
    errors: [] as string[],
    ignored: 0,
  };
  // Every write is checked. supabase-js returns errors rather than throwing,
  // so an unchecked call fails silently and the function cheerfully reports a
  // row count for work it never did — which is exactly what happened on the
  // first real sync: the counts came back and the database was untouched.
  // deno-lint-ignore no-explicit-any
  const check = (what: string, res: any) => {
    if (res?.error) { out.errors.push(`${what}: ${res.error.message}`); return false; }
    return true;
  };

  for (const ev of events) {
    const summary = ev.SUMMARY || "";
    const when = localParts(ev.DTSTART || "");
    if (!when || !ev.UID) continue;
    const place = (ev.LOCATION || "").replace(/\n/g, ", ").trim();

    // ---- practices ----
    if (/\bpractice\b/i.test(summary)) {
      const end = localParts(ev.DTEND || "");
      const row = {
        team_id: teamId, starts_at: when.iso, ends_at: end?.iso ?? null,
        title: summary.trim(), location: place || null,
        notes: (ev.DESCRIPTION || "").trim() || null,
        source: "gamechanger-ics", source_uid: ev.UID,
        updated_at: new Date().toISOString(),
      };
      const { data: before } = await db.from("team_practices")
        .select("id").eq("team_id", teamId).eq("source_uid", ev.UID).maybeSingle();
      const res = await db.from("team_practices").upsert(row, { onConflict: "team_id,source_uid" });
      if (check(`practice ${when.date}`, res)) before ? out.practices.updated++ : out.practices.created++;
      continue;
    }

    // ---- games: "<team> vs <opponent>" is home, "<team> @ <opponent>" is away ----
    const fx = splitFixture(summary, team.name);
    if (!fx) { out.ignored++; continue; }
    const { home, opponent } = fx;

    const uniform = uniformFrom(ev.DESCRIPTION || "");
    const fields = {
      game_date: when.date, game_time: when.time, opponent,
      location: home ? "home" : "away",
      ...(place ? { venue: place } : {}),
      ...(uniform ? { uniform } : {}),
    };

    let match = byUid.get(ev.UID);
    if (!match) {
      // A game entered by hand before the feed was connected. Adopt it so the
      // next sync updates rather than duplicates. Same day is required; the
      // club name only has to be recognisably the same.
      const sameDay = games.filter((g) => !g.source_uid && g.game_date === when.date);
      match = sameDay.find((g) => oppKey(g.opponent) === oppKey(opponent))
        || sameDay.find((g) => nameOverlap(g.opponent, opponent) >= 0.5)
        // Last resort: one unclaimed game that day and one unclaimed feed
        // event for it. "PBG Storm 9U" and "Palm Beach Gardens Storm" share
        // one word out of four, but there is nothing else either could be.
        || (sameDay.length === 1 && dayFeedCount[when.date] === 1 ? sameDay[0] : undefined);
      if (match) {
        const res = await db.from("team_games").update({ source_uid: ev.UID }).eq("id", match.id);
        if (check(`adopt ${opponent} ${when.date}`, res)) {
          match.source_uid = ev.UID;
          byUid.set(ev.UID, match);
          out.games.adopted++;
        }
      }
    }

    if (!match) {
      const res = await db.from("team_games").insert({
        team_id: teamId, ...fields, status: "planned", innings: 4,
        rule_set: "usssa_9u", planning_mode: "balanced",
        batting_order: [], defense: {}, availability: {}, pitching_notes: {},
        source: "gamechanger-ics", source_uid: ev.UID,
      });
      if (check(`create ${opponent} ${when.date}`, res)) out.games.created++;
      continue;
    }

    // Played games are history. Say what the feed thinks and change nothing —
    // except the uniform, which is only ever a note about what to wear and is
    // worth having on the record even after the fact.
    if (played(match)) {
      const diffs: string[] = [];
      if (match.game_time !== fields.game_time) diffs.push(`time ${match.game_time} vs feed ${fields.game_time}`);
      if (match.game_date !== fields.game_date) diffs.push(`date ${match.game_date} vs feed ${fields.game_date}`);
      if (diffs.length) out.conflicts.push(`${match.opponent} ${match.game_date}: ${diffs.join("; ")} — kept yours`);
      if (uniform && !match.uniform) {
        check(`uniform ${opponent}`, await db.from("team_games").update({ uniform }).eq("id", match.id));
      }
      out.games.skipped++;
      continue;
    }

    const changed = Object.entries(fields).some(([k, v]) => (match as Record<string, unknown>)[k] !== v);
    if (changed) {
      const res = await db.from("team_games")
        .update({ ...fields, updated_at: new Date().toISOString() }).eq("id", match.id);
      if (check(`update ${opponent} ${when.date}`, res)) out.games.updated++;
    }
  }

  return json(out);
});
