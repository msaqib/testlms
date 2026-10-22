import csv
import json
import sqlite3
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

FILES = (
    "clients.csv",
    "staff.csv",
    "courses.csv",
    "course_staff.csv",
    "assessments.csv",
    "learners.csv",
    "enrolments.csv",
    "attempts.csv",
)
INITIAL_PASSWORD_HASH = generate_password_hash("password")


def import_csvs(source, database):
    accepted = 0
    rejected = []
    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS imported_records (
            source_file TEXT NOT NULL,
            source_id TEXT NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY (source_file, source_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL,
            active INTEGER NOT NULL
        )
        """
    )
    with connection:
        for filename in FILES:
            with (Path(source) / filename).open(newline="", encoding="utf-8") as file:
                for row in csv.DictReader(file):
                    source_id = row[next(iter(row))]
                    if not source_id:
                        rejected.append({"file": filename, "reason": "missing source ID"})
                        continue
                    cursor = connection.execute(
                        """
                        INSERT OR IGNORE INTO imported_records (source_file, source_id, data)
                        VALUES (?, ?, ?)
                        """,
                        (filename, source_id, json.dumps(row, sort_keys=True)),
                    )
                    accepted += cursor.rowcount
                    if cursor.rowcount and filename == "staff.csv":
                        connection.execute(
                            """
                            INSERT OR IGNORE INTO users (username, password, role, active)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                row["email"],
                                INITIAL_PASSWORD_HASH,
                                row["role"],
                                not row["left_on"],
                            ),
                        )
                    if cursor.rowcount and filename == "learners.csv":
                        connection.execute(
                            """
                            INSERT OR IGNORE INTO users (username, password, role, active)
                            VALUES (?, ?, 'learner', ?)
                            """,
                            (
                                row["email"],
                                INITIAL_PASSWORD_HASH,
                                row["account_status"] == "active",
                            ),
                        )
    connection.close()
    return {"accepted": accepted, "rejected": rejected}


if __name__ == "__main__":
    result = import_csvs(sys.argv[1], sys.argv[2])
    print(f"accepted: {result['accepted']}")
    print(f"rejected: {len(result['rejected'])}")
    for rejection in result["rejected"]:
        print(f"{rejection['file']}: {rejection['reason']}")
