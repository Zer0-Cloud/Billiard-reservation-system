from pathlib import Path
import sqlite3

from werkzeug.security import generate_password_hash


DATABASE = "pool_bookings.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SAMPLE_TABLES = [
    ("Table 1", "American 9-ball", 18.00, "available"),
    ("Table 2", "American 9-ball", 18.00, "available"),
    ("Table 3", "American 9-ball", 18.00, "available"),
    ("Table 4", "American 9-ball", 18.00, "available"),
    ("Table 5", "American 9-ball", 18.00, "available"),
    ("Table 6", "American 9-ball", 18.00, "available"),
    ("Chinese 8-ball Table 1", "Regular Chinese 8-ball", 18.00, "available"),
    ("Chinese 8-ball Table 2", "Regular Chinese 8-ball", 18.00, "available"),
    ("Premium Chinese 8-ball Table 1", "Premium Chinese 8-ball", 22.00, "available"),
    ("Premium Chinese 8-ball Table 2", "Premium Chinese 8-ball", 22.00, "available"),
    ("Premium Chinese 8-ball Table 3", "Premium Chinese 8-ball", 22.00, "available"),
    ("Premium Chinese 8-ball Table 4", "Premium Chinese 8-ball", 22.00, "available"),
    ("Joy Gold Leg Chinese 8-ball", "Joy Gold Leg Chinese 8-ball", 24.00, "available"),
]


def get_db_connection(database_path=DATABASE):
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(database_path=DATABASE):
    conn = get_db_connection(database_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    booking_columns = [
        row["name"] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()
    ]
    user_columns = [
        row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    ]

    if "status" not in booking_columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN status TEXT NOT NULL DEFAULT 'Pending'")
    if "user_id" not in booking_columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN user_id INTEGER")
    if "phone" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")

    conn.execute("DROP INDEX IF EXISTS idx_unique_booking_slot")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_booking_slot
        ON bookings (table_id, booking_date, start_time)
        WHERE status != 'Cancelled'
        """
    )

    desired_table_names = [table[0] for table in SAMPLE_TABLES]
    for name, table_type, hourly_rate, status in SAMPLE_TABLES:
        existing_table = conn.execute(
            "SELECT id FROM tables WHERE name = ?",
            (name,),
        ).fetchone()

        if existing_table:
            conn.execute(
                """
                UPDATE tables
                SET type = ?, hourly_rate = ?, status = ?
                WHERE id = ?
                """,
                (table_type, hourly_rate, status, existing_table["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO tables (name, type, hourly_rate, status)
                VALUES (?, ?, ?, ?)
                """,
                (name, table_type, hourly_rate, status),
            )

    placeholders = ",".join("?" for _ in desired_table_names)
    conn.execute(
        f"UPDATE tables SET status = 'retired' WHERE name NOT IN ({placeholders})",
        desired_table_names,
    )

    admin_email = "admin@qclubbilliard.com"
    existing_admin = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (admin_email,),
    ).fetchone()
    if existing_admin is None:
        conn.execute(
            """
            INSERT INTO users (full_name, email, phone, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                "Q Club Admin",
                admin_email,
                "",
                generate_password_hash("admin123"),
                "admin",
            ),
        )

    conn.commit()
    conn.close()
