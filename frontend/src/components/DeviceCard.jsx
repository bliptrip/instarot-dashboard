import SetpointControl from "./SetpointControl";
import PIDControl from "./PIDControl";

export default function DeviceCard({ device, live, onSelect, selected }) {
  const online = live && (Date.now() / 1000 - live.ts) < 30;

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
      <SetpointControl device={device.hostname} current={live?.setpoint} />
      <PIDControl device={device.hostname} current_kp={live?.kp} current_ki={live?.ki} current_kd={live?.kd}/>
    </div>
  );
}
