const REPO = "clb-sol-dev/statuspage";
const fmt = (d) => d ? new Date(d).toLocaleString('de-DE', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'}) : '---';

function toggleView(v) {
    document.getElementById('view-status').style.display = v === 'status' ? 'block' : 'none';
    document.getElementById('view-maint').style.display = v === 'maint' ? 'block' : 'none';
    document.getElementById('view-changelog').style.display = v === 'changelog' ? 'block' : 'none';
    
    document.getElementById('nav-status').className = v === 'status' ? 'active' : '';
    document.getElementById('nav-maint').className = v === 'maint' ? 'active' : '';
    document.getElementById('nav-changelog').className = v === 'changelog' ? 'active' : '';
    
    if(v === 'maint') loadMaintenance();
    if(v === 'changelog') loadChangelog();
}

async function loadChangelog() {
    const container = document.getElementById('changelog-content');
    try {
        const res = await fetch(`status/changelog.json?t=${Date.now()}`);
        if (!res.ok) throw new Error("Changelog nicht gefunden");
        let data = await res.json();
        
        // Safety First: Sortierung nach Datum absteigend (Neueste zuerst)
        data.sort((a, b) => new Date(b.date) - new Date(a.date));
        
        let html = '<div class="change-section"><h3>Letzte Änderungen</h3>';
        data.forEach(entry => {
            const versionHtml = entry.version ? `<span class="version-tag">${entry.version}</span>` : '';
            const changeIdHtml = entry.change_id ? `<span class="change-id">${entry.change_id}:</span>` : '';
            
            html += `
                <div class="card change-card">
                    <div class="header-card" onclick="this.parentElement.classList.toggle('open')">
                        <div>
                            <strong>${changeIdHtml}${entry.title}</strong>
                            <small style="display:block; color:var(--muted); margin-top:2px;">${fmt(entry.date)}</small>
                        </div>
                        ${versionHtml}
                    </div>
                    <div class="details">
                        <div style="padding: 15px;">
                            <ul style="margin:0; padding-left:18px;">
                                ${entry.changes.map(c => `<li>${c}</li>`).join('')}
                            </ul>
                        </div>
                    </div>
                </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<p>Keine Changelog-Daten verfügbar.</p>';
    }
}

async function loadMaintenance() {
    const container = document.getElementById('maint-content');
    try {
        const res = await fetch(`status/maintenance.json?t=${Date.now()}`);
        if (!res.ok) throw new Error("Datei nicht gefunden");
        const data = await res.json();
        const now = new Date();
        
        // Sortierung für Maintenance: Geplante/Aktive nach Startdatum (baldigste zuerst)
        const active = (data.active || []).sort((a, b) => new Date(a.start) - new Date(b.start));
        // Historie: Neueste beendete zuerst
        const past = (data.past || []).sort((a, b) => new Date(b.end) - new Date(a.end));

        const renderMaint = (m, isPast = false) => `
            <div class="card ${isPast ? 'past-maint' : ''}" style="border-left: 4px solid ${isPast ? 'var(--border)' : 'var(--primary)'}">
                <div class="header-card" onclick="this.parentElement.classList.toggle('open')">
                    <div>
                        <strong>${m.host}: ${m.service}</strong>
                        <small style="display:block; color:var(--muted); margin-top:2px;">
                            ${isPast ? 'Beendet: ' + fmt(m.end) : 'Start: ' + fmt(m.start)}
                        </small>
                    </div>
                    ${!isPast && new Date(m.start) <= now ? '<span class="pill maintenance">Aktiv</span>' : ''}
                </div>
                <div class="details">
                    <div style="padding:15px; font-size:13px;">
                        <strong>Grund:</strong> ${m.reason || 'Keine Angabe'}<br>
                        <small style="color:var(--muted); display:block; margin-top:5px;">Zeitraum: ${fmt(m.start)} bis ${fmt(m.end)}</small>
                    </div>
                </div>
            </div>`;

        let html = '<div class="maint-section"><h3>Aktive & Geplante Wartungen</h3>';
        if (active.length === 0) html += '<p><small>Keine laufenden Wartungen.</small></p>';
        active.forEach(m => html += renderMaint(m));
        
        html += '</div><div class="maint-section"><h3>Historie</h3>';
        if (past.length === 0) html += '<p><small>Keine Historie vorhanden.</small></p>';
        past.forEach(m => html += renderMaint(m, true));
        
        container.innerHTML = html + '</div>';
    } catch (e) {
        container.innerHTML = '<p>Keine Wartungsdaten verfügbar.</p>';
    }
}

// Rendert eine einzelne Status-Karte (Host oder aggregierte Gruppe) und trackt das neueste Update.
async function renderCard(t, latestRef) {
    try {
        const res = await fetch(`status/${t.id}.json?t=${Date.now()}`);
        if (!res.ok) return '';
        const data = await res.json();
        const agg = {};
        Object.values(data.entries).forEach(e => {
            if (e.last_update && new Date(e.last_update) > latestRef.value) latestRef.value = new Date(e.last_update);
            if (e.service === 'Host') return;
            if (!agg[e.service]) agg[e.service] = [];
            agg[e.service].push(e.status.toLowerCase());
        });
        let hStatus = data.overall_status.toLowerCase();
        let html = `<div class="card"><div class="header-card" onclick="this.parentElement.classList.toggle('open')">
            <strong>${data.display_name}</strong>
            <span class="pill ${hStatus}">${hStatus === 'pending' ? 'No Data' : hStatus}</span>
        </div><div class="details">`;
        Object.keys(agg).sort().forEach(s => {
            let statuses = agg[s]; let sStat = 'operational';
            if (statuses.includes('critical') || statuses.includes('down')) sStat = 'critical';
            else if (statuses.includes('warning') || statuses.includes('impaired')) sStat = 'impaired';
            else if (statuses.includes('maintenance')) sStat = 'maintenance';
            else if (statuses.includes('updating')) sStat = 'updating';
            else if (statuses.includes('pending')) sStat = 'pending';
            html += `<div class="svc-row"><span>${s}</span><span class="pill ${sStat}">${sStat === 'pending' ? 'No Data' : sStat}</span></div>`;
        });
        html += `</div></div>`;
        return html;
    } catch (e) {
        return '';
    }
}

async function update() {
    try {
        const cfg = await (await fetch(`https://raw.githubusercontent.com/${REPO}/main/config.json?t=${Date.now()}`)).json();
        const dash = document.getElementById('dashboard');
        dash.style.setProperty('--cols', cfg.ui_config.columns || 2);

        // 1. Targets (einzelne Hosts oder aggregierte Gruppen wie "proxmox"/"docker") auflösen.
        //    display_group kommt direkt vom Host; bei aggregierten Gruppen wird sie von den
        //    zugehörigen Hosts übernommen (erster Host mit gesetzter display_group gewinnt).
        let targets = (cfg.display_order || []).flatMap(o => {
            if (o === 'standalone') {
                return cfg.hosts
                    .filter(h => h.group === 'standalone')
                    .sort((a, b) => a.display_name.localeCompare(b.display_name))
                    .map(h => ({ id: h.id, display_group: h.display_group || null }));
            }
            const member = cfg.hosts.find(h => h.group === o && h.display_group);
            return [{ id: o, display_group: member ? member.display_group : null }];
        });

        // 2. Reihenfolge & Klartext-Namen der Display Groups kommen komplett aus config.json.
        //    Nichts davon ist hier hardcoded - neue Gruppen erscheinen automatisch.
        const displayGroupDefs = cfg.display_groups || [];
        const groupOrder = displayGroupDefs.map(g => g.id);
        const groupName = id => (displayGroupDefs.find(g => g.id === id) || {}).name || id;
        const UNASSIGNED = '__unassigned__';

        // 3. Targets nach display_group bündeln.
        const buckets = new Map();
        targets.forEach(t => {
            const key = t.display_group || UNASSIGNED;
            if (!buckets.has(key)) buckets.set(key, []);
            buckets.get(key).push(t);
        });

        // Bekannte Gruppen zuerst (in konfigurierter Reihenfolge), dann noch unbekannte
        // (in config.json neu vergebene, aber noch nicht in display_groups gepflegte) IDs,
        // "Ohne Gruppe" immer zuletzt.
        const orderedKeys = [
            ...groupOrder.filter(id => buckets.has(id)),
            ...[...buckets.keys()].filter(k => k !== UNASSIGNED && !groupOrder.includes(k)),
            ...(buckets.has(UNASSIGNED) ? [UNASSIGNED] : [])
        ];

        let html = '';
        const latestRef = { value: new Date(0) };

        for (const key of orderedKeys) {
            const label = key === UNASSIGNED ? 'Ohne Gruppe' : groupName(key);
            let sectionHtml = '';
            for (const t of buckets.get(key)) {
                sectionHtml += await renderCard(t, latestRef);
            }
            if (!sectionHtml) continue; // leere Sektionen (z.B. alle Fetches fehlgeschlagen) nicht anzeigen
            html += `<div class="group-section"><div class="section-eyebrow">${label}</div><div class="grid">${sectionHtml}</div></div>`;
        }

        dash.innerHTML = html;
        document.getElementById('last-update').innerText = "Letzte Aktualisierung: " + (latestRef.value.getTime() > 0 ? fmt(latestRef.value) : "---");
    } catch (e) {}
}

update();
setInterval(update, 60000);
