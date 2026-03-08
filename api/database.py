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

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    device      TEXT    NOT NULL,
    started_at  INTEGER NOT NULL,
    ended_at    INTEGER,
    notes       TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sessions_device ON sessions (device, started_at);

CREATE TABLE IF NOT EXISTS programs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT    DEFAULT '',
    steps       TEXT    NOT NULL DEFAULT '[]',
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS program_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id   INTEGER NOT NULL REFERENCES programs(id),
    session_id   INTEGER REFERENCES sessions(id),
    device       TEXT    NOT NULL,
    started_at   INTEGER NOT NULL,
    ended_at     INTEGER,
    status       TEXT    NOT NULL DEFAULT 'running',
    current_step INTEGER NOT NULL DEFAULT 0
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

# ── Sessions ─────────────────────────────────────────────────────────────────

def create_session(name, device):
    now = int(time.time())
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (name, device, started_at) VALUES (?, ?, ?)",
            (name, device, now)
        )
        return cur.lastrowid

def get_sessions(device=None):
    with get_db() as conn:
        if device:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE device=? ORDER BY started_at DESC", (device,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

def get_session(session_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None

def update_session(session_id, ended_at=None, notes=None):
    with get_db() as conn:
        if ended_at is not None:
            conn.execute("UPDATE sessions SET ended_at=? WHERE id=?", (ended_at, session_id))
        if notes is not None:
            conn.execute("UPDATE sessions SET notes=? WHERE id=?", (notes, session_id))

def delete_session(session_id):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))

# ── Programs ──────────────────────────────────────────────────────────────────

def create_program(name, description, steps):
    import json as _json
    now = int(time.time())
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO programs (name, description, steps, created_at) VALUES (?, ?, ?, ?)",
            (name, description, _json.dumps(steps), now)
        )
        return cur.lastrowid

def get_programs():
    import json as _json
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM programs ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["steps"] = _json.loads(d["steps"])
            result.append(d)
        return result

def get_program(program_id):
    import json as _json
    with get_db() as conn:
        row = conn.execute("SELECT * FROM programs WHERE id=?", (program_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["steps"] = _json.loads(d["steps"])
        return d

def update_program(program_id, name, description, steps):
    import json as _json
    with get_db() as conn:
        conn.execute(
            "UPDATE programs SET name=?, description=?, steps=? WHERE id=?",
            (name, description, _json.dumps(steps), program_id)
        )

def delete_program(program_id):
    with get_db() as conn:
        conn.execute("DELETE FROM programs WHERE id=?", (program_id,))

# ── Program Runs ──────────────────────────────────────────────────────────────

def create_program_run(program_id, session_id, device):
    now = int(time.time())
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO program_runs (program_id, session_id, device, started_at) VALUES (?, ?, ?, ?)",
            (program_id, session_id, device, now)
        )
        return cur.lastrowid

def get_program_run(run_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM program_runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

def get_program_runs(program_id=None):
    with get_db() as conn:
        if program_id:
            rows = conn.execute(
                "SELECT * FROM program_runs WHERE program_id=? ORDER BY started_at DESC",
                (program_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM program_runs ORDER BY started_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

def update_program_run(run_id, status=None, current_step=None, ended_at=None):
    with get_db() as conn:
        if status is not None:
            conn.execute("UPDATE program_runs SET status=? WHERE id=?", (status, run_id))
        if current_step is not None:
            conn.execute("UPDATE program_runs SET current_step=? WHERE id=?", (current_step, run_id))
        if ended_at is not None:
            conn.execute("UPDATE program_runs SET ended_at=? WHERE id=?", (ended_at, run_id))

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
