# Training platform

Start from a fresh clone (Python 3.12):

    pip install -r requirements.txt && python app.py

Open http://127.0.0.1:5000. On first start the CSVs in `data/` are imported into `lms.db` (about 10 seconds); later starts reuse it. Set `HOST`, `PORT` or `SECRET_KEY` to override defaults.

Every imported account has the password `password`. Demo accounts:

| Role | Username |
|---|---|
| Administrator | imran.doyle@brightpath.example |
| Instructor | priya.varma@brightpath.example |
| Learner | arjun.bhatti.733@example.com |

Tests: `python -m unittest tests.test_auth tests.test_import tests.test_journey`

Known limits: no CSRF tokens (SameSite=Lax cookie only); uploads limited to png/jpg/gif/pdf; every imported account shares one initial password.
