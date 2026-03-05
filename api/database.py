import sqlite3, time, logging
from contextlib import contextmanager
import config

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device      TEXT    NOT NULL,
    tc1_temp    REAL,
    tc2_temp    REAL,
    setpoint    REAL,
    output      REAL,
    kp          REAL,
    ki          REAL,
    kd          REAL,
    resolution  TEXT    NOT NULL DEFAULT 'raw',
    ts          INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_device_ts  ON readings (device, ts);
CREATE INDEX IF NOT EXISTS idx_resolution ON readings (resolution, ts);

CREATE TABLE IF NOT EXISTS devices (
    hostname    TEXT PRIMARY KEY,
    last_seen   INTEGER,
    last_temp   REAL
);
"""

@contextmanager
def get_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)

def insert_batch(rows):
    with get_db() as conn:
        conn.executemany("""
            INSERT INTO readings (device, tc1_temp, tc2_temp, setpoint, output, kp, ki, kd, ts)
            VALUES (:device, :tc1_temp, :tc2_temp, :setpoint, :output, :kp, :ki, :kd, :ts)
        """, rows)

def upsert_device(hostname, ts, temp):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO devices (hostname, last_seen, last_temp)
            VALUES (?, ?, ?)
            ON CONFLICT(hostname) DO UPDATE SET
                last_seen = excluded.last_seen,
                last_temp = excluded.last_temp
        """, (hostname, ts, temp))

def get_devices():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM devices").fetchall()]

def get_history(device, start_ts, end_ts, resolution="raw"):
    with get_db() as conn:
        count = conn.execute("""
            SELECT COUNT(*) FROM readings
            WHERE device=? AND resolution=? AND ts BETWEEN ? AND ?
        """, (device, resolution, start_ts, end_ts)).fetchone()[0]

        if count == 0:
            return []

        step = max(1, count // config.MAX_CHART_POINTS)

        rows = conn.execute("""
            SELECT ts, tc1_temp, tc2_temp, setpoint, output, kp, ki, kd
            FROM (
                SELECT *, ROW_NUMBER() OVER (ORDER BY ts ASC) rn
                FROM readings
                WHERE device=? AND resolution=? AND ts BETWEEN ? AND ?
            )
            WHERE rn % ? = 0
            ORDER BY ts ASC
        """, (device, resolution, start_ts, end_ts, step)).fetchall()

        return [dict(r) for r in rows]

def get_latest(device):
    with get_db() as conn:
        row = conn.execute("""
            SELECT * FROM readings WHERE device=?
            ORDER BY ts DESC LIMIT 1
        """, (device,)).fetchone()
        return dict(row) if row else None

def downsample_and_cull():
    now = int(time.time())
    with get_db() as conn:
        _downsample(conn, src="raw",   dst="1min",  bucket=60,   max_age=config.RETENTION["raw"])
        _downsample(conn, src="1min",  dst="10min", bucket=600,  max_age=config.RETENTION["1min"])
        _downsample(conn, src="10min", dst="1hr",   bucket=3600, max_age=config.RETENTION["10min"])

        for res, max_age in config.RETENTION.items():
            deleted = conn.execute(
                "DELETE FROM readings WHERE resolution=? AND ts < ?",
                (res, now - max_age)
            ).rowcount
            if deleted:
                log.info(f"Culled {deleted} rows from tier '{res}'")

def _downsample(conn, src, dst, bucket, max_age):
    now = int(time.time())
    cutoff = now - max_age
    conn.execute(f"""
        INSERT OR IGNORE INTO readings (device, tc1_temp, tc2_temp, setpoint, output, kp, ki, kd, resolution, ts)
        SELECT
            device,
            AVG(tc1_temp), AVG(tc2_temp), AVG(setpoint), AVG(output), AVG(kp), AVG(ki), AVG(kd),
            '{dst}'
            (ts / {bucket}) * {bucket}
        FROM readings
        WHERE resolution='{src}' AND ts < ?
        GROUP BY device, (ts / {bucket})
        HAVING COUNT(*) > 1
    """, (cutoff,))
