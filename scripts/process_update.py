import os
import json
import requests
from datetime import datetime, timezone

def update_maintenance_json(status_dir, payload):
    m_file = os.path.join(status_dir, "maintenance.json")
    data = {"active": [], "past": []}
    if os.path.exists(m_file):
        try:
            with open(m_file, 'r') as f: data = json.load(f)
        except: pass

    h, s = payload['host'], payload['service']
    n_type = payload.get('type', 'NOTIFICATION')
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if n_type == "DOWNTIMESTART":
        data["active"] = [x for x in data["active"] if not (x['host'] == h and x['service'] == s)]
        data["active"].append({"host": h, "service": s, "start": ts, "reason": payload.get('output', 'Wartung')})
    elif n_type in ["DOWNTIMEEND", "DOWNTIMECANCELLED"]:
        for item in data["active"][:]:
            if item['host'] == h and item['service'] == s:
                item['end'] = ts
                data["past"].insert(0, item)
                data["active"].remove(item)
        data["past"] = data["past"][:10]

    with open(m_file, 'w') as f:
        json.dump(data, f, indent=2)

def manage_issues(host_id, service, status, output, host_config):
    token = os.getenv('GH_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY')
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
            requests.post(f"https://api.github.com/repos/{repo}/issues", json=issue_data, headers=headers)
        elif status in ['OK', 'UP'] and existing_issue:
            num = existing_issue['number']
            requests.patch(f"https://api.github.com/repos/{repo}/issues/{num}", json={"state": "closed"}, headers=headers)
    except Exception as e:
        print(f"Issue Error: {e}")

def main():
    payload_raw = os.getenv('PAYLOAD')
    status_dir = os.getenv('STATUS_DIR', 'gh-pages/status')
    config_file = os.getenv('CONFIG_JSON_PATH', 'main/config.json')
    
    if not payload_raw: return
    payload = json.loads(payload_raw)
    host_id, service, status, output = payload['host'], payload['service'], payload['status'], payload['output']
    n_type = payload.get('type', 'NOTIFICATION')
    
    with open(config_file, 'r') as f:
        config = json.load(f)

    host_config = next((h for h in config.get('hosts', []) if h['id'] == host_id), None)
    if not host_config: return

    if "DOWNTIME" in n_type:
        update_maintenance_json(status_dir, payload)
    else:
        manage_issues(host_id, service, status, output, host_config)

    group_id = host_config.get('group', 'standalone')
    target_id = host_id if group_id == 'standalone' else group_id
    os.makedirs(status_dir, exist_ok=True)
    status_file = os.path.join(status_dir, f"{target_id}.json")
    
    if os.path.exists(status_file):
        with open(status_file, 'r') as f: data = json.load(f)
    else:
        display_name = host_config['display_name'] if group_id == 'standalone' else \
                       next((g['name'] for g in config.get('groups', []) if g['id'] == group_id), group_id)
        data = {"id": target_id, "display_name": display_name, "is_group": group_id != 'standalone', "entries": {}}

    # Status-Mapping
    final_status = status
    if n_type == "DOWNTIMESTART": final_status = "MAINTENANCE"
    elif n_type in ["DOWNTIMEEND", "DOWNTIMECANCELLED"]: final_status = "UPDATING"

    data["entries"][f"{host_id}:{service}"] = {
        "host": host_id, "service": service, "status": final_status, "output": output,
        "last_update": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    # SEVERITY BERECHNUNG
    severity = 0
    all_pending = True
    
    for key, info in data["entries"].items():
        s = info.get('status', 'pending').upper()
        if s != 'PENDING': all_pending = False
        
        if s in ['CRITICAL', 'DOWN']:
            # Host-Down oder Critical Impact führt zu Overall Critical
            severity = max(severity, 2)
        elif s == 'WARNING':
            severity = max(severity, 1)

    if all_pending:
        data["overall_status"] = "pending"
    else:
        data["overall_status"] = {0: "operational", 1: "impaired", 2: "critical"}[severity]

    with open(status_file, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
