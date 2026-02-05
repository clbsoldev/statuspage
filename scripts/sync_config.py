import os
import json

def main():
    config_file = 'main/config.json'
    status_dir = 'gh-pages/status'
    
    if not os.path.exists(config_file): return
    with open(config_file, 'r') as f:
        config = json.load(f)

    if not os.path.exists(status_dir): return

    # Wir gehen alle Dateien im Status-Ordner durch
    for filename in os.listdir(status_dir):
        if not filename.endswith('.json'): continue
        
        file_path = os.path.join(status_dir, filename)
        target_id = filename.replace('.json', '')
        
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Namen finden (entweder via Host-ID oder Gruppen-ID)
        # 1. Prüfen, ob es eine Gruppe ist
        group = next((g for g in config.get('groups', []) if g['id'] == target_id), None)
        if group:
            data["display_name"] = group['name']
            data["is_group"] = True
        else:
            # 2. Prüfen, ob es ein Standalone Host ist
            host = next((h for h in config.get('hosts', []) if h['id'] == target_id), None)
            if host:
                data["display_name"] = host['display_name']
                data["is_group"] = False

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Updated metadata for {filename}")

if __name__ == "__main__":
    main()
