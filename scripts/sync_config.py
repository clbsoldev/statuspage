import os
import json
from datetime import datetime

def generate_change_id(changelog_data):
    now = datetime.now()
    # Format: CH + Jahr(2stellig) + 00 + Monat(2stellig) + Tag(2stellig)
    prefix = f"CH{now.strftime('%y')}00{now.strftime('%m%d')}"
    
    # Zähler für den heutigen Tag ermitteln
    daily_count = 1
    today_str = now.strftime('%Y-%m-%d')
    
    for entry in changelog_data:
        if entry.get('date', '').startswith(today_str):
            daily_count += 1
            
    return f"{prefix}-{daily_count}"

def main():
    config_file = 'main/config.json'
    status_dir = 'gh-pages/status'
    changelog_file = os.path.join(status_dir, 'changelog.json')
    
    if not os.path.exists(config_file): return
    with open(config_file, 'r') as f:
        config = json.load(f)

    os.makedirs(status_dir, exist_ok=True)
    
    # 1. Vorherigen Zustand erfassen (bevor wir löschen oder ändern)
    existing_files = [f.replace('.json', '') for f in os.listdir(status_dir) if f.endswith('.json') and f != 'changelog.json' and f != 'maintenance.json']
    
    active_target_ids = set()
    new_hosts_found = []
    for host in config.get('hosts', []):
        gid = host.get('group', 'standalone')
        target_id = host['id'] if gid == 'standalone' else gid
        active_target_ids.add(target_id)
        
        # Prüfen ob dieser Host neu ist (ID noch nicht als Datei vorhanden)
        if target_id not in existing_files and target_id not in [h['id'] for h in new_hosts_found]:
            new_hosts_found.append({'id': target_id, 'name': host.get('display_name', target_id)})

    # 2. Entfernte Hosts identifizieren
    removed_hosts = [fid for fid in existing_files if fid not in active_target_ids]

    # 3. Changelog-Eintrag erstellen, falls sich etwas geändert hat
    if new_hosts_found or removed_hosts:
        changelog_data = []
        if os.path.exists(changelog_file):
            with open(changelog_file, 'r') as f:
                changelog_data = json.load(f)
        
        change_id = generate_change_id(changelog_data)
        changes = []
        
        for h in new_hosts_found:
            changes.append(f"Neuer Host hinzugefügt: {h['name']} ({h['id']})")
        for fid in removed_hosts:
            changes.append(f"Host/Gruppe entfernt: {fid}")
            
        new_entry = {
            "date": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "version": "Infrastruktur-Update",
            "change_id": change_id,
            "title": "Automatisches Infrastruktur-Update",
            "changes": changes
        }
        
        # Neuen Eintrag oben anfügen
        changelog_data.insert(0, new_entry)
        with open(changelog_file, 'w') as f:
            json.dump(changelog_data, f, indent=2)

    # --- AB HIER: DEIN BESTEHENDER CODE FÜR DIE DATEI-VERARBEITUNG ---

    # Dateien löschen, die nicht mehr aktiv sind
    for filename in os.listdir(status_dir):
        if not filename.endswith('.json') or filename in ['changelog.json', 'maintenance.json']: continue
        if filename.replace('.json', '') not in active_target_ids:
            os.remove(os.path.join(status_dir, filename))

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

        for r_host in relevant_hosts:
            all_services = [{"name": "Host"}] + r_host.get('services', [])
            for svc in all_services:
                key = f"{r_host['id']}:{svc['name']}"
                if key in old_data.get("entries", {}):
                    new_data["entries"][key] = old_data["entries"][key]
                else:
                    new_data["entries"][key] = {
                        "host": r_host['id'], "service": svc['name'],
                        "status": "pending", "output": "Warte auf Daten...", "last_update": None
                    }

        # Overall Status Berechnung
        sev = 0
        has_data = False
        for e in new_data["entries"].values():
            if e['status'] == 'pending': continue
            has_data = True
            if e['status'] in ['CRITICAL', 'DOWN']:
                h_c = next((h for h in config.get('hosts', []) if h['id'] == e['host']), {})
                s_c = next((s for s in h_c.get('services', []) if s['name'] == e['service']), {"impact": "minor"})
                sev = max(sev, 2 if s_c.get('impact') == 'critical' or e['service'] == 'Host' else 1)
            elif e['status'] == 'WARNING': sev = max(sev, 1)

        new_data["overall_status"] = {0: "operational", 1: "impaired", 2: "critical"}[sev] if has_data else "pending"

        with open(file_path, 'w') as f:
            json.dump(new_data, f, indent=2)

if __name__ == "__main__":
    main()
