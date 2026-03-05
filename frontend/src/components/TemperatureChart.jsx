import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer
} from "recharts";

const RANGES = [
  { label: "1h",  seconds: 3600,    resolution: "raw"   },
  { label: "24h", seconds: 86400,   resolution: "1min"  },
  { label: "7d",  seconds: 604800,  resolution: "10min" },
  { label: "30d", seconds: 2592000, resolution: "1hr"   },
];

export default function TemperatureChart({ device }) {
  const [data,  setData]  = useState([]);
  const [range, setRange] = useState(RANGES[0]);

  useEffect(() => {
    const end   = Math.floor(Date.now() / 1000);
    const start = end - range.seconds;
    fetch(`/api/history/${device}?start=${start}&end=${end}&resolution=${range.resolution}`)
      .then(r => r.json())
      .then(rows => setData(rows.map(r => ({
        ...r,
        time: new Date(r.ts * 1000).toLocaleTimeString(),
      }))));
  }, [device, range]);

  return (
    <div className="chart-panel">
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
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <XAxis dataKey="time" />
          <YAxis unit="C" />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="tc1_temp"  name="TC1"      dot={false} stroke="#f97316" />
          <Line type="monotone" dataKey="tc2_temp"  name="TC2"      dot={false} stroke="#60a5fa" />
          <Line type="monotone" dataKey="setpoint"  name="Setpoint" dot={false} stroke="#a3e635" strokeDasharray="4 2" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
