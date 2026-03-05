import { useState } from "react";

export default function SetpointControl({ device, current }) {
  const [value,  setValue]  = useState(current ?? "");
  const [status, setStatus] = useState(null);

  const send = () => {
    fetch(`/api/cmd/${device}/setpoint`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: parseFloat(value) }),
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
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="Setpoint C"
      />
      <button onClick={send}>Set</button>
      {status && <span className={`status ${status}`}>{status}</span>}
    </div>
  );
}
