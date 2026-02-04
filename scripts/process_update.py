import os
import json
import requests
from datetime import datetime

def manage_issues(host, service, status, output, host_config):
    token = os.getenv('GH_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY')
    assignee = host_config.get('assignee', 'admin')
    issue_title = f"Alert: {host} - {service}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Suche nach offenem Issue
    search_url = f"https://api.github.com/search/issues?q=repo:{repo}+type:issue+state:open+in:title+\"{issue_title}\""
    try:
        search_res = requests.get(search_url, headers=headers).json()
        items = search_res.get('items', [])
        existing_issue = items[0] if items else None

        if status in ['CRITICAL', 'DOWN', 'WARNING'] and not existing_issue:
            issue_data = {
                "title": issue_title,
                "body": f"### Service Alert\n**Host:** {host}\n**Service:** {service}\n**Status:** {status}\n\n**Output:**\n{output}",
                "assignees": [assignee],
                "labels": ["incident", status.lower()]
            }
            requests.post(f"https://api.github.com/repos/{repo}/issues", json=issue_data, headers=headers)
        
        elif status in ['OK', 'UP'] and existing_issue:
            num = existing_issue['number']
            requests.patch(f"https://api.github.com/repos/{repo}/issues/{num}", json={"state": "closed"}, headers=headers)
            requests.post(f"https://api.github.com/repos/{repo}/issues/{num}/comments", json={"body": f"Resolved: Status is now {status}"}, headers=headers)
    except Exception as e:
        print(f"Fehler im Issue-Management: {e}")

def main():
    payload_raw = os.getenv('PAYLOAD')
    status_dir = os.getenv('STATUS_DIR', 'gh-pages/status')
    config_file = os.getenv('CONFIG_JSON_PATH', 'main/config.json')
    
    if not payload_raw:
        print("Fehler: PAYLOAD fehlt.")
        return
    
    payload = json.loads(payload_raw)
    host, service, status, output = payload['host'], payload['service'], payload['status'], payload['output']
    
    with open(config_file, 'r') as f:
        config = json.load(f)

    host_config = next((h for h in config.get('hosts', []) if h['id'] == host), None)
    if not host_config:
        print(f"Host {host} nicht in config.json.")
        return

    # Host-Datei laden/erstellen
    os.makedirs(status_dir, exist_ok=True)
    host_file = os.path.join(status_dir, f"{host}.json")
    
    if os.path.exists(host_file):
        with open(host_file, 'r') as f:
            host_data = json.load(f)
    else:
        host_data = {"id": host, "display_name": host_config['display_name'], "services": {}}

    # Service-Status aktualisieren
    host_data["services"][service] = {
        "status": status,
        "output": output,
        "last_update": datetime.utcnow().isoformat() + "Z"
    }

    # Globalen Host-Status berechnen
    severity = 0 # 0: operational, 1: impaired, 2: critical
    for s_name, s_info in host_data["services"].items():
        conf_svc = next((s for s in host_config['services'] if s['name'] == s_name), {"impact": "minor"})
        if s_info['status'] in ['CRITICAL', 'DOWN']:
            severity = max(severity, 2 if conf_svc['impact'] == 'critical' else 1)
        elif s_info['status'] == 'WARNING':
            severity = max(severity, 1)

    status_map = {0: "operational", 1: "impaired", 2: "critical"}
    host_data["overall_status"] = status_map[severity]

    with open(host_file, 'w') as f:
        json.dump(host_data, f, indent=2)

    manage_issues(host, service, status, output, host_config)

if __name__ == "__main__":
    main()
    
