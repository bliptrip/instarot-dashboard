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
├── simulator/
│   └── esp32_simulator.py  # Software ESP32 PID simulator (systemd service)
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
│   ├── dashboard.service
│   └── simulator.service
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

| Direction | Topic | Payload |
|-----------|-------|---------|
| Device → broker | `instarot/{hostname}/state` | `{"tc1_temp": 225.5, "tc2_temp": 72.1, "setpoint": 225.0, "output": 78.5, "kp": 2.0, "ki": 0.05, "kd": 1.0, "ts": 1700000000}` |
| Device → broker | `instarot/{hostname}/state_pid` | `{"current_temp": 225.5, "setpoint": 225.0, "error": -0.5, "error_p": -1.0, "error_i": 0.2, "error_d": 0.1, "output": 78.5, "kp": 2.0, "ki": 0.05, "kd": 1.0, "ts": 1700000000}` |
| Dashboard → device | `instarot/{hostname}/cmd/setpoint` | `"225.0"` (plain float string) |
| Dashboard → device | `instarot/{hostname}/cmd/pid` | `{"kp": 2.0, "ki": 0.05, "kd": 1.0}` |
| Dashboard → device | `instarot/{hostname}/cmd/publish_pids` | `"1"` to enable live PID stream, `"0"` to disable |

## ESP32 Simulator

`simulator/esp32_simulator.py` is a drop-in software replacement for a physical ESP32 device.
It publishes the same MQTT topics and responds to the same commands, so the full dashboard
stack works without hardware.

### Thermal model

The simulator uses a first-order energy-balance model:

```
dT/dt = (P_max × output/100 − k_loss × (T − T_amb)) / thermal_mass
```

| Parameter | Value | Notes |
|-----------|-------|-------|
| `P_max` | 2000 W | Maximum heater power |
| `k_loss` | 6.5 W/°C | Heat loss to ambient; gives ≈ 333 °C at 100 % output |
| `thermal_mass` | 2000 J/°C | Time constant τ ≈ 5 min |
| `T_ambient` | 25 °C | Room temperature |
| tc2 offset | −8 °C | Second thermocouple is physically cooler |
| tc2 lag | 60 s | First-order lag on the secondary sensor |
| Sensor noise | ±0.15 °C | Gaussian read noise on both sensors |

### Configuration

All settings can be overridden with environment variables (no code edit needed):

| Variable | Default | Description |
|----------|---------|-------------|
| `SIMULATOR_HOSTNAME` | `simulator` | Device name used in MQTT topics |
| `MQTT_BROKER` | `phytopi.local` | MQTT broker hostname or IP |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `SIMULATOR_STATE_FILE` | `simulator/simulator_state.json` | Path to the persistent state file |
| `STATE_INTERVAL` | `1.0` | Seconds between `state` publishes |
| `SIM_DT` | `0.1` | Simulation timestep in seconds |

### Persistent state

On every command received and every 30 seconds, the simulator writes
`simulator_state.json` with the current setpoint, PID parameters, and temperature.
On restart it reads this file so the device resumes from where it left off.

### Running manually

```bash
# Dependencies are the same as the rest of the project
pip3 install -r requirements.txt

# Run with defaults
python3 simulator/esp32_simulator.py

# Run with a custom hostname and broker
SIMULATOR_HOSTNAME=oven-1 MQTT_BROKER=192.168.1.10 python3 simulator/esp32_simulator.py
```

### Installing as a systemd service

```bash
sudo cp services/simulator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable simulator
sudo systemctl start simulator

# To configure hostname/broker without editing the script, uncomment and set
# the Environment= lines in simulator.service before copying it.
```
