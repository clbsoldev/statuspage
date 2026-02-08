import os
import json
import sys
import requests
from datetime import datetime, timezone

def update_maintenance_json(status_dir, payload):
    m_file = os.path.join(status_dir, "maintenance.json")
    
    if os.path.exists(m_file):
        try:
            with open(m_file, 'r') as f:
                data = json.load(f)
        except:
            data = {"active": [], "past": []}
    else:
        data = {"active": [], "past": []}

    h = payload.get('host')
    s = payload.get('service')
    n_type = str(payload.get('type', 'NOTIFICATION')).upper()
    comment = payload.get('output', 'Wartungsarbeiten')
    ts_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if n_type == "DOWNTIMESTART":
        data["active"] = [x for x in data["active"] if not (x['host'] == h and x['service'] == s)]
        data["active"].append({
            "host": h, "service": s, "start": ts_now, "reason": comment
        })
    elif n_type in ["DOWNTIMEEND", "DOWNTIMECANCELLED"]:
        active_entry = next((x for x in data["active"] if x['host'] == h and x['service'] == s), None)
        if active_entry:
            data["active"] = [x for x in data["active"] if not (x['host'] == h and x['service'] == s)]
            active_entry["end"] = ts_now
            data["past"].insert(0, active_entry)
            data["past"] = data["past"][:10]

    with open(m_file, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    status_dir = "status"
    if not os.path.exists(status_dir):
        os.makedirs(status_dir)

    # WICHTIG: Wir holen uns den Payload direkt aus der ENV Variable, 
    # so wie dein Workflow sie bereitstellt.
    payload_str = os.environ.get('PAYLOAD')

    if not payload_str:
        print("Error: Environment variable PAYLOAD is empty or not set.")
        return

    try:
        payload = json.loads(payload_str)
    except Exception as e:
        print(f"Error parsing JSON from PAYLOAD env: {e}")
        return

    host = payload.get('host')
    service = payload.get('service')
    status = str(payload.get('status', 'PENDING')).upper()
    output = payload.get('output', '')
    n_type = str(payload.get('type', 'NOTIFICATION')).upper()
    
    if not host or not service:
        print("Missing host or service in payload")
        return

    # GitHub Issue Kommentar (Zeile 56 Logik)
    token = os.environ.get('GH_TOKEN') # Holen wir uns auch aus der ENV
    repo = payload.get('repo')
    num = payload.get('issue_number')
    if token and repo and num:
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        try:
            requests.post(f"https://api.github.com/repos/{repo}/issues/{num}/comments", 
                          json={"body": f"Resolved: {status}\nOutput: {output}"}, headers=headers)
        except: pass

    # Einzel-Statusdatei (host.json)
    host_file = os.path.join(status_dir, f"{host}.json")
    if os.path.exists(host_file):
        with open(host_file, 'r') as f:
            host_data = json.load(f)
    else:
        host_data = {"host": host, "display_name": host, "overall_status": "UP", "entries": {}}

    # Kompatibilitäts-Check
    if "services" in host_data and "entries" not in host_data:
        host_data["entries"] = host_data.pop("services")

    # Status-Korrektur für Custom Notifications
    if n_type == "CUSTOM" and "Downtime Ended" in output:
        status = "OPERATIONAL"

    host_data["entries"][service] = {
        "service": service, "status": status,
        "last_update": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "output": output
    }

    # Overall Status berechnen
    all_stats = [e['status'].upper() for e in host_data["entries"].values()]
    if any(s in ["CRITICAL", "DOWN"] for s in all_stats):
        host_data["overall_status"] = "CRITICAL"
    elif any(s in ["WARNING", "MAINTENANCE"] for s in all_stats):
        host_data["overall_status"] = "WARNING"
    else:
        host_data["overall_status"] = "OPERATIONAL"

    with open(host_file, 'w') as f:
        json.dump(host_data, f, indent=2)

    # Wartungs-Logik nur bei Downtime-Events
    if "DOWNTIME" in n_type:
        update_maintenance_json(status_dir, payload)

if __name__ == "__main__":
    main()
