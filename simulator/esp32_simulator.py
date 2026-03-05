#!/usr/bin/env python3
"""
ESP32 PID Temperature Controller Simulator

Simulates an instarot ESP32 device on MQTT with a realistic thermal model.
State (setpoint, PID parameters) persists across restarts via a JSON file.

MQTT topics (mirrors real firmware):
  Publishes:
    instarot/{hostname}/state       - periodic state (1 Hz)
    instarot/{hostname}/state_pid   - live PID debug (only when enabled)

  Subscribes:
    instarot/{hostname}/cmd/setpoint     - plain float string, e.g. "225.0"
    instarot/{hostname}/cmd/pid          - JSON {"kp":..., "ki":..., "kd":...}
    instarot/{hostname}/cmd/publish_pids - "1" to enable, "0" to disable

Thermal model (first-order):
  dT/dt = (P_max * (output/100) - k_loss * (T - T_amb)) / thermal_mass

  With the defaults below the heater can reach ~300 °C at 100 % output,
  and has a thermal time constant of ~5 minutes — typical for a small oven.
"""

import json
import logging
import math
import os
import random
import signal
import sys
import threading
import time

import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Configuration – override via environment variables
# ---------------------------------------------------------------------------
HOSTNAME        = os.environ.get("SIMULATOR_HOSTNAME",   "simulator")
MQTT_BROKER     = os.environ.get("MQTT_BROKER",          "phytopi.local")
MQTT_PORT       = int(os.environ.get("MQTT_PORT",        "1883"))
STATE_FILE      = os.environ.get("SIMULATOR_STATE_FILE",
                                 os.path.join(os.path.dirname(__file__),
                                              "simulator_state.json"))
STATE_INTERVAL  = float(os.environ.get("STATE_INTERVAL",  "1.0"))   # seconds
SIM_DT          = float(os.environ.get("SIM_DT",          "0.1"))    # simulation timestep (s)

# ---------------------------------------------------------------------------
# Thermal model constants
# ---------------------------------------------------------------------------
T_AMBIENT   = 25.0    # °C  ambient / room temperature
P_MAX       = 2000.0  # W   maximum heater power
K_LOSS      = 6.5     # W/°C  heat loss coefficient (steady-state Tmax ≈ T_amb + P_MAX/K_LOSS ≈ 333 °C)
THERMAL_MASS = 2000.0 # J/°C  effective thermal mass (τ = THERMAL_MASS/K_LOSS ≈ 308 s ≈ 5 min)
NOISE_STD   = 0.15    # °C  thermocouple read noise (std dev)
TC2_OFFSET  = -8.0    # °C  tc2 reads slightly cooler than tc1 (different location)
TC2_TAU     = 60.0    # s   tc2 lags tc1 (slower thermal path)

# ---------------------------------------------------------------------------
# PID defaults
# ---------------------------------------------------------------------------
DEFAULT_SETPOINT = 0.0   # Cold at startup unless overridden
DEFAULT_KP       = 2.0
DEFAULT_KI       = 0.05
DEFAULT_KD       = 1.0
OUTPUT_MIN       = 0.0
OUTPUT_MAX       = 100.0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persistent state
# ---------------------------------------------------------------------------

def load_state() -> dict:
    defaults = {
        "setpoint":    DEFAULT_SETPOINT,
        "kp":          DEFAULT_KP,
        "ki":          DEFAULT_KI,
        "kd":          DEFAULT_KD,
        "temperature": T_AMBIENT,
        "tc2_temp":    T_AMBIENT + TC2_OFFSET,
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                saved = json.load(f)
            defaults.update(saved)
            log.info(f"Loaded state from {STATE_FILE}: setpoint={defaults['setpoint']} "
                     f"kp={defaults['kp']} ki={defaults['ki']} kd={defaults['kd']}")
        except Exception as e:
            log.warning(f"Could not load state file ({e}), using defaults")
    return defaults


def save_state(state: dict):
    keys = ("setpoint", "kp", "ki", "kd", "temperature", "tc2_temp")
    try:
        os.makedirs(os.path.dirname(os.path.abspath(STATE_FILE)), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({k: state[k] for k in keys}, f, indent=2)
    except Exception as e:
        log.warning(f"Could not save state: {e}")


# ---------------------------------------------------------------------------
# PID controller
# ---------------------------------------------------------------------------

class PIDController:
    def __init__(self, kp: float, ki: float, kd: float):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._integral   = 0.0
        self._prev_error = None

    def reset_integral(self):
        self._integral = 0.0
        self._prev_error = None

    def compute(self, setpoint: float, measurement: float, dt: float):
        error = setpoint - measurement

        # Proportional
        p = self.kp * error

        # Integral with anti-windup clamping
        self._integral += error * dt
        i_term = self.ki * self._integral

        # Derivative (on measurement to avoid derivative kick on setpoint change)
        if self._prev_error is None:
            d = 0.0
        else:
            d = self.kd * (error - self._prev_error) / dt
        self._prev_error = error

        raw_output = p + i_term + d
        output = max(OUTPUT_MIN, min(OUTPUT_MAX, raw_output))

        # Back-calculate integral to prevent wind-up
        if raw_output != output:
            correction = (output - raw_output) / (self.ki if self.ki != 0 else 1.0)
            self._integral += correction

        return output, error, p, i_term, d


# ---------------------------------------------------------------------------
# Thermal model
# ---------------------------------------------------------------------------

class ThermalModel:
    """First-order linear thermal model with a lagged secondary sensor."""

    def __init__(self, initial_temp: float, initial_tc2: float):
        self.temp     = float(initial_temp)
        self.tc2_temp = float(initial_tc2)

    def step(self, output_pct: float, dt: float):
        """Advance simulation by dt seconds given heater output 0–100 %."""
        # Primary thermal node
        p_heat  = P_MAX * (output_pct / 100.0)
        p_loss  = K_LOSS * (self.temp - T_AMBIENT)
        dT      = (p_heat - p_loss) / THERMAL_MASS
        self.temp += dT * dt

        # Secondary sensor: first-order lag toward tc1 + fixed spatial offset
        target_tc2 = self.temp + TC2_OFFSET
        self.tc2_temp += (target_tc2 - self.tc2_temp) / TC2_TAU * dt

    def read_tc1(self) -> float:
        return self.temp + random.gauss(0, NOISE_STD)

    def read_tc2(self) -> float:
        return self.tc2_temp + random.gauss(0, NOISE_STD)


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

class ESP32Simulator:
    def __init__(self):
        self._state = load_state()
        self._lock  = threading.Lock()

        self._thermal = ThermalModel(
            self._state["temperature"],
            self._state["tc2_temp"],
        )
        self._pid = PIDController(
            self._state["kp"],
            self._state["ki"],
            self._state["kd"],
        )
        self._output         = 0.0
        self._publish_pids   = False
        self._running        = True
        self._last_save      = time.time()
        self._last_state_pub = time.time() - STATE_INTERVAL

        # MQTT
        self._client = mqtt.Client(client_id=f"esp32-sim-{HOSTNAME}")
        self._client.on_connect    = self._on_connect
        self._client.on_message    = self._on_message
        self._client.on_disconnect = self._on_disconnect

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            log.error(f"MQTT connect failed rc={rc}")
            return
        log.info(f"MQTT connected to {MQTT_BROKER}:{MQTT_PORT} as {HOSTNAME}")
        base = f"instarot/{HOSTNAME}/cmd"
        client.subscribe(f"{base}/setpoint")
        client.subscribe(f"{base}/pid")
        client.subscribe(f"{base}/publish_pids")
        log.info("Subscribed to command topics")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            log.warning(f"Unexpected MQTT disconnect rc={rc}, will auto-reconnect")

    def _on_message(self, client, userdata, msg):
        topic   = msg.topic
        payload = msg.payload.decode("utf-8", errors="replace").strip()
        log.debug(f"RX {topic}: {payload}")

        if topic.endswith("/cmd/setpoint"):
            self._handle_setpoint(payload)
        elif topic.endswith("/cmd/pid"):
            self._handle_pid(payload)
        elif topic.endswith("/cmd/publish_pids"):
            self._handle_publish_pids(payload)

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _handle_setpoint(self, payload: str):
        try:
            value = float(payload)
        except ValueError:
            log.warning(f"Bad setpoint payload: {payload!r}")
            return
        with self._lock:
            self._state["setpoint"] = value
            self._pid.reset_integral()
        log.info(f"Setpoint -> {value} °C")
        save_state(self._state)

    def _handle_pid(self, payload: str):
        try:
            params = json.loads(payload)
        except json.JSONDecodeError:
            log.warning(f"Bad PID payload: {payload!r}")
            return
        with self._lock:
            if "kp" in params:
                self._state["kp"] = float(params["kp"])
                self._pid.kp      = self._state["kp"]
            if "ki" in params:
                self._state["ki"] = float(params["ki"])
                self._pid.ki      = self._state["ki"]
            if "kd" in params:
                self._state["kd"] = float(params["kd"])
                self._pid.kd      = self._state["kd"]
            self._pid.reset_integral()
        log.info(f"PID params -> kp={self._state['kp']} ki={self._state['ki']} kd={self._state['kd']}")
        save_state(self._state)

    def _handle_publish_pids(self, payload: str):
        enabled = payload.strip() == "1"
        with self._lock:
            self._publish_pids = enabled
        log.info(f"publish_pids -> {enabled}")

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def _sim_loop(self):
        last_t = time.monotonic()

        while self._running:
            now = time.monotonic()
            dt  = now - last_t
            last_t = now

            with self._lock:
                setpoint = self._state["setpoint"]
                kp, ki, kd = self._state["kp"], self._state["ki"], self._state["kd"]

            # Read temperatures (with sensor noise)
            tc1 = self._thermal.read_tc1()

            # PID step
            output, error, p_term, i_term, d_term = self._pid.compute(setpoint, tc1, dt)
            self._output = output

            # Advance thermal model
            self._thermal.step(output, dt)

            # Snapshot for publishing
            with self._lock:
                self._state["temperature"] = self._thermal.temp
                self._state["tc2_temp"]    = self._thermal.tc2_temp
                self._last_output  = output
                self._last_error   = error
                self._last_p_term  = p_term
                self._last_i_term  = i_term
                self._last_d_term  = d_term
                should_pub_pids    = self._publish_pids

            wall_ts = int(time.time())

            # Publish state_pid every sim tick when enabled
            if should_pub_pids:
                self._publish_state_pid(tc1, setpoint, error, p_term, i_term, d_term, output, wall_ts)

            # Publish state at configured interval
            if time.monotonic() - self._last_state_pub >= STATE_INTERVAL:
                self._last_state_pub = time.monotonic()
                self._publish_state(tc1, self._thermal.read_tc2(), setpoint, output, wall_ts)

            # Persist state every 30 s
            if time.time() - self._last_save >= 30:
                save_state(self._state)
                self._last_save = time.time()

            elapsed = time.monotonic() - now
            sleep_for = max(0.0, SIM_DT - elapsed)
            time.sleep(sleep_for)

    # ------------------------------------------------------------------
    # MQTT publish helpers
    # ------------------------------------------------------------------

    def _publish_state(self, tc1: float, tc2: float, setpoint: float,
                       output: float, ts: int):
        with self._lock:
            kp, ki, kd = self._state["kp"], self._state["ki"], self._state["kd"]
        payload = json.dumps({
            "tc1_temp": round(tc1, 2),
            "tc2_temp": round(tc2, 2),
            "setpoint": round(setpoint, 2),
            "output":   round(output, 2),
            "kp":       kp,
            "ki":       ki,
            "kd":       kd,
            "ts":       ts,
        })
        self._client.publish(f"instarot/{HOSTNAME}/state", payload, retain=True)
        log.debug(f"TX state: {payload}")

    def _publish_state_pid(self, current_temp: float, setpoint: float,
                           error: float, p: float, i: float, d: float,
                           output: float, ts: int):
        with self._lock:
            kp, ki, kd = self._state["kp"], self._state["ki"], self._state["kd"]
        payload = json.dumps({
            "current_temp": round(current_temp, 2),
            "setpoint":     round(setpoint, 2),
            "error":        round(error, 4),
            "error_p":      round(p, 4),
            "error_i":      round(i, 4),
            "error_d":      round(d, 4),
            "output":       round(output, 2),
            "kp":           kp,
            "ki":           ki,
            "kd":           kd,
            "ts":           ts,
        })
        self._client.publish(f"instarot/{HOSTNAME}/state_pid", payload)
        log.debug(f"TX state_pid: {payload}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self._client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self._client.loop_start()

        sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
        sim_thread.start()

        log.info(f"ESP32 simulator started — device={HOSTNAME} "
                 f"setpoint={self._state['setpoint']} °C "
                 f"kp={self._state['kp']} ki={self._state['ki']} kd={self._state['kd']}")

        def _shutdown(sig, frame):
            log.info("Shutdown signal received")
            self._running = False
            save_state(self._state)
            self._client.loop_stop()
            self._client.disconnect()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT,  _shutdown)

        sim_thread.join()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sim = ESP32Simulator()
    sim.start()
