import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY, name TEXT, industry TEXT, email_domain TEXT,
    contract_start TEXT, contract_end TEXT, seats INTEGER);
CREATE TABLE IF NOT EXISTS staff (
    staff_id TEXT PRIMARY KEY, full_name TEXT, email TEXT UNIQUE COLLATE NOCASE NOT NULL,
    role TEXT NOT NULL, client_id TEXT, specialism TEXT, joined_on TEXT, left_on TEXT,
    password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS courses (
    course_id TEXT PRIMARY KEY, title TEXT, category TEXT, description TEXT, cohort TEXT,
    starts_on TEXT, ends_on TEXT, length_days INTEGER, status TEXT NOT NULL DEFAULT 'published');
CREATE TABLE IF NOT EXISTS course_staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT, course_id TEXT NOT NULL, staff_id TEXT NOT NULL,
    role TEXT, assigned_on TEXT NOT NULL, unassigned_on TEXT,
    UNIQUE (course_id, staff_id, assigned_on));
CREATE TABLE IF NOT EXISTS assessments (
    assessment_id INTEGER PRIMARY KEY, course_id TEXT NOT NULL, type TEXT, title TEXT,
    due_on TEXT, weight_pct REAL, author_id TEXT, status TEXT, published_on TEXT);
CREATE TABLE IF NOT EXISTS learners (
    learner_id INTEGER PRIMARY KEY, full_name TEXT, email TEXT UNIQUE COLLATE NOCASE NOT NULL,
    client_id TEXT, department TEXT, account_created_on TEXT, created_by TEXT,
    account_status TEXT, password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enrolments (
    enrolment_id TEXT PRIMARY KEY, learner_id INTEGER NOT NULL, course_id TEXT NOT NULL,
    enrolled_on TEXT, withdrawn_on TEXT, outcome TEXT, previous_attempts INTEGER,
    activity_clicks INTEGER, enrolled_by TEXT);
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY, assessment_id INTEGER NOT NULL, learner_id INTEGER NOT NULL,
    course_id TEXT, submitted_on TEXT, score REAL, graded_by TEXT, submission TEXT);
CREATE TABLE IF NOT EXISTS pages (
    page_id INTEGER PRIMARY KEY AUTOINCREMENT, course_id TEXT NOT NULL, title TEXT NOT NULL,
    body TEXT);
CREATE TABLE IF NOT EXISTS attachments (
    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT, page_id INTEGER NOT NULL,
    filename TEXT NOT NULL, mimetype TEXT NOT NULL, data BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id INTEGER NOT NULL,
    prompt TEXT NOT NULL, choices TEXT NOT NULL, correct INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS i_att_course ON attempts (course_id, learner_id);
CREATE INDEX IF NOT EXISTS i_att_assess ON attempts (assessment_id);
CREATE INDEX IF NOT EXISTS i_att_learner ON attempts (learner_id);
CREATE INDEX IF NOT EXISTS i_enr_learner ON enrolments (learner_id);
CREATE INDEX IF NOT EXISTS i_enr_course ON enrolments (course_id);
CREATE INDEX IF NOT EXISTS i_learner_client ON learners (client_id, department);
CREATE INDEX IF NOT EXISTS i_ass_course ON assessments (course_id);
CREATE INDEX IF NOT EXISTS i_cs_staff ON course_staff (staff_id);
"""


def connect(path):
    database = sqlite3.connect(path)
    database.row_factory = sqlite3.Row
    database.executescript(SCHEMA)
    return database
