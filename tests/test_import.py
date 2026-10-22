import subprocess
import sys
import tempfile
import unittest
import sqlite3
from pathlib import Path

from app import create_app
from importer import import_csvs


class ImportTests(unittest.TestCase):
    def test_imported_administrator_can_sign_in_with_the_initial_password(self):
        source = Path(__file__).parents[1] / "data"
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "lms.db"
            import_csvs(source, database)
            client = create_app({"TESTING": True, "DATABASE": str(database)}).test_client()
            response = client.post(
                "/sign-in",
                data={"username": "imran.doyle@brightpath.example", "password": "password"},
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Administrator home", response.get_data(as_text=True))

    def test_command_reports_import_counts(self):
        source = Path(__file__).parents[1] / "data"
        script = Path(__file__).parents[1] / "importer.py"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, script, source, Path(directory) / "lms.db"],
                capture_output=True,
                check=True,
                text=True,
            )

        self.assertIn("accepted:", result.stdout)
        self.assertIn("rejected:", result.stdout)

    def test_importing_source_data_twice_does_not_duplicate_users(self):
        source = Path(__file__).parents[1] / "data"
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "lms.db"

            first = import_csvs(source, database)
            second = import_csvs(source, database)
            connection = sqlite3.connect(database)
            try:
                user = connection.execute(
                    "SELECT count(*) FROM staff WHERE email = ?",
                    ("imran.doyle@brightpath.example",),
                ).fetchone()
            finally:
                connection.close()

        self.assertGreater(first["accepted"], 0)
        self.assertEqual(first["rejected"], [])
        self.assertEqual(second["accepted"], 0)
        self.assertEqual(second["rejected"], [])
        self.assertEqual(user, (1,))


if __name__ == "__main__":
    unittest.main()
