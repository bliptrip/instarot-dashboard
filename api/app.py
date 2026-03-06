import json, queue, time, threading, logging
from flask import Flask, Response, stream_with_context, jsonify, request, abort
import database, config

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
