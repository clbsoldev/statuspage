import os
import json

def main():
    config_file = 'main/config.json'
    status_dir = 'gh-pages/status'
    
    if not os.path.exists(config_file): return
    with open(config_file, 'r') as f:
        config = json.load(f)

    os.makedirs(status_dir, exist_ok=True)

    # Alle IDs sammeln, die laut Config existieren müssen
    active_target_ids = set()
    for host in config.get('hosts', []):
        gid = host.get('group', 'standalone')
        active_target_ids.add(host['id'] if gid == 'standalone' else gid)

    # 1. Verwaiste Dateien löschen (Hosts/Gruppen die entfernt wurden)
    for filename in os.listdir(status_dir):
        if not filename.endswith('.json'): continue
        tid = filename.replace('.json', '')
        if tid not in active_target_ids:
            os.remove(os.path.join(status_dir, filename))
            print(f"Entferne verwaiste Datei: {filename}")

    # 2. Strukturen synchronisieren
    for target_id in active_target_ids:
        file_path = os.path.join(status_dir, f"{target_id}.json")
        
        old_data = {"entries": {}, "overall_status": "pending"}
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                old_data = json.load(f)

        new_data = {
            "id": target_id,
            "entries": {},
            "overall_status": "pending"
        }

        # Metadaten aus config.json
        group = next((g for g in config.get('groups', []) if g['id'] == target_id), None)
        if group:
            new_data.update({"display_name": group['name'], "is_group": True})
            relevant_hosts = [h for h in config.get('hosts', []) if h.get('group') == target_id]
        else:
            host = next((h for h in config.get('hosts', []) if h['id'] == target_id), None)
            new_data.update({"display_name": host['display_name'], "is_group": False})
            relevant_hosts = [host]

        # Services abgleichen (Hinzufügen & Entfernen)
        for r_host in relevant_hosts:
            for svc in r_host.get('services', []):
                svc_key = f"{r_host['id']}:{svc['name']}"
                
                if svc_key in old_data["entries"]:
                    # Bestehende Daten behalten
                    new_data["entries"][svc_key] = old_data["entries"][svc_key]
                else:
                    # Neu initialisieren (No Data)
                    new_data["entries"][svc_key] = {
                        "host": r_host['id'],
                        "service": svc['name'],
                        "status": "pending",
                        "output": "Warte auf Daten...",
                        "last_update": None
                    }

        # Status neu berechnen (falls ein kritischer Service entfernt wurde)
        severity = 0
        has_real_data = False
        for info in new_data["entries"].values():
            if info['status'] == 'pending': continue
            has_real_data = True
            if info['status'] in ['CRITICAL', 'DOWN']:
                h_conf = next((h for h in config.get('hosts', []) if h['id'] == info['host']), {})
                s_conf = next((s for s in h_conf.get('services', []) if s['name'] == info['service']), {"impact": "minor"})
                severity = max(severity, 2 if s_conf.get('impact') == 'critical' or info['service'] == 'Host' else 1)
            elif info['status'] == 'WARNING':
                severity = max(severity, 1)
        
        if has_real_data:
            new_data["overall_status"] = {0: "operational", 1: "impaired", 2: "critical"}[severity]
        else:
            new_data["overall_status"] = "pending"

        with open(file_path, 'w') as f:
            json.dump(new_data, f, indent=2)

if __name__ == "__main__":
    main()
