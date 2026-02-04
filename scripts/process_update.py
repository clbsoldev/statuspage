import os
import json
import requests
from datetime import datetime

def main():
    payload_raw = os.getenv('PAYLOAD')
    status_dir = os.getenv('STATUS_DIR', 'gh-pages/status')
    config_file = os.getenv('CONFIG_JSON_PATH', 'main/config.json')
    
    if not payload_raw: return
    payload = json.loads(payload_raw)
    host, service, status, output = payload['host'], payload['service'], payload['status'], payload['output']
    
    # 1. Config laden
    with open(config_file, 'r') as f:
        config = json.load(f)

    host_config = next((h for h in config.get('hosts', []) if h['id'] == host), None)
    if not host_config: return

    # 2. Host-spezifische Datei laden/erstellen
    os.makedirs(status_dir, exist_ok=True)
    host_file = os.path.join(status_dir, f"{host}.json")
    
    if os.path.exists(host_file):
        with open(host_file, 'r') as f:
            host_data = json.load(f)
    else:
        host_data = {"id": host, "display_name": host_config['display_name'], "services": {}}

    # 3. Service Update
    host_data["services"][service] = {
        "status": status,
        "output": output,
        "last_update": datetime.utcnow().isoformat() + "Z"
    }

    # 4. Globalen Host-Status berechnen
    # Wir mappen Nagios-Status + Impact auf Statuspage-Schweregrad
    overall_severity = 0 # 0: OK, 1: Impaired (minor/warning), 2: Critical (major/critical)
    
    for s_name, s_info in host_data["services"].items():
        # Finde Impact-Vorgabe aus Config für diesen Service
        conf_svc = next((s for s in host_config['services'] if s['name'] == s_name), {"impact": "minor"})
        
        if s_info['status'] in ['CRITICAL', 'DOWN']:
            if conf_svc['impact'] == 'critical': overall_severity = max(overall_severity, 2)
            else: overall_severity = max(overall_severity, 1)
        elif s_info['status'] == 'WARNING':
            overall_severity = max(overall_severity, 1)

    status_map = {0: "operational", 1: "impaired", 2: "critical"}
    host_data["overall_status"] = status_map[overall_severity]

    with open(host_file, 'w') as f:
        json.dump(host_data, f, indent=2)

    # 5. Issue Management (wie bisher...)
    # [Code gekürzt für Übersichtlichkeit, bleibt identisch zum Vorherigen]
    manage_issues(host, service, status, output, host_config)

def manage_issues(host, service, status, output, host_config):
    # (Hier kommt die bekannte Issue-Logik rein)
    pass

if __name__ == "__main__":
    main()
    
