import os
import json
import requests
from datetime import datetime

def main():
    payload_raw = os.getenv('PAYLOAD')
    # Wir nutzen Umgebungsvariablen für die Pfade, um flexibel zu bleiben
    status_file = os.getenv('STATUS_JSON_PATH', 'status.json')
    config_file = os.getenv('CONFIG_JSON_PATH', 'config.json')
    
    if not payload_raw:
        print("Fehler: Keine PAYLOAD Daten gefunden.")
        return
    
    payload = json.loads(payload_raw)
    host = payload.get('host')
    service = payload.get('service')
    status = payload.get('status')
    output = payload.get('output')
    token = os.getenv('GH_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY')

    print(f"Verarbeite Update für {host} - {service} (Status: {status})")

    # 1. Config laden
    if not os.path.exists(config_file):
        print(f"Fehler: Konfigurationsdatei nicht gefunden unter: {config_file}")
        return
        
    with open(config_file, 'r') as f:
        config = json.load(f)

    host_config = next((h for h in config.get('hosts', []) if h['id'] == host), None)
    if not host_config:
        print(f"Host {host} nicht in config.json gefunden. Überspringe.")
        return

    # 2. Status-Daten (status.json) laden/aktualisieren
    status_data = {}
    if os.path.exists(status_file):
        with open(status_file, 'r') as f:
            try:
                status_data = json.load(f)
            except json.JSONDecodeError:
                status_data = {}

    if host not in status_data:
        status_data[host] = {}
    
    status_data[host][service] = {
        "status": status,
        "output": output,
        "last_update": datetime.utcnow().isoformat() + "Z"
    }

    # Verzeichnis für status.json sicherstellen
    os.makedirs(os.path.dirname(status_file) or '.', exist_ok=True)
    with open(status_file, 'w') as f:
        json.dump(status_data, f, indent=2)
    print(f"status.json aktualisiert unter: {status_file}")

    # 3. Issue Management
    issue_title = f"Alert: {host} - {service}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    search_url = f"https://api.github.com/search/issues?q=repo:{repo}+type:issue+state:open+in:title+\"{issue_title}\""
    try:
        search_res = requests.get(search_url, headers=headers).json()
        existing_issue = search_res['items'][0] if search_res.get('items') else None

        if status in ['CRITICAL', 'DOWN', 'WARNING'] and not existing_issue:
            issue_data = {
                "title": issue_title,
                "body": f"### Service Alert\n**Host:** {host}\n**Service:** {service}\n**Status:** {status}\n\n**Output:**\n{output}",
                "assignees": [host_config.get('assignee', 'admin')],
                "labels": ["incident", status.lower()]
            }
            requests.post(f"https://api.github.com/repos/{repo}/issues", json=issue_data, headers=headers)
            print("Neues Issue erstellt.")
        
        elif status in ['OK', 'UP'] and existing_issue:
            num = existing_issue['number']
            requests.patch(f"https://api.github.com/repos/{repo}/issues/{num}", json={"state": "closed"}, headers=headers)
            requests.post(f"https://api.github.com/repos/{repo}/issues/{num}/comments", json={"body": f"Resolved: Status ist jetzt {status}"}, headers=headers)
            print(f"Issue #{num} geschlossen.")
    except Exception as e:
        print(f"Fehler beim Issue-Management: {e}")

if __name__ == "__main__":
    main()
  
