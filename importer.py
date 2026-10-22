import csv
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

import db

# file -> (table, natural key columns, foreign keys that must resolve)
TABLES = {
    "clients.csv": ("clients", ("client_id",), {}),
    "staff.csv": ("staff", ("staff_id",), {}),
    "courses.csv": ("courses", ("course_id",), {}),
    "course_staff.csv": (
        "course_staff",
        ("course_id", "staff_id", "assigned_on"),
        {"course_id": "courses", "staff_id": "staff"},
    ),
    "assessments.csv": ("assessments", ("assessment_id",), {"course_id": "courses"}),
    "learners.csv": ("learners", ("learner_id",), {"client_id": "clients"}),
    "enrolments.csv": (
        "enrolments",
        ("enrolment_id",),
        {"learner_id": "learners", "course_id": "courses"},
    ),
    "attempts.csv": (
        "attempts",
        ("attempt_id",),
        {"assessment_id": "assessments", "learner_id": "learners"},
    ),
}
PASSWORD_TABLES = ("staff", "learners")


def import_csvs(source, database_path):
    initial_hash = generate_password_hash("password")
    accepted = skipped = 0
    rejected = []
    database = db.connect(database_path)
    ids = {}
    with database:
        for filename, (table, key, foreign_keys) in TABLES.items():
            existing = {
                tuple(str(v) for v in row)
                for row in database.execute(f"SELECT {','.join(key)} FROM {table}")
            }
            ids[table] = {k[0] for k in existing} if len(key) == 1 else set()
            with (Path(source) / filename).open(newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                columns = reader.fieldnames + (["password"] if table in PASSWORD_TABLES else [])
                sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' * len(columns))})"
                for line, row in enumerate(reader, start=2):
                    row = {k: (v.strip() or None) if v else None for k, v in row.items()}
                    if any(row[k] is None for k in key):
                        rejected.append({"file": filename, "line": line, "reason": "missing source ID"})
                        continue
                    missing = next(
                        (c for c, parent in foreign_keys.items() if row[c] is not None and row[c] not in ids[parent]),
                        None,
                    )
                    if missing:
                        rejected.append({
                            "file": filename, "line": line,
                            "reason": f"{missing} {row[missing]!r} does not exist",
                        })
                        continue
                    if tuple(row[k] for k in key) in existing:
                        skipped += 1
                        continue
                    if table in PASSWORD_TABLES:
                        row["password"] = initial_hash
                    try:
                        database.execute(sql, [row[c] for c in columns])
                    except Exception as error:
                        rejected.append({"file": filename, "line": line, "reason": str(error)})
                        continue
                    accepted += 1
                    existing.add(tuple(row[k] for k in key))
                    if len(key) == 1:
                        ids[table].add(row[key[0]])
    database.close()
    return {"accepted": accepted, "skipped": skipped, "rejected": rejected}


if __name__ == "__main__":
    result = import_csvs(sys.argv[1], sys.argv[2])
    print(f"accepted: {result['accepted']}")
    print(f"already loaded: {result['skipped']}")
    print(f"rejected: {len(result['rejected'])}")
    for r in result["rejected"]:
        print(f"{r['file']} line {r['line']}: {r['reason']}")
