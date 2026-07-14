#!/usr/bin/env python3
"""Pull WHOOP recovery/sleep/workout data and write data/whoop.json"""
import os, json, urllib.request, urllib.parse, datetime, sys

def get_token():
    access = os.environ.get('WHOOP_ACCESS_TOKEN')
    if access: return access
    # refresh
    refresh = os.environ['WHOOP_REFRESH_TOKEN']
    client_id = os.environ['WHOOP_CLIENT_ID']
    client_secret = os.environ['WHOOP_CLIENT_SECRET']
    data = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'refresh_token': refresh,
        'client_id': client_id,
        'client_secret': client_secret,
    }).encode()
    req = urllib.request.Request('https://api.prod.whoop.com/oauth/oauth2/token', data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'whoop-cli/1.0'})
    with urllib.request.urlopen(req) as r:
        tok = json.loads(r.read())
    # GitHub Actions can't persist refreshed tokens back to Secrets automatically
    # Set WHOOP_ACCESS_TOKEN secret to a long-lived token, or accept that refresh
    # will need manual rotation every ~60 days (WHOOP refresh token TTL)
    # For now, just use the access_token we got
    return tok['access_token']

token = get_token()

def api_get(path, params=None):
    url = 'https://api.prod.whoop.com' + path
    if params: url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}',
        'User-Agent': 'whoop-cli/1.0'
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# Pull last 60 days of data
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
        # stop at ~60 days old
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

# Filter to last 30 days for the game data file (keeps repo small)
cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).isoformat() + 'Z'

def filt(recs):
    return [r for r in recs if r.get('created_at', '') >= cutoff]

recovery = filt(recovery)
sleep = filt(sleep)
workouts = filt(workouts)

# Build compact game data
def compact_recovery(r):
    return {
        'date': r['created_at'][:10],
        'score': r['score']['recovery_score'],
        'rhr': r['score']['resting_heart_rate'],
        'hrv': round(r['score']['hrv_rmssd_milli'], 1),
    }

def compact_sleep(s):
    st = s['score']['stage_summary']
    total_ms = st['total_light_sleep_time_milli'] + st['total_rem_sleep_time_milli'] + st['total_slow_wave_sleep_time_milli']
    return {
        'date': s['start'][:10],
        'hours': round(total_ms / 3600000, 2),
        'performance': s['score'].get('sleep_performance_percentage', 0),
    }

def compact_workout(w):
    return {
        'date': w['start'][:10],
        'sport': w.get('sport_name', 'activity'),
        'strain': round(w['score'].get('strain', 0), 1) if 'score' in w else 0,
    }

# Get user profile for name
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

os.makedirs('data', exist_ok=True)
with open('data/whoop.json', 'w') as f:
    json.dump(out, f, indent=2)

print(f"Wrote data/whoop.json: {len(out['recovery'])} recovery days, {len(out['sleep'])} sleeps, {len(out['workouts'])} workouts", file=sys.stderr)
