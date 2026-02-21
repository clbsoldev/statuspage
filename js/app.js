const REPO = "clb-sol-dev/statuspage";
const fmt = (d) => d ? new Date(d).toLocaleString('de-DE', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'}) : '---';

function toggleView(v) {
    document.getElementById('view-status').style.display = v === 'status' ? 'block' : 'none';
    document.getElementById('view-maint').style.display = v === 'maint' ? 'block' : 'none';
    document.getElementById('nav-status').className = v === 'status' ? 'active' : '';
    document.getElementById('nav-maint').className = v === 'maint' ? 'active' : '';
    if(v === 'maint') loadMaintenance();
}

async function loadMaintenance() {
    const container = document.getElementById('maint-content');
    try {
        const res = await fetch(`status/maintenance.json?t=${Date.now()}`);
        if (!res.ok) throw new Error("Datei nicht gefunden");
        const data = await res.json();
        const now = new Date();
        let html = '';
        html += '<div class="maint-section"><h3>Aktive Wartungen</h3>';
        const active = data.active.filter(m => new Date(m.start) <= now);
        if (active.length === 0) html += '<p><small>Keine laufenden Wartungen.</small></p>';
        active.forEach(m => {
            html += `<div class="maint-card"><strong>${m.host}: ${m.service}</strong><small>Seit: ${fmt(m.start)}<br>Grund: ${m.reason || 'Keine Angabe'}</small></div>`;
        });
        html += '</div>';
        html += '<div class="maint-section"><h3>Geplante Wartungen</h3>';
        const planned = data.active.filter(m => new Date(m.start) > now);
        if (planned.length === 0) html += '<p><small>Keine geplanten Wartungen.</small></p>';
        planned.forEach(m => {
            html += `<div class="maint-card" style="border-left-color: #0969da77"><strong>${m.host}: ${m.service}</strong><small>Geplant für: ${fmt(m.start)}<br>Grund: ${m.reason || 'Geplante Arbeiten'}</small></div>`;
        });
        html += '</div>';
        html += '<div class="maint-section"><h3>Vergangene Wartungen</h3>';
        if (!data.past || data.past.length === 0) html += '<p><small>Keine Historie vorhanden.</small></p>';
        else data.past.forEach(m => {
            html += `<div class="maint-card past"><strong>${m.host}: ${m.service}</strong><small>Zeitraum: ${fmt(m.start)} bis ${fmt(m.end)}</small></div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<p>Keine Wartungsdaten verfügbar (maintenance.json fehlt oder ist leer).</p>';
    }
}

async function update() {
    try {
        const cfg = await (await fetch(`https://raw.githubusercontent.com/${REPO}/main/config.json?t=${Date.now()}`)).json();
        const dash = document.getElementById('dashboard');
        dash.style.setProperty('--cols', cfg.ui_config.columns || 2);
        let targets = (cfg.display_order || []).flatMap(o => {
            if (o === 'standalone') return cfg.hosts.filter(h => h.group === 'standalone').sort((a,b) => a.display_name.localeCompare(b.display_name)).map(h => ({id: h.id}));
            return {id: o};
        });
        let html = ''; let latest = new Date(0);
        for (const t of targets) {
            try {
                const res = await fetch(`status/${t.id}.json?t=${Date.now()}`);
                if(!res.ok) continue;
                const data = await res.json();
                const agg = {};
                Object.values(data.entries).forEach(e => {
                    if(e.last_update && new Date(e.last_update) > latest) latest = new Date(e.last_update);
                    if(e.service === 'Host') return;
                    if(!agg[e.service]) agg[e.service] = [];
                    agg[e.service].push(e.status.toLowerCase());
                });
                let hStatus = data.overall_status.toLowerCase();
                html += `<div class="card"><div class="header-card" onclick="this.parentElement.classList.toggle('open')">
                    <strong>${data.display_name}</strong>
                    <span class="pill ${hStatus}">${hStatus === 'pending' ? 'No Data' : hStatus}</span>
                </div><div class="details">`;
                Object.keys(agg).sort().forEach(s => {
                    let statuses = agg[s]; let sStat = 'operational';
                    if(statuses.includes('critical') || statuses.includes('down')) sStat = 'critical';
                    else if(statuses.includes('warning') || statuses.includes('impaired')) sStat = 'impaired';
                    else if(statuses.includes('maintenance')) sStat = 'maintenance';
                    else if(statuses.includes('updating')) sStat = 'updating';
                    else if(statuses.includes('pending')) sStat = 'pending';
                    html += `<div class="svc-row"><span>${s}</span><span class="pill ${sStat}">${sStat === 'pending' ? 'No Data' : sStat}</span></div>`;
                });
                html += `</div></div>`;
            } catch(e) {}
        }
        dash.innerHTML = html;
        document.getElementById('last-update').innerText = "Letzte Aktualisierung: " + (latest.getTime() > 0 ? fmt(latest) : "---");
    } catch(e) {}
}

// Initialer Aufruf und Intervall
update();
setInterval(update, 60000);
