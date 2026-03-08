import { useState, useEffect, useCallback } from "react";

const DEFAULT_STEPS = JSON.stringify([
  { at: 0,   action: "setpoint", value: 75 },
  { at: 300, action: "setpoint", value: 80 },
], null, 2);

function RunRow({ run, onStop }) {
  const elapsed = run.ended_at
    ? run.ended_at - run.started_at
    : Math.floor(Date.now() / 1000) - run.started_at;
  const fmtElapsed = elapsed < 60 ? `${elapsed}s` : elapsed < 3600 ? `${Math.floor(elapsed / 60)}m` : `${(elapsed / 3600).toFixed(1)}h`;

  return (
    <div className={`run-row run-${run.status}`}>
      <span className="run-device">{run.device}</span>
      <span className="run-status">{run.status}</span>
      <span className="run-step">step {run.current_step}</span>
      <span className="run-elapsed">{fmtElapsed}</span>
      {run.status === "running" && (
        <button className="btn-sm btn-danger" onClick={() => onStop(run.id)}>Stop</button>
      )}
    </div>
  );
}

export default function ProgramPanel({ onRunStarted }) {
  const [programs,  setPrograms]  = useState([]);
  const [devices,   setDevices]   = useState([]);
  const [runs,      setRuns]      = useState([]);
  const [editing,   setEditing]   = useState(null); // null | "new" | program object
  const [editName,  setEditName]  = useState("");
  const [editDesc,  setEditDesc]  = useState("");
  const [editSteps, setEditSteps] = useState(DEFAULT_STEPS);
  const [stepsErr,  setStepsErr]  = useState(null);
  const [runDev,    setRunDev]    = useState("");
  const [runSess,   setRunSess]   = useState("");
  const [runTarget, setRunTarget] = useState(null); // program to run
  const [status,    setStatus]    = useState(null);

  const loadPrograms = useCallback(() => {
    fetch("/api/programs").then(r => r.json()).then(setPrograms);
  }, []);

  const loadRuns = useCallback(() => {
    fetch("/api/runs").then(r => r.json()).then(setRuns);
  }, []);

  useEffect(() => {
    loadPrograms();
    loadRuns();
    fetch("/api/devices").then(r => r.json()).then(devs => {
      setDevices(devs);
      if (devs.length > 0) setRunDev(devs[0].hostname);
    });
    const interval = setInterval(loadRuns, 3000);
    return () => clearInterval(interval);
  }, []);

  const openNew = () => {
    setEditing("new");
    setEditName("");
    setEditDesc("");
    setEditSteps(DEFAULT_STEPS);
    setStepsErr(null);
  };

  const openEdit = (p) => {
    setEditing(p);
    setEditName(p.name);
    setEditDesc(p.description || "");
    setEditSteps(JSON.stringify(p.steps, null, 2));
    setStepsErr(null);
  };

  const validateSteps = (text) => {
    try {
      const parsed = JSON.parse(text);
      if (!Array.isArray(parsed)) throw new Error("Steps must be a JSON array");
      for (const s of parsed) {
        if (typeof s.at !== "number") throw new Error("Each step must have a numeric 'at' (seconds)");
        if (!["setpoint", "pid"].includes(s.action)) throw new Error(`Unknown action: ${s.action}`);
        if (s.value === undefined) throw new Error("Each step must have a 'value'");
      }
      setStepsErr(null);
      return parsed;
    } catch (e) {
      setStepsErr(e.message);
      return null;
    }
  };

  const handleSave = () => {
    const steps = validateSteps(editSteps);
    if (!steps || !editName.trim()) return;
    const isNew = editing === "new";
    const url   = isNew ? "/api/programs" : `/api/programs/${editing.id}`;
    const method = isNew ? "POST" : "PUT";
    fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editName.trim(), description: editDesc, steps }),
    })
      .then(r => r.json())
      .then(() => { setEditing(null); loadPrograms(); });
  };

  const handleDelete = (pid) => {
    fetch(`/api/programs/${pid}`, { method: "DELETE" }).then(() => loadPrograms());
  };

  const handleRun = () => {
    if (!runTarget || !runDev) return;
    fetch(`/api/programs/${runTarget.id}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device: runDev, session_name: runSess.trim() || undefined }),
    })
      .then(r => r.json())
      .then(run => {
        setRunTarget(null);
        setRunSess("");
        setStatus("started");
        loadRuns();
        if (run.session && onRunStarted) onRunStarted(run.session);
        setTimeout(() => setStatus(null), 2000);
      });
  };

  const handleStop = (runId) => {
    fetch(`/api/runs/${runId}/stop`, { method: "POST" }).then(() => loadRuns());
  };

  const recentRuns = runs.slice(0, 20);

  if (editing !== null) {
    return (
      <div className="panel">
        <div className="panel-section">
          <div className="panel-row" style={{ justifyContent: "space-between" }}>
            <h3>{editing === "new" ? "New Program" : `Edit: ${editing.name}`}</h3>
            <button className="btn-sm" onClick={() => setEditing(null)}>Cancel</button>
          </div>
          <div className="panel-col">
            <label>Name</label>
            <input type="text" value={editName} onChange={e => setEditName(e.target.value)} placeholder="Program name" />
            <label>Description</label>
            <input type="text" value={editDesc} onChange={e => setEditDesc(e.target.value)} placeholder="Optional description" />
            <label>Steps (JSON)</label>
            <textarea
              className="steps-editor"
              value={editSteps}
              onChange={e => { setEditSteps(e.target.value); validateSteps(e.target.value); }}
              rows={12}
              spellCheck={false}
            />
            {stepsErr && <span className="status error">{stepsErr}</span>}
            <div className="steps-hint">
              Each step: <code>{`{"at": <seconds>, "action": "setpoint"|"pid", "value": <number|object>}`}</code>
            </div>
            <button onClick={handleSave} disabled={!!stepsErr || !editName.trim()}>Save</button>
          </div>
        </div>
      </div>
    );
  }

  if (runTarget) {
    return (
      <div className="panel">
        <div className="panel-section">
          <div className="panel-row" style={{ justifyContent: "space-between" }}>
            <h3>Run: {runTarget.name}</h3>
            <button className="btn-sm" onClick={() => setRunTarget(null)}>Cancel</button>
          </div>
          <div className="panel-col">
            <label>Device</label>
            <select value={runDev} onChange={e => setRunDev(e.target.value)}>
              {devices.map(d => <option key={d.hostname} value={d.hostname}>{d.hostname}</option>)}
            </select>
            <label>Session name (optional — creates a session to record this run)</label>
            <input
              type="text"
              value={runSess}
              onChange={e => setRunSess(e.target.value)}
              placeholder="e.g. Ramp test 2026-03-07"
            />
            <button onClick={handleRun} disabled={!runDev}>Run Program</button>
            {status && <span className="status sent">{status}</span>}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-section">
        <div className="panel-row" style={{ justifyContent: "space-between", marginBottom: "0.75rem" }}>
          <h3>Programs</h3>
          <button onClick={openNew}>+ New Program</button>
        </div>
        {programs.length === 0 && <p className="muted-text">No programs yet.</p>}
        {programs.map(p => (
          <div key={p.id} className="program-row">
            <div className="program-info">
              <span className="program-name">{p.name}</span>
              {p.description && <span className="program-desc">{p.description}</span>}
              <span className="program-steps">{p.steps.length} step{p.steps.length !== 1 ? "s" : ""}</span>
            </div>
            <div className="session-actions">
              <button className="btn-sm" onClick={() => setRunTarget(p)}>Run</button>
              <button className="btn-sm" onClick={() => openEdit(p)}>Edit</button>
              <button className="btn-sm btn-danger" onClick={() => handleDelete(p.id)}>Del</button>
            </div>
          </div>
        ))}
      </div>

      <div className="panel-section">
        <h3>Recent Runs</h3>
        {recentRuns.length === 0 && <p className="muted-text">No runs yet.</p>}
        {recentRuns.map(r => (
          <RunRow key={r.id} run={r} onStop={handleStop} />
        ))}
      </div>
    </div>
  );
}
