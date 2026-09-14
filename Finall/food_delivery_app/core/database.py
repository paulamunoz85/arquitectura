import sqlite3
import os
import threading
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "marketplace.db")


class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = DB_PATH):
        if self._initialized:
            return
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._lock_db = threading.Lock()
        self._create_schema()
        self._seed_admin()
        self._initialized = True

    def execute(self, sql: str, params: tuple = ()):
        with self._lock_db:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()):
        with self._lock_db:
            cur = self.conn.execute(sql, params)
            return cur.fetchall()

    def query_one(self, sql: str, params: tuple = ()):
        with self._lock_db:
            cur = self.conn.execute(sql, params)
            return cur.fetchone()

    def transaction(self, statements):
        with self._lock_db:
            try:
                cur = self.conn.cursor()
                last = None
                for sql, params in statements:
                    cur.execute(sql, params)
                    last = cur.lastrowid
                self.conn.commit()
                return last
            except Exception:
                self.conn.rollback()
                raise

    def _create_schema(self):
        c = self.conn
        c.executescript(              
        )
        self.conn.commit()

    def _seed_admin(self):
        row = self.query_one("SELECT id FROM usuarios WHERE rol = 'ADMINISTRADOR' LIMIT 1")
        if row is None:
            from core.security import hash_password
            self.execute(
                "INSERT INTO usuarios (nombre, correo_electronico, contrasena_hash, rol, esta_activo, fecha_creacion) "
                "VALUES (?, ?, ?, 'ADMINISTRADOR', 1, ?)",
                ("Administrador SaborLocal", "admin@marketplace.com", hash_password("admin123"),
                 datetime.now().isoformat()),
            )

    def log_evento(self, pedido_id, actor_id, evento, detalle=""):
        self.execute(
            "INSERT INTO historial_estados (pedido_id, actor_id, evento, detalle, fecha) VALUES (?,?,?,?,?)",
            (pedido_id, actor_id, evento, detalle, datetime.now().isoformat()),
        )


def get_db() -> Database:
    """Punto de acceso global al Singleton de base de datos."""
    return Database()
