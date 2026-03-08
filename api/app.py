import json, queue, time, threading, logging
from flask import Flask, Response, stream_with_context, jsonify, request, abort
import database, config

# Active program runs: run_id -> threading.Event (stop signal)
_active_runs = {}
_active_runs_lock = threading.Lock()

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

app = Flask(__name__)
database.init_db()

_subscribers = []
_subscribers_lock = threading.Lock()

def broadcast(data: dict):
    msg = json.dumps(data)
    with _subscribers_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)

def poll_latest_loop():
    while True:
        time.sleep(2)
        try:
            devices = database.get_devices()
            for d in devices:
                latest = database.get_latest(d["hostname"])
                if latest:
                    broadcast({"type": "reading", "device": d["hostname"], "data": latest})
        except Exception as e:
            log.error(f"Poll error: {e}")

threading.Thread(target=poll_latest_loop, daemon=True).start()

@app.route("/stream")
def stream():
    q = queue.Queue(maxsize=30)
    with _subscribers_lock:
        _subscribers.append(q)

    def generate():
        try:
            while True:
                try:
                    msg = q.get(timeout=15)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            with _subscribers_lock:
                if q in _subscribers:
                    _subscribers.remove(q)

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

@app.route("/stream-pids/<device>")
def stream_pids(device):
    import paho.mqtt.client as mqtt
    def on_connect(client, userdata, flags, rc):
        log.info(f"MQTT connected (rc={rc})")
        #Publish command to send realtime pid data
        log.info(f"Enable publish_pids for device {device}.")
        client.publish(f"instarot/{device}/cmd/publish_pids",
                       payload=str(1))
        client.subscribe(f'instarot/{device}/state_pid')

    def on_message(client, userdata, msg):
        try:
            q = userdata
            payload = json.loads(msg.payload)
            hostname = msg.topic.split("/")[1]
            now = int(time.time())
            pid_state = {
                "device": hostname,
                "setpoint": payload.get("setpoint"),
                "temp": payload.get("current_temp"),
                "error": payload.get("error"),
                "error_p": payload.get("error_p"),
                "error_i": payload.get("error_i"),
                "error_d": payload.get("error_d"),
                "output": payload.get("output"),
                "kp": payload.get("kp"),
                "ki": payload.get("ki"),
                "kd": payload.get("kd"),
                "ts": payload.get("ts", now),
            }
            log.debug(f"Received payload on {msg.topic}: {pid_state}")
            q.put(json.dumps(pid_state))
        except Exception as e:
            log.warning(f"Bad payload on {msg.topic}: {e}")
            pass

    q = queue.Queue(maxsize=30)
    client = mqtt.Client(userdata=q)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(config.MQTT_BROKER, config.MQTT_PORT, keepalive=60)
    client.loop_start()

    def generate():
        try:
            while True:
                try:
                    msg = q.get(timeout=15)
                    log.debug(f"generate(): Queue received message {msg}.")
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    log.debug(f"generate(): Nothing in queue, generating heartbeat.")
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            #First disable the debug publishing of active pid data
            client.publish(f"instarot/{device}/cmd/publish_pids",
                        payload=str(0))
            client.loop_stop()
        except OSError: #Also handle client disconnect events
            #First disable the debug publishing of active pid data
            client.publish(f"instarot/{device}/cmd/publish_pids",
                        payload=str(0))
            client.loop_stop()

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

@app.route("/api/devices")
def devices():
    return jsonify(database.get_devices())

@app.route("/api/history/<device>")
def history(device):
    session_id = request.args.get("session_id", type=int)
    if session_id:
        session = database.get_session(session_id)
        if not session:
            abort(404, "Session not found")
        start = session["started_at"]
        end   = session["ended_at"] or int(time.time())
        duration = end - start
        if duration <= 3600:
            res = "raw"
        elif duration <= 86400:
            res = "1min"
        elif duration <= 604800:
            res = "10min"
        else:
            res = "1hr"
    else:
        end   = int(request.args.get("end",   time.time()))
        start = int(request.args.get("start", end - 3600))
        res   = request.args.get("resolution", "raw")
    if res not in ("raw", "1min", "10min", "1hr"):
        abort(400, "Invalid resolution")
    return jsonify(database.get_history(device, start, end, res))

@app.route("/api/cmd/<device>/setpoint", methods=["POST"])
def set_setpoint(device):
    import paho.mqtt.publish as publish
    value = request.json.get("value")
    publish.single(f"instarot/{device}/cmd/setpoint",
                   payload=str(value),
                   hostname=config.MQTT_BROKER)
    return jsonify({"ok": True})

@app.route("/api/cmd/<device>/pid", methods=["POST"])
def set_pid(device):
    import paho.mqtt.publish as publish
    pids = request.data.decode('utf-8')
    publish.single(f"instarot/{device}/cmd/pid",
                   payload=pids,
                   hostname=config.MQTT_BROKER)
    return jsonify({"ok": True})

# ── Sessions ──────────────────────────────────────────────────────────────────

@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    device = request.args.get("device")
    return jsonify(database.get_sessions(device))

@app.route("/api/sessions", methods=["POST"])
def create_session():
    body = request.json or {}
    name = body.get("name", "").strip()
    device = body.get("device", "").strip()
    if not name or not device:
        abort(400, "name and device are required")
    sid = database.create_session(name, device)
    return jsonify(database.get_session(sid)), 201

@app.route("/api/sessions/<int:sid>", methods=["GET"])
def get_session(sid):
    s = database.get_session(sid)
    if not s:
        abort(404)
    return jsonify(s)

@app.route("/api/sessions/<int:sid>", methods=["PUT"])
def update_session(sid):
    body = request.json or {}
    ended_at = body.get("ended_at")
    notes = body.get("notes")
    if ended_at is None and "end_now" in body and body["end_now"]:
        ended_at = int(time.time())
    database.update_session(sid, ended_at=ended_at, notes=notes)
    return jsonify(database.get_session(sid))

@app.route("/api/sessions/<int:sid>", methods=["DELETE"])
def delete_session(sid):
    database.delete_session(sid)
    return jsonify({"ok": True})

# ── Programs ──────────────────────────────────────────────────────────────────

@app.route("/api/programs", methods=["GET"])
def list_programs():
    return jsonify(database.get_programs())

@app.route("/api/programs", methods=["POST"])
def create_program():
    body = request.json or {}
    name = body.get("name", "").strip()
    if not name:
        abort(400, "name is required")
    steps = body.get("steps", [])
    description = body.get("description", "")
    pid = database.create_program(name, description, steps)
    return jsonify(database.get_program(pid)), 201

@app.route("/api/programs/<int:pid>", methods=["GET"])
def get_program(pid):
    p = database.get_program(pid)
    if not p:
        abort(404)
    return jsonify(p)

@app.route("/api/programs/<int:pid>", methods=["PUT"])
def update_program(pid):
    body = request.json or {}
    p = database.get_program(pid)
    if not p:
        abort(404)
    name = body.get("name", p["name"])
    description = body.get("description", p["description"])
    steps = body.get("steps", p["steps"])
    database.update_program(pid, name, description, steps)
    return jsonify(database.get_program(pid))

@app.route("/api/programs/<int:pid>", methods=["DELETE"])
def delete_program(pid):
    database.delete_program(pid)
    return jsonify({"ok": True})

# ── Program Runs ──────────────────────────────────────────────────────────────

def _run_program(run_id, program, device, session_id, stop_event):
    """Execute program steps in a background thread."""
    import paho.mqtt.publish as publish
    steps = sorted(program["steps"], key=lambda s: s["at"])
    started_at = time.time()

    try:
        for i, step in enumerate(steps):
            # Wait until it's time for this step (or stop is requested)
            delay = started_at + step["at"] - time.time()
            if delay > 0:
                if stop_event.wait(timeout=delay):
                    break  # stopped

            if stop_event.is_set():
                break

            action = step.get("action")
            value  = step.get("value")
            try:
                if action == "setpoint":
                    publish.single(
                        f"instarot/{device}/cmd/setpoint",
                        payload=str(value),
                        hostname=config.MQTT_BROKER
                    )
                elif action == "pid":
                    publish.single(
                        f"instarot/{device}/cmd/pid",
                        payload=json.dumps(value),
                        hostname=config.MQTT_BROKER
                    )
                log.info(f"Run {run_id} step {i}: {action} -> {value}")
                database.update_program_run(run_id, current_step=i + 1)
            except Exception as e:
                log.error(f"Run {run_id} step {i} error: {e}")

        status = "stopped" if stop_event.is_set() else "completed"
    except Exception as e:
        log.error(f"Run {run_id} fatal error: {e}")
        status = "error"

    ended_at = int(time.time())
    database.update_program_run(run_id, status=status, ended_at=ended_at)
    if session_id:
        database.update_session(session_id, ended_at=ended_at)

    with _active_runs_lock:
        _active_runs.pop(run_id, None)


@app.route("/api/programs/<int:pid>/run", methods=["POST"])
def run_program(pid):
    program = database.get_program(pid)
    if not program:
        abort(404)
    body = request.json or {}
    device = body.get("device", "").strip()
    if not device:
        abort(400, "device is required")
    session_name = body.get("session_name", "").strip()

    # Optionally create a session for this run
    session_id = None
    if session_name:
        session_id = database.create_session(session_name, device)

    run_id = database.create_program_run(pid, session_id, device)
    stop_event = threading.Event()
    with _active_runs_lock:
        _active_runs[run_id] = stop_event

    t = threading.Thread(
        target=_run_program,
        args=(run_id, program, device, session_id, stop_event),
        daemon=True
    )
    t.start()

    run = database.get_program_run(run_id)
    if session_id:
        run["session"] = database.get_session(session_id)
    return jsonify(run), 201


@app.route("/api/runs", methods=["GET"])
def list_runs():
    program_id = request.args.get("program_id", type=int)
    runs = database.get_program_runs(program_id)
    return jsonify(runs)


@app.route("/api/runs/<int:run_id>", methods=["GET"])
def get_run(run_id):
    run = database.get_program_run(run_id)
    if not run:
        abort(404)
    return jsonify(run)


@app.route("/api/runs/<int:run_id>/stop", methods=["POST"])
def stop_run(run_id):
    with _active_runs_lock:
        stop_event = _active_runs.get(run_id)
    if stop_event:
        stop_event.set()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
