import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
import time
import socket


# ---------- Utilities ----------
def wait_for_port(host: str, port: int, timeout: int = 60, interval: float = 1.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except Exception:
            time.sleep(interval)
    return False

def make_pool(host, port, dbname, user, password):
    dsn = {"host": host, "port": port, "dbname": dbname, "user": user, "password": password}
    return SimpleConnectionPool(1, 10, **dsn)

def db_fetchone(pool, sql, params=()):
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        pool.putconn(conn)

def db_fetchall(pool, sql, params=()):
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        pool.putconn(conn)

def db_execute(pool, sql, params=(), commit=True):
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if commit:
                conn.commit()
    finally:
        pool.putconn(conn)