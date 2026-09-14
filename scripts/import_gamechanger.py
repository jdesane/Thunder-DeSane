#!/usr/bin/env python3
"""
Import one GameChanger per-game stats export into team_games.

    python3 scripts/import_gamechanger.py "path/to/export.csv" --game-number 13
    python3 scripts/import_gamechanger.py "path/to/export.csv" --create \
        --opponent "Northstars 9U" --date 2026-09-20 --result W --rs 8 --ra 3 \
        [--tournament "Summer Heat Wave"] [--time "1:00 PM"] [--venue "..."]

What it does
- Parses the one CSV GameChanger produces per game (batting, pitching and
  fielding sections side by side; the four "category" downloads from the app
  are byte-identical, one is enough).
- Stores innings as OUTS so 2.2 (two and two-thirds) survives exactly.
- Rebuilds counts from the percentages GameChanger exports (line drives,
  swing-and-miss, first-pitch-strike outcomes, contact quality) using their
  denominators, so rates can be summed across games and recomputed.
- Fingerprints the file and refuses to import one already stored under a
  different game — the same export has been supplied twice under two names.
- Matches players to the roster by jersey number.

It never touches the planned defense grid, availability or notes.
"""
import argparse, csv, hashlib, json, os, sys, urllib.parse, urllib.request

SUPA = "https://zyonidiybzrgklrmalbt.supabase.co"
KEY = os.environ.get("SUPABASE_ANON_KEY") or (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5b25pZGl5YnpyZ2tscm1hbGJ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3MTY5NzUsImV4cCI6MjA4ODI5Mjk3NX0."
    "5See-qjLkXA4CoJi9tNfcLAX_cdvZhPaxw8iViKM8S8")

POS = ['P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'SF']
BAT_C = ['GP','PA','AB','H','1B','2B','3B','HR','RBI','R','BB','SO','K-L','HBP','SAC','SF','ROE','FC','SB','CS','QAB','TB','PS','XBH','HHB','LOB','2OUTRBI','2S+3','6+','GIDP','CI']
BAT_R = ['AVG','OBP','SLG','OPS','QAB%','C%','LD%','FB%','GB%','BABIP','BA/RISP','PS/PA']
PIT_C = ['GP','GS','BF','#P','H','R','ER','BB','SO','K-L','HBP','WP','BK','PIK','CS','SB','LOO','1ST2OUT','123INN','<13','BBS','LOBB','LOBBS','0BBINN','HR']
PIT_R = ['S%','FPS%','FPSO%','FPSW%','FPSH%','BAA','ERA','WHIP','K/BF','K/BB','P/IP','P/BF','<3%','SM%','WEAK%','HHB%','GO/AO','LD%','FB%','GB%','BABIP','BA/RISP','BB/INN','MPHFB']
FLD_C = ['TC','A','PO','E','DP','TP','PB','SB','CS','PIK','CI']
FLD_R = ['FPCT','CS%']


def req(path, method='GET', body=None, prefer=None):
    r = urllib.request.Request(SUPA + "/rest/v1/" + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None)
    for k, v in [('apikey', KEY), ('Authorization', 'Bearer ' + KEY), ('Content-Type', 'application/json'),
                 ('Prefer', prefer or ('return=representation' if method in ('POST', 'PATCH') else 'return=minimal'))]:
        r.add_header(k, v)
    with urllib.request.urlopen(r) as resp:
        t = resp.read().decode()
        return json.loads(t) if t.strip() else None


def outs(v):
    if v in (None, '', '-', 'N/A'): return 0
    s = str(v)
    if '.' in s:
        w, f = s.split('.', 1); f = f[:1]
        return int(w) * 3 + (int(f) if f.isdigit() else 0)
    try: return int(float(s)) * 3
    except ValueError: return 0

def num(v):
    if v in (None, '', '-', 'N/A'): return None
    try: return float(v)
    except ValueError: return None

def iv(v):
    n = num(v); return int(n) if n is not None else 0

def cnt(pct, denom):
    return round(pct * denom / 100) if (pct is not None and denom) else 0

def key(x):
    return (x.lower().replace('%', 'pct').replace('#', 'n').replace('-', '_')
             .replace('<', 'lt').replace('/', '_').replace('+', 'plus'))


def parse(path):
    rows = list(csv.reader(open(path, encoding='utf-8-sig')))
    idx, cur = {}, ''
    for i, (s, h) in enumerate(zip(rows[0], rows[1])):
        if s.strip(): cur = s.strip()
        idx[(cur, h)] = i
    g = lambda r, sec, n: r[idx[(sec, n)]] if (sec, n) in idx else None
    players = [r for r in rows[2:] if r and r[0].strip() and r[0] not in ('Totals', 'Glossary')]
    totals = next((r for r in rows[2:] if r and r[0] == 'Totals'), None)
    gp = {r[idx[('Batting', 'GP')]] for r in players}
    if gp - {'0', '1'}:
        sys.exit(f"Refusing: GP values {sorted(gp)} — this looks like a season/cumulative export, not one game.")

    bat, pit, fld, fielding = {}, {}, {}, {}
    for r in players:
        k = r[0]
        b = {key(x): iv(g(r, 'Batting', x)) for x in BAT_C}
        b.update({key(x): num(g(r, 'Batting', x)) for x in BAT_R})
        b['bip'] = max(0, b['ab'] - b['so'] + b['sf'] + b['sac'])
        for pk, ck in [('ldpct', 'ld'), ('fbpct', 'fb'), ('gbpct', 'gb')]: b[ck] = cnt(b[pk], b['bip'])
        bat[k] = b

        po, pitches = outs(g(r, 'Pitching', 'IP')), iv(g(r, 'Pitching', '#P'))
        if po > 0 or pitches > 0:
            p = {'outs': po, 'pitches': pitches}
            p.update({key(x): iv(g(r, 'Pitching', x)) for x in PIT_C})
            p.update({key(x): num(g(r, 'Pitching', x)) for x in PIT_R})
            p['strikes'] = cnt(p['spct'], pitches)
            p['first_pitch_strikes'] = cnt(p['fpspct'], p['bf'])
            for pk, ck in [('fpsopct', 'fpso'), ('fpswpct', 'fpsw'), ('fpshpct', 'fpsh')]: p[ck] = cnt(p[pk], p['first_pitch_strikes'])
            p['lt3'] = cnt(p['lt3pct'], p['bf'])
            p['swing_miss'] = cnt(p['smpct'], pitches)
            p['bip'] = max(0, p['bf'] - p['bb'] - p['so'] - p['hbp'])
            for pk, ck in [('weakpct', 'weak'), ('hhbpct', 'hhb'), ('ldpct', 'ld'), ('fbpct', 'fb'), ('gbpct', 'gb')]: p[ck] = cnt(p[pk], p['bip'])
            pit[k] = p

        f = {key(x): iv(g(r, 'Fielding', x)) for x in FLD_C}
        f.update({key(x): num(g(r, 'Fielding', x)) for x in FLD_R})
        f['c_outs'] = outs(g(r, 'Fielding', 'INN'))
        att = g(r, 'Fielding', 'SB-ATT')
        if att and '-' in str(att):
            a, bb = str(att).split('-'); f['sb_allowed'], f['sb_att'] = iv(a), iv(bb)
        if f['tc'] or f['c_outs'] or f['pb'] or f['e']: fld[k] = f

        pos = {p: outs(g(r, 'Fielding', p)) for p in POS if outs(g(r, 'Fielding', p)) > 0}
        if pos: fielding[k] = pos

    length_outs = max((outs(totals[idx[('Fielding', p)]]) for p in POS if (('Fielding', p) in idx)), default=0) if totals else 0
    rs = iv(totals[idx[('Batting', 'R')]]) if totals else None
    ra = iv(totals[idx[('Pitching', 'R')]]) if totals else None
    return dict(bat=bat, pit=pit, fld=fld, fielding=fielding, innings=-(-length_outs // 3), rs=rs, ra=ra)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv')
    ap.add_argument('--game-number', type=int, help='update the game with this number')
    ap.add_argument('--create', action='store_true', help='insert a new game instead')
    ap.add_argument('--opponent'); ap.add_argument('--date'); ap.add_argument('--time'); ap.add_argument('--venue')
    ap.add_argument('--result', choices=['W', 'L', 'T']); ap.add_argument('--rs', type=int); ap.add_argument('--ra', type=int)
    ap.add_argument('--tournament', help='tournament name (substring match)')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if not a.create and a.game_number is None:
        sys.exit("Give --game-number N to update, or --create with --opponent/--date/--result.")

    fp = hashlib.md5(open(a.csv, 'rb').read()).hexdigest()
    existing = req("team_games?select=game_number,opponent,game_date,source_fingerprint&source_fingerprint=eq." + fp)
    if existing and not (a.game_number is not None and existing[0]['game_number'] == a.game_number):
        e = existing[0]
        sys.exit(f"Refusing: this exact file is already imported as game {e['game_number']} ({e['opponent']}, {e['game_date']}). "
                 "GameChanger has been re-downloaded under the wrong name before — export the right game.")

    d = parse(a.csv)
    roster = req("team_players?select=id,jersey_number,name")
    bynum = {}
    for p in roster:
        bynum[str(p['jersey_number'])] = p['id']; bynum[str(p['jersey_number']).lstrip('0') or '0'] = p['id']
    def pid(n):
        k = str(n); v = bynum.get(k) or bynum.get(k.lstrip('0') or '0')
        if not v: sys.exit(f"Jersey #{n} is not on the roster.")
        return v

    payload = {
        'status': 'final', 'innings': d['innings'], 'source': 'gamechanger-csv', 'source_fingerprint': fp,
        'fielding': {pid(k): v for k, v in d['fielding'].items()},
        'batting_stats': {pid(k): v for k, v in d['bat'].items()},
        'pitching_stats': {pid(k): v for k, v in d['pit'].items()},
        'fielding_stats': {pid(k): v for k, v in d['fld'].items()},
        'availability': {pid(k): True for k in d['fielding']},
    }
    rs, ra = (a.rs if a.rs is not None else d['rs']), (a.ra if a.ra is not None else d['ra'])
    outcome = a.result or ('W' if rs > ra else 'L' if rs < ra else 'T')
    payload['result'] = {'outcome': outcome, 'rs': rs, 'ra': ra}

    pitch_line = ', '.join(f"#{k} {v['outs']//3}.{v['outs']%3} IP/{v['pitches']}p" for k, v in d['pit'].items())
    print(f"{os.path.basename(a.csv)}: {outcome} {rs}-{ra}, {d['innings']} innings, {len(d['fielding'])} fielders · pitching: {pitch_line}")
    if a.dry_run:
        print("dry run — nothing written"); return

    if a.create:
        if not (a.opponent and a.date): sys.exit("--create needs --opponent and --date")
        nums = [g['game_number'] or 0 for g in req("team_games?select=game_number")]
        payload.update({'opponent': a.opponent, 'game_date': a.date, 'game_time': a.time, 'venue': a.venue,
                        'location': 'coin', 'rule_set': 'usssa_9u', 'planning_mode': 'balanced',
                        'batting_order': [], 'defense': {}, 'game_number': max(nums) + 1})
        if a.tournament:
            t = req("team_tournaments?select=id,name&name=ilike." + urllib.parse.quote(f"*{a.tournament}*"))
            if t: payload['tournament_id'] = t[0]['id']
        res = req("team_games", 'POST', [payload])
        print(f"created game {res[0]['game_number']}: {res[0]['opponent']} {res[0]['game_date']}")
    else:
        res = req(f"team_games?game_number=eq.{a.game_number}", 'PATCH', payload)
        if not res: sys.exit(f"No game with number {a.game_number}.")
        print(f"updated game {a.game_number}: {res[0]['opponent']} {res[0]['game_date']}")
    print("Remember: add this game's length to Settings → Game length.")


if __name__ == '__main__':
    main()
