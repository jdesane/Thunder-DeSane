#!/usr/bin/env python3
"""Export every table to timestamped JSON — your own copy of the team's data.

    python3 scripts/export_backup.py                 # into backups/
    python3 scripts/export_backup.py --out ~/Dropbox/thunder-backups
    python3 scripts/export_backup.py --check         # verify the newest export

Supabase Pro already keeps a daily backup for seven days. This is the belt and
braces: a copy you hold, in a format you can read without Supabase existing,
and the thing to reach for when the answer to "what did the roster look like in
September" matters more than disaster recovery.

The anon key cannot read anything any more, so this signs in as a coach the
same way the app does. Set THUNDER_EMAIL and THUNDER_PASSWORD, or let it ask —
asking keeps the password out of your shell history and environment.

**The export contains children's home addresses, dates of birth and parents'
phone numbers.** It refuses to write anywhere git would pick it up.
"""
import argparse, getpass, json, os, pathlib, subprocess, sys, urllib.error, urllib.request
from datetime import datetime, timezone

SUPA = "https://zyonidiybzrgklrmalbt.supabase.co"
ANON = os.environ.get("SUPABASE_ANON_KEY") or (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5b25pZGl5YnpyZ2tscm1hbGJ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3MTY5NzUsImV4cCI6MjA4ODI5Mjk3NX0."
    "5See-qjLkXA4CoJi9tNfcLAX_cdvZhPaxw8iViKM8S8")

# Everything the coach app can see. team_secrets is deliberately absent: the
# API keys in it are not readable by a signed-in coach and have no business in
# a file on a laptop.
TABLES = [
    "teams", "team_members", "team_config", "team_players", "team_parents",
    "team_games", "team_tournaments", "team_reviews",
    "team_worksheets", "team_worksheet_answers",
    "team_expenses", "team_player_payments", "team_donations", "team_agreements",
]
PAGE = 1000


def die(msg):
    sys.exit("error: " + msg)


def post(path, body, token=None):
    r = urllib.request.Request(SUPA + path, method="POST", data=json.dumps(body).encode())
    r.add_header("apikey", ANON)
    r.add_header("Authorization", "Bearer " + (token or ANON))
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


def sign_in():
    email = os.environ.get("THUNDER_EMAIL") or input("Email: ").strip()
    pw = os.environ.get("THUNDER_PASSWORD") or getpass.getpass("Password: ")
    try:
        j = post("/auth/v1/token?grant_type=password", {"email": email, "password": pw})
    except urllib.error.HTTPError as e:
        die("could not sign in: " + e.read().decode()[:200])
    return j["access_token"]


def fetch(table, token):
    """Every row, a page at a time, so this keeps working as a season fills up.

    No server-side ordering: team_config and team_worksheet_answers have no
    created_at, and a per-table exception list is a bug waiting to happen.
    Rows are sorted here instead, which is what makes two exports diffable.
    """
    rows, start = [], 0
    while True:
        r = urllib.request.Request(f"{SUPA}/rest/v1/{table}?select=*")
        r.add_header("apikey", ANON)
        r.add_header("Authorization", "Bearer " + token)
        r.add_header("Range-Unit", "items")
        r.add_header("Range", f"{start}-{start + PAGE - 1}")
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                page = json.loads(resp.read().decode() or "[]")
        except urllib.error.HTTPError as e:
            if e.code == 416:      # past the end
                break
            return None, f"HTTP {e.code} {e.read().decode()[:120]}"
        rows.extend(page)
        if len(page) < PAGE:
            break
        start += PAGE
    rows.sort(key=lambda r: json.dumps(r, sort_keys=True, default=str))
    return rows, None


def git_would_track(path: pathlib.Path) -> bool:
    """True if git is not already ignoring this directory."""
    try:
        probe = path / ".git-visibility-probe"
        out = subprocess.run(["git", "check-ignore", "-q", str(probe)],
                             cwd=pathlib.Path(__file__).resolve().parent.parent,
                             capture_output=True)
        return out.returncode != 0          # 0 means ignored
    except Exception:
        return False                        # not a git repo at all


def do_export(out_dir: pathlib.Path):
    repo = pathlib.Path(__file__).resolve().parent.parent
    try:
        inside = out_dir.resolve().is_relative_to(repo)
    except AttributeError:                  # Python < 3.9
        inside = str(out_dir.resolve()).startswith(str(repo))
    if inside and git_would_track(out_dir):
        die(f"{out_dir} is inside the repo and not gitignored.\n"
            f"       The export holds home addresses, dates of birth and parent phone\n"
            f"       numbers — add it to .gitignore or use --out somewhere else.")

    token = sign_in()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    dest = out_dir / stamp
    dest.mkdir(parents=True, exist_ok=True)

    manifest, failed = {}, []
    for t in TABLES:
        rows, err = fetch(t, token)
        if err:
            failed.append((t, err))
            print(f"  {t:<24} FAILED  {err}")
            continue
        (dest / f"{t}.json").write_text(json.dumps(rows, indent=1, sort_keys=True, default=str))
        manifest[t] = len(rows)
        print(f"  {t:<24} {len(rows):>5} rows")

    (dest / "_manifest.json").write_text(json.dumps({
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "project": SUPA,
        "tables": manifest,
        "failed": dict(failed),
    }, indent=1))

    total = sum(manifest.values())
    size = sum(f.stat().st_size for f in dest.glob("*.json"))
    print(f"\n{total} rows across {len(manifest)} tables → {dest}  ({size/1024:.0f} KB)")
    if failed:
        die(f"{len(failed)} table(s) did not export — the backup is incomplete.")
    verify(dest)


def verify(dest: pathlib.Path):
    """A dump nobody has read back is not a backup. Re-read every file and
    check it parses and matches the manifest."""
    man = json.loads((dest / "_manifest.json").read_text())
    bad = []
    for t, n in man["tables"].items():
        f = dest / f"{t}.json"
        if not f.exists():
            bad.append(f"{t}: file missing"); continue
        try:
            rows = json.loads(f.read_text())
        except Exception as e:
            bad.append(f"{t}: will not parse ({e})"); continue
        if len(rows) != n:
            bad.append(f"{t}: {len(rows)} rows, manifest says {n}")
    if bad:
        die("the export does not read back cleanly:\n       " + "\n       ".join(bad))
    print(f"verified: every file parses and matches the manifest ({man['taken_at']})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent.parent / "backups"),
                    help="where to write (default: backups/ in the repo, which is gitignored)")
    ap.add_argument("--check", action="store_true", help="verify the newest export instead of taking a new one")
    a = ap.parse_args()
    out = pathlib.Path(a.out).expanduser()

    if a.check:
        runs = sorted(d for d in out.glob("*") if (d / "_manifest.json").exists())
        if not runs:
            die(f"no export found under {out}")
        verify(runs[-1])
        return
    do_export(out)


if __name__ == "__main__":
    main()
