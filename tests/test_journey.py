import re
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from app import create_app
from importer import import_csvs

ADMIN = "imran.doyle@brightpath.example"
INSTRUCTOR = "priya.varma@brightpath.example"


class JourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.database = str(Path(cls.directory.name) / "lms.db")
        import_csvs(Path(__file__).parents[1] / "data", cls.database)
        cls.app = create_app({"TESTING": True, "DATABASE": cls.database})

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def login(self, username, password="password"):
        client = self.app.test_client()
        client.post("/sign-in", data={"username": username, "password": password})
        return client

    def test_wrong_role_and_anonymous_get_403(self):
        self.assertEqual(self.app.test_client().get("/learner").status_code, 403)
        self.assertEqual(self.login(INSTRUCTOR).get("/administrator").status_code, 403)
        self.assertEqual(self.login("arjun.bhatti.733@example.com").get("/instructor").status_code, 403)

    def test_reports_open_quickly(self):
        admin = self.login(ADMIN)
        start = time.time()
        self.assertEqual(admin.get("/administrator/report").status_code, 200)
        self.assertLess(time.time() - start, 2)
        instructor = self.login(INSTRUCTOR)
        start = time.time()
        home = instructor.get("/instructor").get_data(as_text=True)
        cohort = re.search(r"/instructor/cohorts/([^/]+)/results", home).group(1)
        self.assertEqual(instructor.get(f"/instructor/cohorts/{cohort}/results").status_code, 200)
        self.assertLess(time.time() - start, 2)

    def test_full_journey(self):
        admin = self.login(ADMIN)
        r = admin.post("/administrator/learners", data={
            "full_name": "Zed Tester", "email": "zed@example.com", "password": "secret1",
            "client_id": "CL01", "department": "QA"})
        self.assertIn(r.status_code, (200, 302))
        learner = self.login("zed@example.com", "secret1")
        self.assertEqual(learner.get("/learner").status_code, 200)

        teacher = self.login(INSTRUCTOR)
        r = teacher.post("/instructor/courses/new", data={
            "title": "Journey Course", "cohort": "J1", "starts_on": "2026-01-01"})
        self.assertEqual(r.status_code, 302)
        course = r.headers["Location"].rsplit("/", 1)[1]
        teacher.post(f"/instructor/courses/{course}/assessments", data={"type": "Quiz", "title": "Q1"})
        con = sqlite3.connect(self.database)
        aid = con.execute("SELECT max(assessment_id) FROM assessments").fetchone()[0]
        con.close()
        teacher.post(f"/instructor/assessments/{aid}/questions", data={
            "prompt": "2+2?", "choice": ["3", "4", "5", ""], "correct": "1"})

        cohort_id = course
        enrol_page = learner.get("/learner").get_data(as_text=True)
        self.assertNotIn("Journey Course", enrol_page)  # draft is hidden
        teacher.post(f"/instructor/courses/{course}/publish")
        enrol_page = learner.get("/learner").get_data(as_text=True)
        self.assertIn("Journey Course", enrol_page)
        learner.post(f"/learner/enrol/{cohort_id}")
        page = learner.get(f"/learner/assessments/{aid}").get_data(as_text=True)
        qid = re.search(r'name="q(\d+)"', page).group(1)
        learner.post(f"/learner/assessments/{aid}", data={f"q{qid}": "1"})
        learner.post(f"/learner/assessments/{aid}", data={f"q{qid}": "0"})
        con = sqlite3.connect(self.database)
        scores = [s for (s,) in con.execute(
            "SELECT score FROM attempts WHERE assessment_id=? ORDER BY attempt_id", (aid,))]
        con.close()
        self.assertEqual(scores, [100, 0])  # both attempts kept
        home = learner.get("/learner").get_data(as_text=True)
        self.assertRegex(home, r"(?s)Journey Course.*?<td>100\.0%</td>")
        results = teacher.get(f"/instructor/cohorts/{course}/results").get_data(as_text=True)
        self.assertIn("Zed Tester", results)


if __name__ == "__main__":
    unittest.main()
