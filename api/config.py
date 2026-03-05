MQTT_BROKER   = "phytopi.local"
MQTT_PORT     = 1883
MQTT_TOPIC    = "instarot/+/state"

DB_PATH       = "/home/maule/applications/instarot-dashboard/data/instarot.db"

RETENTION = {
    "raw":   60 * 60 * 24,
    "1min":  60 * 60 * 24 * 7,
    "10min": 60 * 60 * 24 * 30,
    "1hr":   60 * 60 * 24 * 365,
}

WRITE_BUFFER_INTERVAL = 10
MAX_CHART_POINTS      = 500
