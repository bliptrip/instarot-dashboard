import { useState, useEffect, useCallback } from "react";

export default function SessionPanel({ onViewSession }) {
  const [sessions, setSessions] = useState([]);
  const [devices,  setDevices]  = useState([]);
  const [newName,  setNewName]  = useState("");
  const [newDev,   setNewDev]   = useState("");
  const [status,   setStatus]   = useState(null);

  const load = useCallback(() => {
    fetch("/api/sessions").then(r => r.json()).then(setSessions);
  }, []);

  useEffect(() => {
    load();
    fetch("/api/devices").then(r => r.json()).then(devs => {
      setDevices(devs);
      if (devs.length > 0 && !newDev) setNewDev(devs[0].hostname);
    });
  }, []);

  const handleCreate = () => {
    if (!newName.trim() || !newDev) return;
    fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName.trim(), device: newDev }),
    })
      .then(r => r.json())
      .then(s => {
        setNewName("");
        setStatus("created");
        load();
        setTimeout(() => setStatus(null), 2000);
      });
  };

  const handleEnd = (sid) => {
    fetch(`/api/sessions/${sid}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ end_now: true }),
    }).then(() => load());
  };

  const handleDelete = (sid) => {
    fetch(`/api/sessions/${sid}`, { method: "DELETE" }).then(() => load());
  };

  const fmtTime = (ts) => ts ? new Date(ts * 1000).toLocaleString() : "—";
  const duration = (s) => {
    const end = s.ended_at || Math.floor(Date.now() / 1000);
    const secs = end - s.started_at;
    if (secs < 60) return `${secs}s`;
    if (secs < 3600) return `${Math.floor(secs / 60)}m`;
    return `${(secs / 3600).toFixed(1)}h`;
  };

  return (
    <div className="panel">
      <div className="panel-section">
        <h3>New Session</h3>
        <div className="panel-row">
          <input
            type="text"
            placeholder="Session name"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleCreate()}
          />
          <select value={newDev} onChange={e => setNewDev(e.target.value)}>
            {devices.map(d => <option key={d.hostname} value={d.hostname}>{d.hostname}</option>)}
          </select>
          <button onClick={handleCreate}>Start</button>
          {status && <span className="status sent">{status}</span>}
        </div>
      </div>

      <div className="panel-section">
        <h3>Sessions</h3>
        {sessions.length === 0 && <p className="muted-text">No sessions yet.</p>}
        <div className="session-list">
          {sessions.map(s => (
            <div key={s.id} className={`session-row ${s.ended_at ? "ended" : "active"}`}>
              <div className="session-info">
                <span className="session-name">{s.name}</span>
                <span className="session-meta">{s.device} &middot; {fmtTime(s.started_at)} &middot; {duration(s)}</span>
                {!s.ended_at && <span className="session-badge">live</span>}
              </div>
              <div className="session-actions">
                <button className="btn-sm" onClick={() => onViewSession(s)}>View</button>
                {!s.ended_at && (
                  <button className="btn-sm" onClick={() => handleEnd(s.id)}>End</button>
                )}
                <button className="btn-sm btn-danger" onClick={() => handleDelete(s.id)}>Del</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
