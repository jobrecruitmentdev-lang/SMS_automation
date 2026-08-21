import urllib.request
import json
import time

CLOUD_URL = 'https://sms.jobrecruitment.in'
PAIRING_CODE = 'JR-795250'

print('=' * 75)
print(' [*] CLOUD SERVER UNFILTERED RAW TEST REPORT (https://sms.jobrecruitment.in)')
print('=' * 75)

# TEST 1: Cloud Server Health
t0 = time.time()
try:
    with urllib.request.urlopen(f'{CLOUD_URL}/api/health_check', timeout=10) as r:
        res1 = json.loads(r.read().decode())
        latency1 = int((time.time() - t0) * 1000)
        print(f'[PASS] [1/6] Cloud Health Check ({latency1}ms)')
        print(f'             API Version: {res1.get("api_version")}, Server: {res1.get("status")}')
except Exception as e:
    print(f'[FAIL] [1/6] Cloud Health Check: {e}')

# TEST 2: Gateway Registration
t0 = time.time()
try:
    payload2 = {
        'pairing_code': PAIRING_CODE,
        'device_name': 'Samsung SM-G781B (Jio 4G)',
        'device_id': 'RZCW717VDZJ',
        'carrier': 'JIO 4G (Signal: 100%)',
        'battery': '49%',
        'android_version': '13 (One UI 5.1)'
    }
    req2 = urllib.request.Request(
        f'{CLOUD_URL}/api/gateway/register',
        data=json.dumps(payload2).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req2, timeout=10) as r:
        res2 = json.loads(r.read().decode())
        latency2 = int((time.time() - t0) * 1000)
        print(f'[PASS] [2/6] Gateway Registration for {PAIRING_CODE} ({latency2}ms)')
        print(f'             Auth Token: {res2.get("token")}, Ok: {res2.get("ok")}')
except Exception as e:
    print(f'[FAIL] [2/6] Gateway Registration: {e}')

# TEST 3: Heartbeat Telemetry Ping
t0 = time.time()
try:
    payload3 = {
        'pairing_code': PAIRING_CODE,
        'is_online': True,
        'battery': '49%',
        'temperature': '34.0°C',
        'is_screen_locked': False,
        'screen_state_text': 'Unlocked & Active'
    }
    req3 = urllib.request.Request(
        f'{CLOUD_URL}/api/gateway/heartbeat',
        data=json.dumps(payload3).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req3, timeout=10) as r:
        res3 = json.loads(r.read().decode())
        latency3 = int((time.time() - t0) * 1000)
        print(f'[PASS] [3/6] Heartbeat Telemetry Ping ({latency3}ms)')
        print(f'             Status: {res3.get("status")}')
except Exception as e:
    print(f'[FAIL] [3/6] Heartbeat Telemetry Ping: {e}')

# TEST 4: Recruiter Status Check
t0 = time.time()
try:
    with urllib.request.urlopen(f'{CLOUD_URL}/api/relay/status?pairing_code={PAIRING_CODE}', timeout=10) as r:
        res4 = json.loads(r.read().decode())
        latency4 = int((time.time() - t0) * 1000)
        print(f'[PASS] [4/6] Recruiter Dashboard Status ({latency4}ms)')
        print(f'             Online: {res4.get("is_online")}, Device: {res4.get("device_name")}, Battery: {res4.get("battery")}')
except Exception as e:
    print(f'[FAIL] [4/6] Recruiter Dashboard Status: {e}')

# TEST 5: Enqueue Campaign Job (Cloud -> Queue via /api/start_dispatch)
t0 = time.time()
try:
    payload5 = {
        'pairing_code': PAIRING_CODE,
        'campaign_id': 'TEST-CAMPAIGN-001',
        'campaign_title': 'Unfiltered Cloud Dispatch Test',
        'candidates': [{'name': 'Rahul Patel', 'phone': '9898011223', 'role': 'Sales'}],
        'template': 'Hello {name}, job invite for {role}',
        'role': 'Sales',
        'location': 'Ahmedabad',
        'company': 'JobRecruitment'
    }
    req5 = urllib.request.Request(
        f'{CLOUD_URL}/api/start_dispatch',
        data=json.dumps(payload5).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req5, timeout=10) as r:
        res5 = json.loads(r.read().decode())
        latency5 = int((time.time() - t0) * 1000)
        print(f'[PASS] [5/6] Enqueue Campaign Job ({latency5}ms)')
        print(f'             Status: {res5.get("status")}, Ok: {res5.get("ok")}')
except Exception as e:
    print(f'[FAIL] [5/6] Enqueue Campaign Job: {e}')

# TEST 6: Phone Gateway Poll (Fetch Job from Cloud Queue)
t0 = time.time()
try:
    with urllib.request.urlopen(f'{CLOUD_URL}/api/gateway/poll?pairing_code={PAIRING_CODE}', timeout=10) as r:
        res6 = json.loads(r.read().decode())
        latency6 = int((time.time() - t0) * 1000)
        print(f'[PASS] [6/6] Phone Gateway Poll ({latency6}ms)')
        print(f'             Has Job: {res6.get("has_job")}, Job: {res6.get("job")}')
except Exception as e:
    print(f'[FAIL] [6/6] Phone Gateway Poll: {e}')

print('=' * 75)
