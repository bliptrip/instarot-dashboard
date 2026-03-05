import { useState } from "react";

export default function PIDControl({ device, current_kp, current_kd, current_ki }) {
  const [kp,  setkp]  = useState(current_kp ?? "");
  const [kd,  setkd]  = useState(current_kd ?? "");
  const [ki,  setki]  = useState(current_ki ?? "");
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
    <div className="setpoint-control">
      <input
        type="number"
        value={kp}
        onChange={e => setkp(e.target.value)}
        placeholder="Kp"
      />
      <input
        type="number"
        value={kd}
        onChange={e => setkd(e.target.value)}
        placeholder="Kd"
      />
      <input
        type="number"
        value={ki}
        onChange={e => setki(e.target.value)}
        placeholder="Ki"
      />
      <button onClick={send}>Set PID Parameters</button>
      {status && <span className={`status ${status}`}>{status}</span>}
    </div>
  );
}
