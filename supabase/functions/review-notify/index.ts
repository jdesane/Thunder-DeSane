// review-notify — emails the manager when a coach submits a note on the review.
//
// POST { scope_key, key, coach, label, scope, link }
//   scope_key  the team_reviews row (the app's RV_NOTES_KEY)
//   key        the section key the note is under ("hitting", "player:<pid>"…)
//   coach      the coach's name as stored under that key
//   label      the section's heading, for the subject line
//   scope      the review's title ("Summer Heat Wave (Rings)")
//   link       the review URL, for the email body
// → { sent: true } | { skipped: reason }
//
// Nothing in the request is trusted for the note itself: the function reads
// the submitted note back from the table and only emails when that coach
// has a stamped submission there. The same stamp is never emailed twice.
// Mail goes through Resend; the key sits in team_secrets (service role only)
// or the RESEND_API_KEY function secret. The recipient is
// team_settings.review_notify_email. Deployed with verify_jwt off.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  let body: Record<string, string>;
  try { body = await req.json(); } catch { return json({ error: "bad json" }, 400); }
  const { scope_key = "", key = "", coach = "", label = "", scope = "", link = "" } = body;
  if (!scope_key || !key || !coach) return json({ error: "scope_key, key and coach required" }, 400);

  const supa = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  const { data: cfg } = await supa.from("team_config").select("value").eq("key", "team_settings").single();
  const to = String(cfg?.value?.review_notify_email ?? "").trim();
  if (!to) return json({ skipped: "no review_notify_email in team settings" });

  // The note as it sits in the table — the only version that gets emailed
  const { data: row } = await supa.from("team_reviews").select("notes,title").eq("scope_key", scope_key).single();
  const notes = (row?.notes ?? {}) as Record<string, Record<string, { text?: string; at?: string | null; notified?: string | null }>>;
  const entry = notes[key]?.[coach];
  if (!entry || typeof entry !== "object" || !entry.at || !(entry.text ?? "").trim()) return json({ skipped: "no submitted note there" });
  if (entry.notified === entry.at) return json({ skipped: "already sent" });

  let apiKey = Deno.env.get("RESEND_API_KEY") ?? "";
  if (!apiKey) {
    const { data: sec } = await supa.from("team_secrets").select("value").eq("name", "resend_api_key").single();
    apiKey = sec?.value ?? "";
  }
  if (!apiKey) return json({ error: "no mail key configured" }, 500);

  const first = coach.split(/\s+/)[0];
  const title = scope || row?.title || "the review";
  const section = label || key;
  const text = (entry.text ?? "").trim();
  const subject = `${first} on ${section} — ${title}`;
  const plain = `${coach} submitted a note on "${section}" (${title}):\n\n${text}\n\n${link ? `Open the review: ${link}\n` : ""}Turn on "Show submitted notes" to read everything the staff has sent.`;
  const html = `<div style="font-family:-apple-system,Segoe UI,sans-serif;font-size:15px;line-height:1.5;color:#111">
    <p style="margin:0 0 12px"><b>${esc(coach)}</b> submitted a note on <b>${esc(section)}</b> — ${esc(title)}</p>
    <blockquote style="margin:0 0 16px;padding:10px 14px;border-left:3px solid #FFB612;background:#fff8e6;white-space:pre-wrap">${esc(text)}</blockquote>
    ${link ? `<p style="margin:0 0 8px"><a href="${esc(link)}">Open the review</a></p>` : ""}
    <p style="margin:0;color:#666;font-size:13px">Turn on “Show submitted notes” to read everything the staff has sent.</p></div>`;

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: "Thunder Review <onboarding@resend.dev>", to: [to], subject, text: plain, html }),
  });
  if (!res.ok) {
    const err = await res.text().catch(() => "");
    return json({ error: `mail failed: ${res.status} ${err.slice(0, 200)}` }, 502);
  }

  // Mark the stamp so a repeat call doesn't email again. The app rewrites the
  // whole row on every save, so this can be lost — a duplicate email at worst.
  notes[key][coach] = { ...entry, notified: entry.at };
  await supa.from("team_reviews").update({ notes }).eq("scope_key", scope_key);
  return json({ sent: true });
});
