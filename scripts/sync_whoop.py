#!/usr/bin/env python3
"""Pull WHOOP recovery/sleep/workout data, write data/whoop.json,
and optionally email a daily summary."""
import os, json, urllib.request, urllib.parse, datetime, sys

def http_json(url, method='GET', data=None, headers=None):
    if data is not None and isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read()
            return json.loads(body), r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='ignore')
        print(f"HTTP {e.code} {url}\n{body[:500]}", file=sys.stderr)
        raise

def get_whoop_token():
    access = os.environ.get('WHOOP_ACCESS_TOKEN', '').strip()
    if access:
        return access
    refresh = os.environ['WHOOP_REFRESH_TOKEN']
    client_id = os.environ['WHOOP_CLIENT_ID']
    client_secret = os.environ['WHOOP_CLIENT_SECRET']
    tok, _ = http_json(
        'https://api.prod.whoop.com/oauth/oauth2/token',
        method='POST',
        data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh,
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'offline read:recovery read:cycles read:sleep read:workout read:body_measurement read:profile'
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'whoop-cli/1.0'}
    )
    return tok['access_token']

token = get_whoop_token()

def api_get(path, params=None):
    url = 'https://api.prod.whoop.com' + path
    if params: url += '?' + urllib.parse.urlencode(params)
    data, _ = http_json(url, headers={
        'Authorization': f'Bearer {token}',
        'User-Agent': 'whoop-cli/1.0'
    })
    return data

def pull_all(endpoint):
    all_recs = []
    next_token = None
    for _ in range(20):
        params = {'limit': 25}
        if next_token: params['nextToken'] = next_token
        data = api_get(endpoint, params)
        recs = data.get('records', [])
        all_recs.extend(recs)
        next_token = data.get('next_token')
        if not next_token: break
        if recs:
            oldest = min(r.get('created_at', '') for r in recs)
            if oldest < (datetime.datetime.utcnow() - datetime.timedelta(days=60)).isoformat() + 'Z':
                break
    return all_recs

print("Fetching WHOOP data...", file=sys.stderr)
cycles = pull_all('/developer/v2/cycle')
recovery = pull_all('/developer/v2/recovery')
sleep = pull_all('/developer/v2/activity/sleep')
workouts = pull_all('/developer/v2/activity/workout')

cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).isoformat() + 'Z'
def filt(recs):
    return [r for r in recs if r.get('created_at', '') >= cutoff]

recovery = filt(recovery)
sleep = filt(sleep)
workouts = filt(workouts)

def compact_recovery(r):
    return {
        'date': r['created_at'][:10],
        'score': r['score']['recovery_score'],
        'rhr': r['score']['resting_heart_rate'],
        'hrv': round(r['score']['hrv_rmssd_milli'], 1),
    }

def compact_sleep(s):
    sc = s['score']
    st = sc['stage_summary']
    total_ms = st['total_in_bed_time_milli'] - st.get('total_awake_time_milli', 0)
    # fallback to sum of sleep stages if total_in_bed not available
    if total_ms <= 0:
        total_ms = st['total_light_sleep_time_milli'] + st['total_rem_sleep_time_milli'] + st['total_slow_wave_sleep_time_milli']
    out = {
        'date': s['start'][:10],
        'hours': round(total_ms / 3600000, 1),
        'performance': sc.get('sleep_performance_percentage', 0),
    }
    # Sleep disturbances
    if 'sleep_needed' in sc and 'disturbances' in sc['sleep_needed']:
        out['disturbances'] = sc['sleep_needed']['disturbances']
    elif 'respiratory_rate' in sc:  # v2 sometimes has it here
        pass
    # WHOOP v2 sleep_disorder_count (API v2 ActivitySleep)
    if 'sleep_disorder_count' in sc:
        out['disturbances'] = sc['sleep_disorder_count']
    # Sleep stages in hours
    out['rem_h'] = round(st['total_rem_sleep_time_milli'] / 3600000, 1)
    out['sws_h'] = round(st['total_slow_wave_sleep_time_milli'] / 3600000, 1)
    out['light_h'] = round(st['total_light_sleep_time_milli'] / 3600000, 1)
    out['awake_h'] = round(st.get('total_awake_time_milli', 0) / 3600000, 1)
    return out

def compact_workout(w):
    return {
        'date': w['start'][:10],
        'sport': w.get('sport_name', w.get('sport_id', 0)),
        'strain': round(w['score'].get('strain', 0), 1) if 'score' in w else 0,
    }

try:
    profile = api_get('/developer/v2/user/profile/basic')
    user_name = profile.get('first_name', 'Player')
    user_id = profile.get('user_id')
except Exception:
    user_name = 'Player'
    user_id = None

out = {
    'user': {'name': user_name, 'user_id': user_id},
    'updated_at': datetime.datetime.utcnow().isoformat() + 'Z',
    'recovery': sorted([compact_recovery(r) for r in recovery], key=lambda x: x['date']),
    'sleep': sorted([compact_sleep(s) for s in [x for x in sleep if not x.get('nap')]], key=lambda x: x['date']),
    'workouts': sorted([compact_workout(w) for w in workouts], key=lambda x: x['date']),
}

# Merge with existing data/whoop.json to preserve sleep_disturbances + sleep stages
# if the API didn't return them (API schema drift protection)
try:
    with open('data/whoop.json') as f:
        existing = json.load(f)
    ex_sleep = {s['date']: s for s in existing.get('sleep', [])}
    for s in out['sleep']:
        ex = ex_sleep.get(s['date'])
        if ex:
            for k in ('disturbances', 'rem_h', 'sws_h', 'light_h', 'awake_h'):
                if k not in s and k in ex:
                    s[k] = ex[k]
except Exception:
    pass

os.makedirs('data', exist_ok=True)
with open('data/whoop.json', 'w') as f:
    json.dump(out, f, indent=2)

print(f"Wrote data/whoop.json: {len(out['recovery'])} recovery days, {len(out['sleep'])} sleeps, {len(out['workouts'])} workouts", file=sys.stderr)

# --- Email summary ---
email_to = os.environ.get('EMAIL_TO', '').strip()
if email_to:
    try:
        # Build daily summary email
        rec_map = {r['date']: r for r in out['recovery']}
        slp_map = {s['date']: s for s in out['sleep']}
        dates = sorted(rec_map.keys(), reverse=True)[:7]
        lines = [f"WHOOP Daily — {datetime.datetime.utcnow().strftime('%b %d, %Y')}", ""]
        for d in dates:
            r = rec_map.get(d); s = slp_map.get(d)
            if r:
                sleep_str = f"{s['hours']}h / {s['performance']}%" if s else "—"
                dist = f" dist {s.get('disturbances','-')}" if s and 'disturbances' in s else ""
                lines.append(f"{d}  rec {r['score']}%  HRV {r['hrv']}  RHR {r['rhr']}  sleep {sleep_str}{dist}")
        # Stress analysis for most recent day
        if dates:
            latest = dates[0]
            r = rec_map.get(latest)
            if r:
                lines.append("")
                if r['score'] < 34:
                    lines.append(f"⚠️  {latest}: Low recovery ({r['score']}%). Rest day recommended.")
                elif r['score'] >= 67:
                    lines.append(f"💚 {latest}: Green recovery ({r['score']}%). Good to go!")
                else:
                    lines.append(f"💛 {latest}: Yellow recovery ({r['score']}%). Take it easy.")
                if r['hrv'] < 20:
                    lines.append(f"   HRV low ({r['hrv']} ms) — stress/recovery signal")
        lines.append("")
        lines.append("Dashboard: https://dacameragirl.github.io/whoop-quest/")
        lines.append("Stress Analysis: https://dacameragirl.github.io/whoop-quest/stress.html")
        email_body = "\n".join(lines)

        # Send via Gmail API if GMAIL_* secrets are configured
        gmail_refresh = os.environ.get('GMAIL_REFRESH_TOKEN', '').strip()
        gmail_client_id = os.environ.get('GMAIL_CLIENT_ID', '').strip()
        gmail_client_secret = os.environ.get('GMAIL_CLIENT_SECRET', '').strip()
        if gmail_refresh and gmail_client_id and gmail_client_secret:
            # Refresh Gmail access token
            gmail_tok_data = urllib.parse.urlencode({
                'client_id': gmail_client_id,
                'client_secret': gmail_client_secret,
                'refresh_token': gmail_refresh,
                'grant_type': 'refresh_token'
            }).encode()
            gmail_tok_req = urllib.request.Request('https://oauth2.googleapis.com/token', data=gmail_tok_data)
            with urllib.request.urlopen(gmail_tok_req) as r_tok:
                gmail_access = json.loads(r_tok.read())['access_token']
            # Send email
            import base64
            from email.message import EmailMessage
            msg = EmailMessage()
            for addr in [a.strip() for a in email_to.split(',') if a.strip()]:
                msg['To'] = addr if 'To' not in msg else msg['To'] + ', ' + addr
            if 'To' not in msg:
                msg['To'] = email_to
            msg['From'] = os.environ.get('EMAIL_FROM', 'angela.hudson.data@gmail.com')
            latest_date = dates[0] if dates else 'today'
            latest_rec = rec_map.get(latest_date, {}).get('score', '?') if dates else '?'
            msg['Subject'] = f"WHOOP Daily — {latest_date} — {latest_rec}% recovery"
            msg.set_content(email_body)
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            send_req = urllib.request.Request(
                'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
                data=json.dumps({'raw': raw}).encode(),
                headers={'Authorization': f'Bearer {gmail_access}', 'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(send_req) as r_send:
                send_resp = json.loads(r_send.read())
            print(f"📧 Email sent to {email_to}: {send_resp.get('id')}", file=sys.stderr)
        else:
            print(f"\n{email_body}\n", file=sys.stderr)
            print("EMAIL_TO set but GMAIL_* secrets missing — skipping send, printed above.", file=sys.stderr)
    except Exception as e:
        import traceback
        print(f"Email send failed: {e}", file=sys.stderr)
        traceback.print_exc()

print("Sync complete.", file=sys.stderr)
