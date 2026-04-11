import json, time, logging, threading
import paho.mqtt.client as mqtt
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
import config, database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

database.init_db()

buffer = []
buffer_lock = threading.Lock()

def flush_loop():
    while True:
        time.sleep(config.WRITE_BUFFER_INTERVAL)
        with buffer_lock:
            if not buffer:
                continue
            batch = buffer[:]
            buffer.clear()
        try:
            database.insert_batch(batch)
            log.info(f"Flushed {len(batch)} readings to DB")
        except Exception as e:
            log.error(f"DB flush failed: {e}")

def maintenance_loop():
    while True:
        time.sleep(60 * 20)
        try:
            database.downsample_and_cull()
        except Exception as e:
            log.error(f"Maintenance failed: {e}")

def on_connect(client, userdata, flags, rc):
    log.info(f"MQTT connected (rc={rc})")
    client.subscribe(config.MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
        hostname = msg.topic.split("/")[1]
        now = int(time.time())
        row = {
            "device":   hostname,
            "tc1_temp": payload.get("tc1_temp"),
            "tc2_temp": payload.get("tc2_temp"),
            "setpoint": payload.get("setpoint"),
            "output":   payload.get("output"),
            "kp":       payload.get("kp"),
            "ki":       payload.get("ki"),
            "kd":       payload.get("kd"),
            "error":    payload.get("error"),
            "error_p":  payload.get("error_p"),
            "error_i":  payload.get("error_i"),
            "error_d":  payload.get("error_d"),
            "ts":       payload.get("ts", now),
        }
        with buffer_lock:
            buffer.append(row)
        database.upsert_device(hostname, now, row["tc1_temp"])
    except Exception as e:
        log.warning(f"Bad payload on {msg.topic}: {e}")

threading.Thread(target=flush_loop,       daemon=True).start()
threading.Thread(target=maintenance_loop, daemon=True).start()

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=60)
client.loop_forever()
