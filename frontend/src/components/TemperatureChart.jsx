import { useState, useEffect, useRef } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, Brush,
} from "recharts";
import useLiveData from "../hooks/useLiveData";

const RANGES = [
  { label: "1h",  seconds: 3600,    resolution: "raw"   },
  { label: "24h", seconds: 86400,   resolution: "1min"  },
  { label: "7d",  seconds: 604800,  resolution: "10min" },
  { label: "30d", seconds: 2592000, resolution: "1hr"   },
];

export default function TemperatureChart({ device, session }) {
  const [data,   setData]   = useState([]);
  const [range,  setRange]  = useState(RANGES[0]);
  const [brush,  setBrush]  = useState({ startIndex: 0, endIndex: 0 });
  const [paused, setPaused] = useState(false);
  const [hidden, setHidden] = useState({});

  const toggleLine = ({ dataKey }) =>
    setHidden(prev => ({ ...prev, [dataKey]: !prev[dataKey] }));
  const liveReadings = useLiveData();
  const prevLiveRef  = useRef(null);

  useEffect(() => {
    let url;
    if (session) {
      url = `/api/history/${device}?session_id=${session.id}`;
    } else {
      const end   = Math.floor(Date.now() / 1000);
      const start = end - range.seconds;
      url = `/api/history/${device}?start=${start}&end=${end}&resolution=${range.resolution}`;
    }
    fetch(url)
      .then(r => r.json())
      .then(rows => {
        const fmt = session ? (ts) => new Date(ts * 1000).toLocaleString() : (ts) => new Date(ts * 1000).toLocaleTimeString();
        const mapped = rows.map(r => ({ ...r, time: fmt(r.ts) }));
        setData(mapped);
        setBrush({ startIndex: 0, endIndex: mapped.length - 1 });
        setPaused(false);
        prevLiveRef.current = null;
      });
  }, [device, range, session]);

  // Append live readings only when not paused and not viewing a completed session
  useEffect(() => {
    if (session?.ended_at) return;
    if (range.resolution !== "raw") return;
    if (paused) return;
    const live = liveReadings[device];
    if (!live || live === prevLiveRef.current) return;
    prevLiveRef.current = live;
    const point = { ...live, time: new Date(live.ts * 1000).toLocaleTimeString() };
    setData(prev => {
      const cutoff = Math.floor(Date.now() / 1000) - range.seconds;
      const next = [...prev.filter(p => p.ts >= cutoff), point];
      setBrush({ startIndex: 0, endIndex: next.length - 1 });
      return next;
    });
  }, [liveReadings, device, range, paused, session]);

  const handleBrush = ({ startIndex, endIndex }) => {
    setPaused(true);
    setBrush({ startIndex, endIndex });
  };

  const handleResume = () => {
    prevLiveRef.current = null;
    setBrush({ startIndex: 0, endIndex: data.length - 1 });
    setPaused(false);
  };

  const isLiveMode = !session && range.resolution === "raw";

  return (
    <div className="chart-panel">
      {session ? (
        <div className="session-chart-header">
          <span className="session-chart-label">Session: <strong>{session.name}</strong></span>
          <span className="session-chart-device">{session.device}</span>
          <span className="session-chart-time">
            {new Date(session.started_at * 1000).toLocaleString()}
            {" — "}
            {session.ended_at ? new Date(session.ended_at * 1000).toLocaleString() : "ongoing"}
          </span>
        </div>
      ) : (
        <div className="range-selector">
          {RANGES.map(r => (
            <button
              key={r.label}
              className={range.label === r.label ? "active" : ""}
              onClick={() => setRange(r)}
            >
              {r.label}
            </button>
          ))}
          {isLiveMode && (
            <button
              className={`live-toggle ${paused ? "paused" : "live"}`}
              onClick={paused ? handleResume : () => setPaused(true)}
            >
              {paused ? "▶ Resume" : "⏸ Pause"}
            </button>
          )}
        </div>
      )}
      <ResponsiveContainer width="100%" height={324}>
        <LineChart data={data}>
          <XAxis dataKey="time" />
          <YAxis unit="C" />
          <Tooltip />
          <Legend onClick={toggleLine} style={{ cursor: "pointer" }} />
          <Line type="monotone" dataKey="tc1_temp"  name="TC1"      dot={false} stroke="#f97316" hide={!!hidden.tc1_temp} />
          <Line type="monotone" dataKey="tc2_temp"  name="TC2"      dot={false} stroke="#60a5fa" hide={!!hidden.tc2_temp} />
          <Line type="monotone" dataKey="setpoint"  name="Setpoint" dot={false} stroke="#a3e635" strokeDasharray="4 2" hide={!!hidden.setpoint} />
          <Brush
            dataKey="time"
            startIndex={brush.startIndex}
            endIndex={Math.min(brush.endIndex, data.length - 1)}
            onChange={handleBrush}
            height={24}
            stroke="#2a2d3a"
            fill="#1a1d27"
            travellerWidth={8}
            tick={{ fontSize: 10, fill: "#64748b" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
