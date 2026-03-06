import { useState, useEffect, useRef } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, Brush,
} from "recharts";
import useLivePIDs from "../hooks/useLivePIDs";

function SectionHeader({ title, collapsed, onToggle }) {
  return (
    <div className="pid-section-header" onClick={onToggle}>
      <span>{title}</span>
      <span className={`pid-section-chevron${collapsed ? " collapsed" : ""}`}>▾</span>
    </div>
  );
}

export default function PIDChart({ device }) {
  const history = useLivePIDs(device);
  const [brush, setBrush] = useState({ startIndex: 0, endIndex: 0 });
  const [paused, setPaused] = useState(false);
  const [snapshot, setSnapshot] = useState([]);
  const [hidden, setHidden] = useState({});
  const [collapsed, setCollapsed] = useState({});
  const pausedRef = useRef(false);

  useEffect(() => { pausedRef.current = paused; }, [paused]);

  // Follow the latest data unless paused
  useEffect(() => {
    if (history.length === 0) return;
    if (!pausedRef.current) {
      setBrush({ startIndex: 0, endIndex: history.length - 1 });
    }
  }, [history.length]);

  const handleBrush = ({ startIndex, endIndex }) => {
    if (!pausedRef.current) {
      setSnapshot([...history]);
    }
    setPaused(true);
    setBrush({ startIndex, endIndex });
  };

  const handlePause = () => {
    setSnapshot([...history]);
    setPaused(true);
  };

  const handleResume = () => {
    setPaused(false);
    setSnapshot([]);
    setBrush({ startIndex: 0, endIndex: history.length - 1 });
  };

  const toggleLine = (dataKey) => {
    setHidden(prev => ({ ...prev, [dataKey]: !prev[dataKey] }));
  };

  const toggleSection = (key) => {
    setCollapsed(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const displayData = paused ? snapshot : history;
  const safeEnd = Math.min(brush.endIndex, displayData.length - 1);
  const visible = displayData.slice(brush.startIndex, safeEnd + 1);

  const brushProps = {
    dataKey: "time",
    startIndex: brush.startIndex,
    endIndex: safeEnd,
    onChange: handleBrush,
    height: 24,
    stroke: "#2a2d3a",
    fill: "#1a1d27",
    travellerWidth: 8,
    tick: { fontSize: 10, fill: "#64748b" },
  };

  return (
    <div className="chart-panel" style={{ marginTop: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Live PID Debug — {device}</h3>
        <button
          className={`live-toggle ${paused ? "paused" : "live"}`}
          onClick={paused ? handleResume : handlePause}
        >
          {paused ? "Resume" : "Pause"}
        </button>
      </div>

      <SectionHeader title="Temperature vs Setpoint" collapsed={collapsed.temp} onToggle={() => toggleSection("temp")} />
      {!collapsed.temp && (
        <ResponsiveContainer width="100%" height={224}>
          <LineChart data={displayData}>
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis unit="°C" tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend onClick={({ dataKey }) => toggleLine(dataKey)} />
            <Line type="monotone" dataKey="temp"     name="Temp"     dot={false} stroke="#f97316" hide={!!hidden.temp}     isAnimationActive={false} />
            <Line type="monotone" dataKey="setpoint" name="Setpoint" dot={false} stroke="#a3e635" hide={!!hidden.setpoint} strokeDasharray="4 2" isAnimationActive={false} />
            <Brush {...brushProps} />
          </LineChart>
        </ResponsiveContainer>
      )}

      <SectionHeader title="PID Error Terms" collapsed={collapsed.error} onToggle={() => toggleSection("error")} />
      {!collapsed.error && (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={visible}>
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend onClick={({ dataKey }) => toggleLine(dataKey)} />
            <Line type="monotone" dataKey="error"   name="Error" dot={false} stroke="#f43f5e" hide={!!hidden.error}   isAnimationActive={false} />
            <Line type="monotone" dataKey="error_p" name="P"     dot={false} stroke="#60a5fa" hide={!!hidden.error_p} isAnimationActive={false} />
            <Line type="monotone" dataKey="error_i" name="I"     dot={false} stroke="#a78bfa" hide={!!hidden.error_i} isAnimationActive={false} />
            <Line type="monotone" dataKey="error_d" name="D"     dot={false} stroke="#34d399" hide={!!hidden.error_d} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      )}

      <SectionHeader title="PID Gains" collapsed={collapsed.gains} onToggle={() => toggleSection("gains")} />
      {!collapsed.gains && (
        <ResponsiveContainer width="100%" height={150}>
          <LineChart data={visible}>
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend onClick={({ dataKey }) => toggleLine(dataKey)} />
            <Line type="monotone" dataKey="kp" name="Kp" dot={false} stroke="#60a5fa" hide={!!hidden.kp} isAnimationActive={false} />
            <Line type="monotone" dataKey="ki" name="Ki" dot={false} stroke="#a78bfa" hide={!!hidden.ki} isAnimationActive={false} />
            <Line type="monotone" dataKey="kd" name="Kd" dot={false} stroke="#34d399" hide={!!hidden.kd} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      )}

      <SectionHeader title="Output" collapsed={collapsed.output} onToggle={() => toggleSection("output")} />
      {!collapsed.output && (
        <ResponsiveContainer width="100%" height={150}>
          <LineChart data={visible}>
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend onClick={({ dataKey }) => toggleLine(dataKey)} />
            <Line type="monotone" dataKey="output" name="Output" dot={false} stroke="#fb923c" hide={!!hidden.output} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
