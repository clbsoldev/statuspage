import os
import json

def main():
    config_file = 'main/config.json'
    status_dir = 'gh-pages/status'
    
    if not os.path.exists(config_file): return
    with open(config_file, 'r') as f:
        config = json.load(f)

    os.makedirs(status_dir, exist_ok=True)

    active_target_ids = set()
    for host in config.get('hosts', []):
        gid = host.get('group', 'standalone')
        active_target_ids.add(host['id'] if gid == 'standalone' else gid)

    # 1. Verwaiste Dateien entfernen
    for filename in os.listdir(status_dir):
        if not filename.endswith('.json'): continue
        if filename.replace('.json', '') not in active_target_ids:
            os.remove(os.path.join(status_dir, filename))

    # 2. Synchronisieren
    for target_id in active_target_ids:
        file_path = os.path.join(status_dir, f"{target_id}.json")
        old_data = {"entries": {}}
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                old_data = json.load(f)

        new_data = {"id": target_id, "entries": {}, "overall_status": "pending"}

        group = next((g for g in config.get('groups', []) if g['id'] == target_id), None)
        if group:
            new_data.update({"display_name": group['name'], "is_group": True})
            relevant_hosts = [h for h in config.get('hosts', []) if h.get('group') == target_id]
        else:
            host = next((h for h in config.get('hosts', []) if h['id'] == target_id), None)
            new_data.update({"display_name": host['display_name'], "is_group": False})
            relevant_hosts = [host]

        # Alle Services pro Host in der Datei halten (für Issue-Management-Referenz)
        for r_host in relevant_hosts:
            for svc in r_host.get('services', []):
                key = f"{r_host['id']}:{svc['name']}"
                if key in old_data.get("entries", {}):
                    new_data["entries"][key] = old_data["entries"][key]
                else:
                    new_data["entries"][key] = {
                        "host": r_host['id'], "service": svc['name'],
                        "status": "pending", "output": "No data yet", "last_update": None
                    }

        # Overall Status Berechnung
        sev = 0
        has_data = False
        for e in new_data["entries"].values():
            if e['status'] == 'pending': continue
            has_data = True
            if e['status'] in ['CRITICAL', 'DOWN']:
                # Impact Check
                h_c = next((h for h in config.get('hosts', []) if h['id'] == e['host']), {})
                s_c = next((s for s in h_c.get('services', []) if s['name'] == e['service']), {"impact": "minor"})
                sev = max(sev, 2 if s_c.get('impact') == 'critical' or e['service'] == 'Host' else 1)
            elif e['status'] == 'WARNING': sev = max(sev, 1)

        if has_data:
            new_data["overall_status"] = {0: "operational", 1: "impaired", 2: "critical"}[sev]

        with open(file_path, 'w') as f:
            json.dump(new_data, f, indent=2)

if __name__ == "__main__":
    main()
