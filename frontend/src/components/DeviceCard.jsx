import { useState, useEffect } from "react";

export default function DeviceCard({ device, live, onSelect, selected }) {
  const online = live && (Date.now() / 1000 - live.ts) < 30;

  const [setpoint, setSetpoint] = useState("");
  const [kp, setKp] = useState("");
  const [ki, setKi] = useState("");
  const [kd, setKd] = useState("");
  const [status, setStatus] = useState(null);

  // Populate fields once the first live reading arrives
  useEffect(() => {
    if (live?.setpoint !== undefined && setpoint === "") setSetpoint(String(live.setpoint));
  }, [live?.setpoint]);
  useEffect(() => {
    if (live?.kp !== undefined && kp === "") setKp(String(live.kp));
  }, [live?.kp]);
  useEffect(() => {
    if (live?.ki !== undefined && ki === "") setKi(String(live.ki));
  }, [live?.ki]);
  useEffect(() => {
    if (live?.kd !== undefined && kd === "") setKd(String(live.kd));
  }, [live?.kd]);

  const handleSet = () => {
    const calls = [];

    const spVal = parseFloat(setpoint);
    if (!isNaN(spVal) && spVal !== live?.setpoint) {
      calls.push(fetch(`/api/cmd/${device.hostname}/setpoint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: spVal }),
      }));
    }

    const kpVal = parseFloat(kp), kiVal = parseFloat(ki), kdVal = parseFloat(kd);
    if (
      (!isNaN(kpVal) && kpVal !== live?.kp) ||
      (!isNaN(kiVal) && kiVal !== live?.ki) ||
      (!isNaN(kdVal) && kdVal !== live?.kd)
    ) {
      const pid = {};
      if (!isNaN(kpVal)) pid.kp = kpVal;
      if (!isNaN(kiVal)) pid.ki = kiVal;
      if (!isNaN(kdVal)) pid.kd = kdVal;
      calls.push(fetch(`/api/cmd/${device.hostname}/pid`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pid),
      }));
    }

    if (calls.length === 0) return;
    Promise.all(calls)
      .then(() => setStatus("sent"))
      .catch(() => setStatus("error"))
      .finally(() => setTimeout(() => setStatus(null), 2000));
  };

  return (
    <div
      className={`card ${selected ? "selected" : ""} ${online ? "online" : "offline"}`}
      onClick={onSelect}
    >
      <div className="card-header">
        <h2>{device.hostname}</h2>
        <span className="status-dot" title={online ? "Online" : "Offline"} />
      </div>
      <div className="temp">{live?.tc1_temp?.toFixed(1) ?? "—"}C</div>
      <div className="tc2">TC2: {live?.tc2_temp?.toFixed(1) ?? "—"}C</div>
      <div className="meta">
        <span>SP: {live?.setpoint?.toFixed(1) ?? "—"}C</span>
        <span>OUT: {live?.output?.toFixed(0) ?? "—"}%</span>
      </div>
      <div onClick={e => e.stopPropagation()}>
        <div className="setpoint-control">
          <input
            type="number"
            value={setpoint}
            onChange={e => setSetpoint(e.target.value)}
            placeholder="Setpoint °C"
          />
        </div>
        <div className="pid-control">
          <div className="pid-row">
            <label>Kp</label>
            <input type="number" value={kp} onChange={e => setKp(e.target.value)} placeholder="Kp" />
          </div>
          <div className="pid-row">
            <label>Ki</label>
            <input type="number" value={ki} onChange={e => setKi(e.target.value)} placeholder="Ki" />
          </div>
          <div className="pid-row">
            <label>Kd</label>
            <input type="number" value={kd} onChange={e => setKd(e.target.value)} placeholder="Kd" />
          </div>
          <div className="pid-row">
            <button onClick={handleSet}>Set</button>
            {status && <span className={`status ${status}`}>{status}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
