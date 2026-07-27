import sqlite3
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: reset_admin_password.py <db_path> <username> <password>")
        return 2

    db_path = Path(sys.argv[1])
    username = sys.argv[2]
    password = sys.argv[3]

    db_path.parent.mkdir(parents=True, exist_ok=True)

    password_hash = generate_password_hash(password)
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER NOT NULL,
                username VARCHAR(80) NOT NULL,
                password_hash VARCHAR(120) NOT NULL,
                role VARCHAR(20),
                status VARCHAR(20),
                created_at DATETIME,
                login_failed_count INTEGER,
                locked_until DATETIME,
                last_login_at DATETIME,
                last_login_ip VARCHAR(50),
                PRIMARY KEY (id),
                UNIQUE (username)
            )
            """
        )
        row = conn.execute("SELECT id FROM user WHERE username = ?", (username,)).fetchone()
        if row:
            conn.execute(
                """
                UPDATE user
                   SET password_hash = ?,
                       role = 'admin',
                       status = 'normal',
                       login_failed_count = 0,
                       locked_until = NULL,
                       must_change_password = 0
                 WHERE username = ?
                """,
                (password_hash, username),
            )
        else:
            conn.execute(
                """
                INSERT INTO user
                    (username, password_hash, role, status, created_at, login_failed_count, locked_until)
                VALUES
                    (?, ?, 'admin', 'normal', datetime('now', 'localtime'), 0, NULL)
                """,
                (username, password_hash),
            )
        conn.commit()
    finally:
        conn.close()

    print(f"Admin account ready: {username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
