import json
import os
import sys
import subprocess
from datetime import datetime

def load_json(file_path, default=None):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return default if default is not None else {}

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    # Input von GitHub Action Payload
    payload = json.loads(sys.argv[1])
    host_id = payload.get('host')
    service_name = payload.get('service')
    new_status = payload.get('status') # 'online', 'offline', 'impaired'

    config = load_json('config.json')
    
    # 1. Host Validierung
    host_config = next((h for h in config.get('hosts', []) if h['id'] == host_id), None)
    if not host_config:
        print(f"Host {host_id} nicht in config.json gefunden.")
        sys.exit(0)

    # 2. Status-Datei des Hosts laden/erstellen
    status_path = f"status/{host_id}.json"
    history_path = f"history/{host_id}.json"
    status_data = load_json(status_path, {"overall": "online", "services": {}, "active_issue": None})

    old_overall = status_data['overall']
    status_data['services'][service_name] = new_status

    # 3. Aggregation basierend auf Impact
    # Wir prüfen alle in der Config definierten Services für diesen Host
    current_overall = "online"
    for s_conf in host_config.get('services', []):
        s_name = s_conf['name']
        s_stat = status_data['services'].get(s_name, 'online')
        
        if s_stat != 'online':
            if s_conf.get('impact') == 'critical':
                current_overall = "down"
                break
            else:
                current_overall = "impaired"
    
    status_data['overall'] = current_overall
    status_data['last_update'] = datetime.now().isoformat()

    # 4. Issue Management (GitHub CLI)
    if current_overall != "online" and old_overall == "online":
        assignee = host_config.get('assignee', 'admin')
        title = f"🔴 Incident: {host_id} is {current_overall}"
        body = f"Host {host_id} meldet Probleme beim Service: {service_name} ({new_status})."
        # Issue erstellen und URL speichern
        issue_cmd = f"gh issue create --title '{title}' --body '{body}' --assignee {assignee}"
        issue_url = subprocess.check_output(issue_cmd, shell=True).decode().strip()
        status_data['active_issue'] = issue_url

    elif current_overall == "online" and old_overall != "online":
        if status_data.get('active_issue'):
            subprocess.run(f"gh issue close {status_data['active_issue']} --comment 'System recovered.'", shell=True)
            status_data['active_issue'] = None

    # 5. Speichern
    save_json(status_path, status_data)
    
    # History Eintrag hinzufügen
    history = load_json(history_path, [])
    history.insert(0, {"t": datetime.now().isoformat(), "s": current_overall, "msg": f"{service_name}: {new_status}"})
    save_json(history_path, history[:50]) # Letzte 50 Einträge

if __name__ == "__main__":
    main()
