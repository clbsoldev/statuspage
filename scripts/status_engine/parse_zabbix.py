import os
import json
from core import process_event

def parse_zabbix():
    payload_raw = os.getenv('PAYLOAD')
    if not payload_raw:
        print("Error: No PAYLOAD environment variable set.")
        return
    
    try:
        data = json.loads(payload_raw)
    except Exception as e:
        print(f"Error parsing Zabbix payload JSON: {e}")
        return
    
    raw_status = str(data.get('status', '')).upper()
    severity_raw = str(data.get('severity', '')).upper()
    is_suppressed = str(data.get('suppressed', '0')) in ['1', 'TRUE', 'YES']
    
    event_type = str(data.get('type', 'NOTIFICATION')).upper()

    # Maintenance-Erkennung via Zabbix Suppressed-State oder expliziten Event-Typ
    if is_suppressed and raw_status in ['1', 'PROBLEM']:
        event_type = 'DOWNTIMESTART'
    elif not is_suppressed and event_type == 'DOWNTIMESTART' and raw_status in ['0', 'OK', 'RESOLVED']:
        event_type = 'DOWNTIMEEND'

    # Mapping der Zabbix Severities
    if raw_status in ['1', 'PROBLEM']:
        if severity_raw in ['HIGH', 'DISASTER', 'CRITICAL']:
            status = 'CRITICAL'
        elif severity_raw in ['AVERAGE', 'WARNING']:
            status = 'WARNING'
        else:
            status = 'WARNING'
    elif raw_status in ['0', 'OK', 'RESOLVED']:
        status = 'OK'
    else:
        status = raw_status

    unified_payload = {
        "host": data.get('host'),
        "service": data.get('service'),
        "status": status,
        "output": data.get('output', ''),
        "type": event_type,
        "comment": data.get('comment', 'Zabbix Event')
    }

    process_event(unified_payload)

if __name__ == "__main__":
    parse_zabbix()
