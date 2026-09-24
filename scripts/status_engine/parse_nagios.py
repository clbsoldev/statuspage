import os
import json
from core import process_event

def parse_nagios():
    payload_raw = os.getenv('PAYLOAD')
    if not payload_raw:
        print("Error: No PAYLOAD environment variable set.")
        return
    
    try:
        data = json.loads(payload_raw)
    except Exception as e:
        print(f"Error parsing Nagios payload JSON: {e}")
        return

    unified_payload = {
        "host": data.get('host'),
        "service": data.get('service'),
        "status": str(data.get('status', '')).upper(),
        "output": data.get('output', ''),
        "type": str(data.get('type', 'NOTIFICATION')).upper(),
        "comment": data.get('comment', '')
    }

    process_event(unified_payload)

if __name__ == "__main__":
    parse_nagios()
