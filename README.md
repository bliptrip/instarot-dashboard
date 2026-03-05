# Instarot Dashboard

Flask + SQLite + React dashboard for ESP32-based PID temperature controllers.

## Project Structure

```
instarot-dashboard/
├── api/
│   ├── app.py              # Flask server + SSE endpoint
│   ├── database.py         # SQLite schema, queries, tiered downsampling
│   └── config.py           # Broker, retention periods, paths
├── collector/
│   └── mqtt_collector.py   # MQTT subscriber -> SQLite writer (systemd service)
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── index.css
│       ├── hooks/
│       │   └── useLiveData.js
│       └── components/
│           ├── DeviceCard.jsx
│           ├── TemperatureChart.jsx
│           └── SetpointControl.jsx
├── services/
│   ├── collector.service
│   └── dashboard.service
├── requirements.txt
└── README.md
```

## Setup

### 1. Python dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Edit config
Update `api/config.py` with your MQTT broker address and desired DB path.

### 3. Install systemd services
```bash
sudo cp services/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable collector dashboard
sudo systemctl start collector dashboard
```

### 4. Build the frontend
```bash
cd frontend
npm install
npm run build
# Serve frontend/dist/ as static files from Flask, or via nginx
```

### 5. Dev mode (hot reload, proxied to Flask)
```bash
cd frontend && npm run dev
```

## Data Retention Tiers

| Tier   | Resolution   | Kept for |
|--------|-------------|----------|
| raw    | as received | 24 hours |
| 1min   | 1-min avg   | 7 days   |
| 10min  | 10-min avg  | 30 days  |
| 1hr    | hourly avg  | 1 year   |

Downsampling runs automatically every 20 minutes inside the collector process.

## MQTT Topics

- ESP32 publishes: `instarot/{hostname}/state`
  ```json
  {"tc1_temp": 225.5, "tc2_temp": 72.1, "setpoint": 225.0, "output": 78.5, "ts": 1700000000}
  ```
- Dashboard sends: `instarot/{hostname}/cmd/setpoint`
