import os
import json
from datetime import datetime, timezone

def generate_change_id(changelog_data):
    now = datetime.now(timezone.utc)
    prefix = f"CH{now.strftime('%y')}00{now.strftime('%m%d')}"
    
    daily_count = 1
    today_str = now.strftime('%Y-%m-%d')
    
    for entry in changelog_data:
        if entry.get('date', '').startswith(today_str):
            daily_count += 1
            
    return f"{prefix}-{daily_count}"

def main():
    config_file = os.getenv('CONFIG_JSON_PATH', 'main/config.json')
    status_dir = os.getenv('STATUS_DIR', 'gh-pages/status')
    changelog_file = os.path.join(status_dir, 'changelog.json')
    
    if not os.path.exists(config_file): 
        print(f"Error: Config file {config_file} not found at {config_file}")
        return

    with open(config_file, 'r') as f:
        config = json.load(f)

    os.makedirs(status_dir, exist_ok=True)
    
    # 1. Aktive Target-IDs aus config.json ermitteln
    active_target_ids = set()
    for host in config.get('hosts', []):
        gid = host.get('group', 'standalone')
        target_id = host['id'] if gid == 'standalone' else gid
        active_target_ids.add(target_id)

    for group in config.get('groups', []):
        active_target_ids.add(group['id'])

    # System-Dateien, die NIEMALS gelöscht werden dürfen
    protected_files = {'changelog.json', 'maintenance.json'}

    # 2. Physisch vorhandene JSON-Dateien im Verzeichnis scannen
    present_files_map = {} # {'host1': 'host1.json'}
    for fname in os.listdir(status_dir):
        if fname.endswith('.json') and fname not in protected_files:
            # Sauber die Endung .json abschneiden
            target_id = fname[:-5]
            present_files_map[target_id] = fname

    # 3. Neue und zu löschende Targets bestimmen
    new_hosts_found = []
    for host in config.get('hosts', []):
        gid = host.get('group', 'standalone')
        target_id = host['id'] if gid == 'standalone' else gid
        
        if target_id not in present_files_map and target_id not in [h['id'] for h in new_hosts_found]:
            new_hosts_found.append({'id': target_id, 'name': host.get('display_name', target_id)})

    removed_target_ids = [tid for tid in present_files_map.keys() if tid not in active_target_ids]

    # 4. CHANGELOG GENERIEREN (NUR wenn wirklich Änderungen vorliegen)
    if new_hosts_found or removed_target_ids:
        changelog_data = []
        if os.path.exists(changelog_file):
            try:
                with open(changelog_file, 'r') as f:
                    changelog_data = json.load(f)
            except json.JSONDecodeError:
                changelog_data = []
        
        changes = []
        for h in new_hosts_found:
            changes.append(f"New host added: {h['name']} ({h['id']})")
        for tid in removed_target_ids:
            changes.append(f"Host or group removed: {tid}")

        change_id = generate_change_id(changelog_data)
        new_entry = {
            "date": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "version": "Infrastructure Update",
            "change_id": change_id,
            "title": "Automated Infrastructure Update",
            "changes": changes
        }
        
        changelog_data.insert(0, new_entry)
        with open(changelog_file, 'w') as f:
            json.dump(changelog_data, f, indent=2)
        print(f"Changelog updated: {change_id}")

    # 5. VERWAISTE DATEIEN HARD LÖSCHEN
    for tid in removed_target_ids:
        fname = present_files_map[tid]
        file_path = os.path.join(status_dir, fname)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"SUCCESS: File {file_path} permanently deleted.")
            except Exception as e:
                print(f"ERROR: Could not delete {file_path}: {e}")

    # 6. AKTUELLE TARGET-DATEIEN AKTUALISIEREN / ERSTELLEN
    for target_id in active_target_ids:
        file_path = os.path.join(status_dir, f"{target_id}.json")
        old_data = {"entries": {}}
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    old_data = json.load(f)
            except json.JSONDecodeError:
                old_data = {"entries": {}}

        new_data = {"id": target_id, "entries": {}, "overall_status": "pending"}
        group = next((g for g in config.get('groups', []) if g['id'] == target_id), None)
        
        if group:
            new_data.update({"display_name": group['name'], "is_group": True})
            relevant_hosts = [h for h in config.get('hosts', []) if h.get('group') == target_id]
        else:
            host = next((h for h in config.get('hosts', []) if h['id'] == target_id), None)
            if not host:
                continue
            new_data.update({"display_name": host['display_name'], "is_group": False})
            relevant_hosts = [host]

        for r_host in relevant_hosts:
            all_services = [{"name": "Host"}] + r_host.get('services', [])
            for svc in all_services:
                key = f"{r_host['id']}:{svc['name']}"
                if key in old_data.get("entries", {}):
                    new_data["entries"][key] = old_data["entries"][key]
                else:
                    new_data["entries"][key] = {
                        "host": r_host['id'], 
                        "service": svc['name'],
                        "status": "pending", 
                        "output": "Waiting for data...", 
                        "last_update": None
                    }

        # Overall Status Berechnung
        sev = 0
        has_data = False
        for e in new_data["entries"].values():
            if e['status'] == 'pending': 
                continue
            has_data = True
            if e['status'] in ['CRITICAL', 'DOWN']:
                h_c = next((h for h in config.get('hosts', []) if h['id'] == e['host']), {})
                s_c = next((s for s in h_c.get('services', []) if s['name'] == e['service']), {"impact": "minor"})
                sev = max(sev, 2 if s_c.get('impact') == 'critical' or e['service'] == 'Host' else 1)
            elif e['status'] == 'WARNING': 
                sev = max(sev, 1)

        new_data["overall_status"] = {0: "operational", 1: "impaired", 2: "critical"}[sev] if has_data else "pending"

        with open(file_path, 'w') as f:
            json.dump(new_data, f, indent=2)

if __name__ == "__main__":
    main()
