import os
import json
from datetime import datetime, timezone

def update_maintenance_json(host, service, msg_type, output):
    maint_file = 'gh-pages/status/maintenance.json'
    os.makedirs(os.path.dirname(maint_file), exist_ok=True)
    
    if not os.path.exists(maint_file):
        data = {"active": [], "past": []}
    else:
        with open(maint_file, 'r') as f: data = json.load(f)

    now = datetime.now(timezone.utc).isoformat()

    if msg_type == 'DOWNTIMESTART':
        # Falls schon drin (Doublette), erst raus
        data["active"] = [a for a in data["active"] if not (a['host'] == host and a['service'] == service)]
        data["active"].append({"host": host, "service": service, "start": now, "reason": output})
    
    elif msg_type in ['DOWNTIMEEND', 'DOWNTIMECANCELLED']:
        new_active = []
        for a in data["active"]:
            if a['host'] == host and a['service'] == service:
                a['end'] = now
                data["past"].insert(0, a)
            else:
                new_active.append(a)
        data["active"] = new_active
        data["past"] = data["past"][:15] # Die letzten 15 Einträge behalten

    with open(maint_file, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    payload_raw = os.getenv('PAYLOAD')
    status_dir = 'gh-pages/status'
    config_file = 'main/config.json'
    
    if not payload_raw: return
    payload = json.loads(payload_raw)
    
    host_id = payload['host']
    service = payload.get('service', 'Host')
    msg_type = payload.get('type', 'CUSTOM')
    raw_status = payload['status']
    output = payload['output']

    # 1. Maintenance Liste aktualisieren
    if 'DOWNTIME' in msg_type:
        update_maintenance_json(host_id, service, msg_type, output)

    # 2. Status-Logik bestimmen
    status = raw_status
    if msg_type == 'DOWNTIMESTART':
        status = 'MAINTENANCE'
    elif msg_type in ['DOWNTIMEEND', 'DOWNTIMECANCELLED']:
        status = 'UPDATING' # Brückenstatus für das Frontend

    # 3. Datei-Speicherung (Host/Gruppe finden)
    with open(config_file, 'r') as f: config = json.load(f)
    host_cfg = next((h for h in config['hosts'] if h['id'] == host_id), None)
    if not host_cfg: return
    
    target_id = host_id if host_cfg.get('group', 'standalone') == 'standalone' else host_cfg['group']
    status_file = os.path.join(status_dir, f"{target_id}.json")

    with open(status_file, 'r') as f: data = json.load(f)
    
    data["entries"][f"{host_id}:{service}"] = {
        "host": host_id, "service": service, "status": status,
        "output": output, "last_update": datetime.now(timezone.utc).isoformat()
    }

    # Overall Status Berechnung
    states = [e['status'].upper() for e in data["entries"].values()]
    if 'CRITICAL' in states or 'DOWN' in states: data['overall_status'] = 'critical'
    elif 'WARNING' in states or 'IMPAIRED' in states: data['overall_status'] = 'impaired'
    elif 'MAINTENANCE' in states: data['overall_status'] = 'maintenance'
    elif 'UPDATING' in states: data['overall_status'] = 'updating'
    else: data['overall_status'] = 'operational'

    with open(status_file, 'w') as f: json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
