import os
import json
import sys
from datetime import datetime, timezone

def update_maintenance_json(status_dir, payload):
    m_file = os.path.join(status_dir, "maintenance.json")
    
    # Datei laden oder Grundstruktur erstellen
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
    n_type = payload.get('type', 'NOTIFICATION')
    # Der Kommentar von Nagios kommt über das Output-Feld
    comment = payload.get('output', 'Wartungsarbeiten')
    ts_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if n_type == "DOWNTIMESTART":
        # Bestehende Einträge für diesen Service entfernen (Vermeidung von Dubletten)
        data["active"] = [x for x in data["active"] if not (x['host'] == h and x['service'] == s)]
        # Neuen aktiven Wartungseintrag mit dem Nagios-Kommentar hinzufügen
        data["active"].append({
            "host": h,
            "service": s,
            "start": ts_now,
            "reason": comment
        })

    elif n_type in ["DOWNTIMEEND", "DOWNTIMECANCELLED"]:
        # Eintrag aus active suchen und nach past verschieben
        active_entry = next((x for x in data["active"] if x['host'] == h and x['service'] == s), None)
        if active_entry:
            data["active"] = [x for x in data["active"] if not (x['host'] == h and x['service'] == s)]
            active_entry["end"] = ts_now
            data["past"].insert(0, active_entry)
            # Historie auf 10 Einträge begrenzen
            data["past"] = data["past"][:10]

    # Speichern der maintenance.json
    with open(m_file, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    # Pfad zum Status-Ordner (relativ zum Repo-Root)
    status_dir = "status"
    if not os.path.exists(status_dir):
        os.makedirs(status_dir)

    # Payload von stdin lesen (wird von der Action/CLI übergeben)
    try:
        payload = json.loads(sys.stdin.read())
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return

    host = payload.get('host')
    service = payload.get('service')
    status = payload.get('status', 'PENDING')

    if not host or not service:
        print("Missing host or service in payload")
        return

    # 1. Einzel-Statusdatei aktualisieren (host.json)
    host_file = os.path.join(status_dir, f"{host}.json")
    if os.path.exists(host_file):
        with open(host_file, 'r') as f:
            host_data = json.load(f)
    else:
        host_data = {
            "host": host,
            "display_name": host,
            "overall_status": "UP",
            "entries": {}
        }

    # Eintrag aktualisieren
    host_data["entries"][service] = {
        "service": service,
        "status": status,
        "last_update": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "output": payload.get('output', '')
    }

    # Overall Status berechnen (einfache Logik)
    all_stats = [e['status'].upper() for e in host_data["entries"].values()]
    if "CRITICAL" in all_stats or "DOWN" in all_stats:
        host_data["overall_status"] = "CRITICAL"
    elif "WARNING" in all_stats or "MAINTENANCE" in all_stats:
        host_data["overall_status"] = "WARNING"
    else:
        host_data["overall_status"] = "OPERATIONAL"

    with open(host_file, 'w') as f:
        json.dump(host_data, f, indent=2)

    # 2. Wartungs-Logik verarbeiten
    if "DOWNTIME" in payload.get('type', ''):
        update_maintenance_json(status_dir, payload)

if __name__ == "__main__":
    main()
