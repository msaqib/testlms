import tempfile
import unittest
from pathlib import Path

from app import create_app
from importer import import_csvs


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.database = str(Path(cls.directory.name) / "lms.db")
        import_csvs(Path(__file__).parents[3] / "data", cls.database)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.app = create_app({"TESTING": True, "DATABASE": self.database})
        self.client = self.app.test_client()

    def test_sign_in_page_has_username_and_password_fields(self):
        response = self.client.get("/sign-in")

        self.assertEqual(response.status_code, 200)
        self.assertIn('name="username"', response.get_data(as_text=True))
        self.assertIn('name="password"', response.get_data(as_text=True))

    def test_deactivated_learner_cannot_sign_in(self):
        response = self.client.post(
            "/sign-in",
            data={"username": "rafiq.costa.261@example.com", "password": "password"},
        )

        self.assertEqual(response.status_code, 403)

    def test_administrator_sign_in_lands_on_administrator_home(self):
        response = self.client.post(
            "/sign-in",
            data={"username": "imran.doyle@brightpath.example", "password": "password"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "Administrator home")

    def test_anonymous_user_cannot_open_administrator_home(self):
        response = self.client.get("/administrator")

        self.assertEqual(response.status_code, 403)

    def test_instructor_sign_in_lands_on_instructor_home(self):
        response = self.client.post(
            "/sign-in",
            data={"username": "priya.varma@brightpath.example", "password": "password"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "Instructor home")

    def test_learner_sign_in_lands_on_learner_home(self):
        response = self.client.post(
            "/sign-in",
            data={"username": "arjun.bhatti.733@example.com", "password": "password"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "Learner home")


if __name__ == "__main__":
    unittest.main()
