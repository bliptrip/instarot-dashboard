import { useState, useEffect } from "react";
import DeviceCard from "./components/DeviceCard";
import TemperatureChart from "./components/TemperatureChart";
import PIDChart from "./components/PIDChart";
import SessionPanel from "./components/SessionPanel";
import ProgramPanel from "./components/ProgramPanel";
import useLiveData from "./hooks/useLiveData";

const TABS = ["Live", "Sessions", "Programs"];

export default function App() {
  const [devices,    setDevices]    = useState([]);
  const [selected,   setSelected]   = useState(null);
  const [pidDebug,   setPidDebug]   = useState(false);
  const [tab,        setTab]        = useState("Live");
  const [viewSession, setViewSession] = useState(null); // session object to view in chart
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

  const handleViewSession = (session) => {
    setViewSession(session);
    setSelected(session.device);
    setTab("Live");
  };

  const handleRunStarted = (session) => {
    setViewSession(session);
    setSelected(session.device);
    setTab("Live");
  };

  const handleClearSession = () => setViewSession(null);

  return (
    <div className="app">
      <div className="app-header">
        <h1>Instarot Dashboard</h1>
        <div className="tab-bar">
          {TABS.map(t => (
            <button
              key={t}
              className={`tab-btn ${tab === t ? "active" : ""}`}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {tab === "Live" && (
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
            {viewSession && (
              <div className="session-banner">
                Viewing session: <strong>{viewSession.name}</strong>
                <button className="btn-sm" style={{ marginLeft: "0.75rem" }} onClick={handleClearSession}>
                  Back to live
                </button>
              </div>
            )}
            {selected && (
              <TemperatureChart
                device={selected}
                session={viewSession && viewSession.device === selected ? viewSession : null}
              />
            )}
            {selected && !viewSession && (
              <div style={{ marginTop: "0.75rem" }}>
                <button
                  className={pidDebug ? "active" : ""}
                  onClick={() => setPidDebug(v => !v)}
                >
                  {pidDebug ? "Hide PID Debug" : "Show PID Debug"}
                </button>
              </div>
            )}
            {selected && !viewSession && pidDebug && <PIDChart device={selected} />}
          </div>
        </div>
      )}

      {tab === "Sessions" && (
        <SessionPanel onViewSession={handleViewSession} />
      )}

      {tab === "Programs" && (
        <ProgramPanel onRunStarted={handleRunStarted} />
      )}
    </div>
  );
}
