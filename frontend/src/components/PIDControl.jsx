import { useState, useEffect } from "react";

export default function PIDControl({ device, current_kp, current_kd, current_ki }) {
  const [kp,  setkp]  = useState(current_kp ?? "");
  const [kd,  setkd]  = useState(current_kd ?? "");
  const [ki,  setki]  = useState(current_ki ?? "");

  useEffect(() => {
    if (current_kp !== undefined && kp === "") setkp(String(current_kp));
  }, [current_kp]);
  useEffect(() => {
    if (current_ki !== undefined && ki === "") setki(String(current_ki));
  }, [current_ki]);
  useEffect(() => {
    if (current_kd !== undefined && kd === "") setkd(String(current_kd));
  }, [current_kd]);
  const [status, setStatus] = useState(null);

  const send = () => {
    fetch(`/api/cmd/${device}/pid`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kp: parseFloat(kp),
                             kd: parseFloat(kd),
                             ki: parseFloat(ki)}),
    })
      .then(r => r.json())
      .then(() => setStatus("sent"))
      .catch(() => setStatus("error"))
      .finally(() => setTimeout(() => setStatus(null), 2000));
  };

  return (
    <div className="pid-control">
      <div className="pid-row">
        <label>Kp</label>
        <input type="number" value={kp} onChange={e => setkp(e.target.value)} placeholder="Kp" />
      </div>
      <div className="pid-row">
        <label>Ki</label>
        <input type="number" value={ki} onChange={e => setki(e.target.value)} placeholder="Ki" />
      </div>
      <div className="pid-row">
        <label>Kd</label>
        <input type="number" value={kd} onChange={e => setkd(e.target.value)} placeholder="Kd" />
      </div>
      <div className="pid-row">
        <button onClick={send}>Set PID</button>
        {status && <span className={`status ${status}`}>{status}</span>}
      </div>
    </div>
  );
}
