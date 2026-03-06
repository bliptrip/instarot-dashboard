import { useState, useEffect } from "react";
import DeviceCard from "./components/DeviceCard";
import TemperatureChart from "./components/TemperatureChart";
import PIDChart from "./components/PIDChart";
import useLiveData from "./hooks/useLiveData";

export default function App() {
  const [devices,  setDevices]  = useState([]);
  const [selected, setSelected] = useState(null);
  const [pidDebug, setPidDebug] = useState(false);
  const liveReadings = useLiveData();

  useEffect(() => {
    fetch("/api/devices")
      .then(r => r.json())
      .then(setDevices);
  }, []);

  const handleSelect = (hostname) => {
    if (hostname !== selected) setPidDebug(false);
    setSelected(hostname);
  };

  return (
    <div className="app">
      <h1>Instarot Dashboard</h1>
      <div className="main-layout">
        <div className="device-grid">
          {devices.map(d => (
            <DeviceCard
              key={d.hostname}
              device={d}
              live={liveReadings[d.hostname]}
              onSelect={() => handleSelect(d.hostname)}
              selected={selected === d.hostname}
            />
          ))}
        </div>
        <div className="chart-side">
          {selected && <TemperatureChart device={selected} />}
          {selected && (
            <div style={{ marginTop: "0.75rem" }}>
              <button
                className={pidDebug ? "active" : ""}
                onClick={() => setPidDebug(v => !v)}
              >
                {pidDebug ? "Hide PID Debug" : "Show PID Debug"}
              </button>
            </div>
          )}
          {selected && pidDebug && <PIDChart device={selected} />}
        </div>
      </div>
    </div>
  );
}
