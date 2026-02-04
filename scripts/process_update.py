import os
import json
import requests
from datetime import datetime, timezone

def manage_issues(host_id, service, status, output, host_config):
    token = os.getenv('GH_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY')
    assignee = host_config.get('assignee', 'admin')
    
    # Eindeutiger Titel für das GitHub Issue
    issue_title = f"Alert: {host_id} - {service}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        # Suche nach existierenden offenen Issues mit diesem Titel
        search_url = f"https://api.github.com/search/issues?q=repo:{repo}+type:issue+state:open+in:title+\"{issue_title}\""
        search_res = requests.get(search_url, headers=headers).json()
        items = search_res.get('items', [])
        existing_issue = items[0] if items else None

        # Erstelle Issue bei Fehlern (CRITICAL, DOWN, WARNING)
        if status in ['CRITICAL', 'DOWN', 'WARNING'] and not existing_issue:
            issue_data = {
                "title": issue_title,
                "body": f"### Service Alert\n**Host:** {host_id}\n**Service:** {service}\n**Status:** {status}\n\n**Output:**\n{output}",
                "assignees": [assignee],
                "labels": ["incident", status.lower()]
            }
            requests.post(f"https://api.github.com/repos/{repo}/issues", json=issue_data, headers=headers)
        
        # Schließe Issue, wenn der Status wieder OK/UP ist
        elif status in ['OK', 'UP'] and existing_issue:
            num = existing_issue['number']
            requests.patch(f"https://api.github.com/repos/{repo}/issues/{num}", json={"state": "closed"}, headers=headers)
            requests.post(f"https://api.github.com/repos/{repo}/issues/{num}/comments", json={"body": f"Resolved: {status}\nOutput: {output}"}, headers=headers)
    except Exception as e:
        print(f"Fehler im Issue-Management: {e}")

def main():
    payload_raw = os.getenv('PAYLOAD')
    status_dir = os.getenv('STATUS_DIR', 'gh-pages/status')
    config_file = os.getenv('CONFIG_JSON_PATH', 'main/config.json')
    
    if not payload_raw: return
    payload = json.loads(payload_raw)
    host_id, service, status, output = payload['host'], payload['service'], payload['status'], payload['output']
    
    with open(config_file, 'r') as f:
        config = json.load(f)

    host_config = next((h for h in config.get('hosts', []) if h['id'] == host_id), None)
    if not host_config: 
        print(f"Host {host_id} nicht in config.json gefunden.")
        return

    # Issue Management aufrufen
    manage_issues(host_id, service, status, output, host_config)

    # Dateipfad bestimmen (Aggregation in Gruppen-JSON falls konfiguriert)
    group_id = host_config.get('group', 'standalone')
    target_id = host_id if group_id == 'standalone' else group_id
    
    os.makedirs(status_dir, exist_ok=True)
    status_file = os.path.join(status_dir, f"{target_id}.json")
    
    if os.path.exists(status_file):
        with open(status_file, 'r') as f:
            data = json.load(f)
    else:
        display_name = host_config['display_name'] if group_id == 'standalone' else \
                       next((g['name'] for g in config.get('groups', []) if g['id'] == group_id), group_id)
        data = {"id": target_id, "display_name": display_name, "is_group": group_id != 'standalone', "entries": {}}

    # Migration alter Datenstrukturen
    if "services" in data and "entries" not in data:
        data["entries"] = data.pop("services")

    # Update des Eintrags (Nutzt jetzt die moderne timezone-aware datetime)
    data["entries"][f"{host_id}:{service}"] = {
        "host": host_id,
        "service": service,
        "status": status,
        "output": output,
        "last_update": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    # Berechnung des Gesamtstatus (Severity Logic)
    severity = 0
    for key, info in data["entries"].items():
        curr_status = info.get('status', 'OK')
        # Finde Impact in der config.json
        h_conf = next((h for h in config.get('hosts', []) if h['id'] == info['host']), {})
        s_list = h_conf.get('services', [])
        s_conf = next((s for s in s_list if s['name'] == info['service']), {"impact": "minor"})
        
        if curr_status in ['CRITICAL', 'DOWN']:
            severity = max(severity, 2 if s_conf.get('impact') == 'critical' or info['service'] == 'Host' else 1)
        elif curr_status == 'WARNING':
            severity = max(severity, 1)

    data["overall_status"] = {0: "operational", 1: "impaired", 2: "critical"}[severity]

    with open(status_file, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
