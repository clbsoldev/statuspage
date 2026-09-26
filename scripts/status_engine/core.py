import os
import json
import requests
from datetime import datetime, timezone


def load_config(config_path=None):
    if not config_path:
        config_path = os.getenv('CONFIG_JSON_PATH', 'config.json')

    if not os.path.exists(config_path):
        print(f"❌ [CORE ERROR] Config file not found at: {config_path}")
        return None
    with open(config_path, 'r') as f:
        return json.load(f)


def update_maintenance_json(status_dir, payload):
    """Verwaltet aktive und vergangene Wartungsfenster in maintenance.json."""
    m_file = os.path.join(status_dir, "maintenance.json")
    data = {"active": [], "past": []}
    if os.path.exists(m_file):
        try:
            with open(m_file, 'r') as f:
                data = json.load(f)
        except Exception:
            pass

    h, s = payload['host'], payload['service']
    n_type = payload.get('type', 'NOTIFICATION')
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if n_type == "DOWNTIMESTART":
        data["active"] = [x for x in data["active"] if not (x['host'] == h and x['service'] == s)]
        data["active"].append({
            "host": h,
            "service": s,
            "start": ts,
            "reason": payload.get('comment') or "Planmäßige Wartung"
        })
        print(f"🛠️ [MAINTENANCE] Started downtime for {h}:{s}")
    elif n_type in ["DOWNTIMEEND", "DOWNTIMECANCELLED"]:
        for item in data["active"][:]:
            if item['host'] == h and item['service'] == s:
                item['end'] = ts
                data["past"].insert(0, item)
                data["active"].remove(item)
        data["past"] = data["past"][:10]
        print(f"🛠️ [MAINTENANCE] Ended downtime for {h}:{s}")

    with open(m_file, 'w') as f:
        json.dump(data, f, indent=2)


def manage_issues(host_id, service, status, output, host_config, auto_close=True):
    """Erstellt oder schließt automatisch GitHub Issues basierend auf dem Incident-Status."""
    token = os.getenv('GH_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY')

    if not token or not repo:
        print("⚠️ [ISSUES] GH_TOKEN or GITHUB_REPOSITORY not set. Skipping GitHub Issue sync.")
        return

    assignee = host_config.get('assignee', 'admin')
    issue_title = f"Alert: {host_id} - {service}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    try:
        search_url = f"https://api.github.com/search/issues?q=repo:{repo}+type:issue+state:open+in:title+\"{issue_title}\""
        search_res = requests.get(search_url, headers=headers).json()
        items = search_res.get('items', [])
        existing_issue = items[0] if items else None

        if status in ['CRITICAL', 'DOWN', 'WARNING'] and not existing_issue:
            issue_data = {
                "title": issue_title,
                "body": f"### Service Alert\n**Host:** {host_id}\n**Service:** {service}\n**Status:** {status}\n\n**Output:**\n{output}",
                "assignees": [assignee],
                "labels": ["incident", status.lower()]
            }
            res = requests.post(f"https://api.github.com/repos/{repo}/issues", json=issue_data, headers=headers)
            if res.status_code == 201:
                print(f"🎫 [ISSUES] Created GitHub Issue #{res.json().get('number')} for {host_id}:{service}")
        elif status in ['OK', 'UP'] and existing_issue and auto_close:
            num = existing_issue['number']
            requests.patch(f"https://api.github.com/repos/{repo}/issues/{num}", json={"state": "closed"}, headers=headers)
            print(f"🎫 [ISSUES] Closed GitHub Issue #{num} for {host_id}:{service}")
    except Exception as e:
        print(f"❌ [ISSUES ERROR] Failed to sync GitHub Issue: {e}")


def process_event(unified_payload):
    """Haupt-Funktion zur Verarbeitung eingehender Zabbix/Nagios Alerts."""
    host_id = unified_payload.get('host')
    service = unified_payload.get('service')
    status = unified_payload.get('status', 'UNKNOWN')
    output = unified_payload.get('output', '')
    n_type = unified_payload.get('type', 'NOTIFICATION')

    # 1. KONSOLEN-LOGGING FÜR GITHUB ACTIONS
    print("=" * 60)
    print("📥 [STATUS ENGINE] Incoming Event")
    print(f"  • Host ID:  {host_id}")
    print(f"  • Service:  {service}")
    print(f"  • Status:   {status}")
    print(f"  • Type:     {n_type}")
    print(f"  • Output:   {output or 'N/A'}")
    print("-" * 60)

    config = load_config()
    if not config:
        return False

    status_dir = os.getenv('STATUS_DIR', 'gh-pages/status')

    # 2. Host-Matching
    host_config = next((h for h in config.get('hosts', []) if h['id'] == host_id), None)
    if not host_config:
        print(f"⚠️ [CORE WARNING] Host '{host_id}' not found in config.json. Event ignored.")
        print("=" * 60)
        return False

    # 3. Service-Matching (Schutz gegen unkonfigurierte Services)
    configured_services = host_config.get('services', [])
    service_config = next((s for s in configured_services if s['name'] == service), None)

    # Wenn der Service nicht 'Host' (Ping) ist und nicht in config.json existiert
    if service_config is None and service != "Host":
        print(f"⚠️ [CORE WARNING] Service '{service}' for host '{host_id}' not found in config.json. Event ignored.")
        print("=" * 60)
        return False

    should_auto_close = service_config.get('auto_close', True) if service_config else True

    # 4. Wartung vs. Normaler Incident
    if "DOWNTIME" in n_type:
        update_maintenance_json(status_dir, unified_payload)
    else:
        manage_issues(host_id, service, status, output, host_config, should_auto_close)

    # 5. Echte Gruppen vs. Standalone ermitteln
    real_group_ids = {g['id'] for g in config.get('groups', []) if g['id'] != 'standalone'}
    gid = host_config.get('group')
    target_id = gid if (gid and gid in real_group_ids) else host_id

    os.makedirs(status_dir, exist_ok=True)
    status_file = os.path.join(status_dir, f"{target_id}.json")

    # 6. Status-Datei laden oder initialisieren
    if os.path.exists(status_file):
        with open(status_file, 'r') as f:
            data = json.load(f)
    else:
        display_name = host_config['display_name'] if target_id == host_id else \
            next((g['name'] for g in config.get('groups', []) if g['id'] == target_id), target_id)
        data = {
            "id": target_id,
            "display_name": display_name,
            "is_group": target_id != host_id,
            "entries": {}
        }

    # Status anpassen, falls es ein Downtime-Event ist
    final_status = status
    if n_type == "DOWNTIMESTART":
        final_status = "MAINTENANCE"
    elif n_type in ["DOWNTIMEEND", "DOWNTIMECANCELLED"]:
        final_status = "UPDATING"

    # Eintrag schreiben
    entry_key = f"{host_id}:{service}"
    data["entries"][entry_key] = {
        "host": host_id,
        "service": service,
        "status": final_status,
        "output": output,
        "last_update": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    # Overall Status neu berechnen
    sev = 0
    has_data = False
    for info in data["entries"].values():
        s = info.get('status', 'pending').upper()
        if s == 'PENDING':
            continue
        has_data = True
        if s in ['CRITICAL', 'DOWN']:
            h_c = next((h for h in config.get('hosts', []) if h['id'] == info['host']), {})
            s_c = next((sc for sc in h_c.get('services', []) if sc['name'] == info['service']), {"impact": "minor"})
            sev = max(sev, 2 if s_c.get('impact') == 'critical' or info['service'] == 'Host' else 1)
        elif s in ['WARNING', 'IMPAIRED']:
            sev = max(sev, 1)

    data["overall_status"] = {0: "operational", 1: "impaired", 2: "critical"}[sev] if has_data else "pending"

    with open(status_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✅ [CORE SUCCESS] Updated '{entry_key}' -> {final_status}")
    print(f"   Target File: {status_file} (Overall: {data['overall_status']})")
    print("=" * 60)
    return True
