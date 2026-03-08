MQTT_BROKER   = "phytopi.local"
MQTT_PORT     = 1883
MQTT_TOPIC    = "instarot/+/state"

DB_PATH       = "/home/maule/applications/instarot-dashboard/data/instarot.db"

RETENTION = {
    "raw":   60 * 60 * 24 * 7, #Store for a week - so that user can pull session data for debugging/viewing
    "1min":  60 * 60 * 24 * 30, #Store 1-min averages for a month
    "10min": 60 * 60 * 24 * 182, #Store 10-min averages for ~1/2 year
    "1hr":   60 * 60 * 24 * 365, #Store 1-hour averages for a year
}

WRITE_BUFFER_INTERVAL = 10
MAX_CHART_POINTS      = 500