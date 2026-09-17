// review-draft — drafts or rewrites one section of the tournament review in
// the head coach's voice, from the numbers and his own private notes.
//
// POST { pin, section, data, notes, current, instruction }
//   pin         the review PIN from team_settings (the manager's unlock)
//   section     a label for the section ("Overview", "Pitching", "Micah Dubler"…)
//   data        the numbers for that section, as plain text lines
//   notes       the manager's own private note on the section (may be empty)
//   current     the existing write-up, when rewriting (may be empty)
//   instruction what the manager wants changed or added (may be empty)
//   others      for a player section: the other players' write-ups already in
//               this review, so phrasing is not recycled (may be empty)
// → { text }
//
// The Anthropic key lives in team_secrets (service role only) or the
// ANTHROPIC_API_KEY function secret. Deployed with verify_jwt off: the PIN is
// the auth, since the app's anon key is public anyway.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import Anthropic from "npm:@anthropic-ai/sdk";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const SYSTEM = `You write the published voice of a 9U youth travel baseball tournament review, as the head coach speaking to his assistant coaches. Team: SFL Thunder Black.

Voice: plain, direct, warm, like a coach talking — not a report, not corporate. Short sentences. First person ("I", "we"). No headings, no bullet lists, no bold, no emoji. Two or three short paragraphs at most, roughly 90 to 180 words. It reads well out loud.

Ground rules:
- Use only the numbers you are given. Never invent a statistic, a play, a quote, or something a coach saw. Youth scorekeeping is imperfect; treat numbers as direction, not verdicts.
- The coach's notes are the source of any observation about what happened on the field. If there are no notes, stay with what the numbers show and say plainly that the staff's observations will fill in the rest — do not make up what was seen.
- Everything is teaching. Frame weaknesses as what we work on next, never as labels. Never rank or bury a player.
- Never mention age. Everyone reading knows how old the players are, so no "at nine", "for nine-year-olds", "at this age", or anything like it, and never grade a result against age.
- Every player's write-up is his own. Say what his numbers and the notes say about him, and don't reach for stock lines. If other players' write-ups are supplied, do not repeat their phrasing, openings, compliments, or framing.
- When rewriting, keep what the coach did not ask to change. Apply his instruction faithfully, in his voice, even if it means cutting.
- Output the write-up only. No preamble, no title, no sign-off.`;

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  let body: Record<string, string>;
  try { body = await req.json(); } catch { return json({ error: "bad json" }, 400); }
  const { pin = "", section = "", data = "", notes = "", current = "", instruction = "", others = "" } = body;

  const supa = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  // The PIN gates this; a wrong or missing PIN is a 401 no matter what.
  const { data: cfg } = await supa.from("team_config").select("value").eq("key", "team_settings").single();
  const wantPin = String(cfg?.value?.review_pin ?? "").trim();
  if (!wantPin || String(pin).trim() !== wantPin) return json({ error: "wrong pin" }, 401);

  let apiKey = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
  if (!apiKey) {
    const { data: sec } = await supa.from("team_secrets").select("value").eq("name", "anthropic_api_key").single();
    apiKey = sec?.value ?? "";
  }
  if (!apiKey) return json({ error: "no api key configured" }, 500);

  const parts: string[] = [];
  parts.push(`Section: ${section || "Review"}`);
  parts.push(`\nThe numbers:\n${data.trim() || "(none provided)"}`);
  parts.push(`\nCoach's private notes on this section:\n${notes.trim() || "(none yet)"}`);
  if (current.trim()) parts.push(`\nCurrent write-up:\n${current.trim()}`);
  if (others.trim()) parts.push(`\nOther players' write-ups already in this review (do not reuse their phrasing):\n${others.trim()}`);
  if (instruction.trim()) parts.push(`\nWhat the coach wants changed or added:\n${instruction.trim()}`);
  else if (current.trim()) parts.push(`\nTighten and improve the current write-up without changing its meaning.`);
  else parts.push(`\nWrite the first draft.`);

  const client = new Anthropic({ apiKey });
  try {
    const res = await client.messages.create({
      model: "claude-opus-5",
      max_tokens: 2000,
      system: SYSTEM,
      messages: [{ role: "user", content: parts.join("\n") }],
    });
    if (res.stop_reason === "refusal") return json({ error: "declined" }, 422);
    const text = res.content.filter((b) => b.type === "text").map((b) => (b as { text: string }).text).join("\n").trim();
    return json({ text, usage: res.usage });
  } catch (e) {
    const status = (e as { status?: number }).status ?? 500;
    return json({ error: (e as Error).message ?? "api error" }, status >= 400 && status < 600 ? status : 500);
  }
});
