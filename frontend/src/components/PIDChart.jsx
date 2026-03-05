import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import useLivePIDs from "../hooks/useLivePIDs";

export default function PIDChart({ device }) {
  const history = useLivePIDs(device);

  return (
    <div className="chart-panel">
      <h3 style={{ margin: "0 0 0.5rem" }}>Live PID Debug — {device}</h3>

      <p style={{ margin: "0 0 0.25rem", fontWeight: 600, fontSize: "0.85rem" }}>Temperature vs Setpoint</p>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={history}>
          <XAxis dataKey="time" tick={{ fontSize: 11 }} />
          <YAxis unit="°C" tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="temp"     name="Temp"     dot={false} stroke="#f97316" isAnimationActive={true} />
          <Line type="monotone" dataKey="setpoint" name="Setpoint" dot={false} stroke="#a3e635" strokeDasharray="4 2" isAnimationActive={true} />
        </LineChart>
      </ResponsiveContainer>

      <p style={{ margin: "0.75rem 0 0.25rem", fontWeight: 600, fontSize: "0.85rem" }}>PID Error Terms</p>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={history}>
          <XAxis dataKey="time" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="error"   name="Error" dot={false} stroke="#f43f5e" isAnimationActive={false} />
          <Line type="monotone" dataKey="error_p" name="P"     dot={false} stroke="#60a5fa" isAnimationActive={false} />
          <Line type="monotone" dataKey="error_i" name="I"     dot={false} stroke="#a78bfa" isAnimationActive={false} />
          <Line type="monotone" dataKey="error_d" name="D"     dot={false} stroke="#34d399" isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>

      <p style={{ margin: "0.75rem 0 0.25rem", fontWeight: 600, fontSize: "0.85rem" }}>Output</p>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart data={history}>
          <XAxis dataKey="time" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="output" name="Output" dot={false} stroke="#fb923c" isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
