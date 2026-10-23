import csv
import io
import os
import re
import secrets
from datetime import date, datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, Response, abort, flash, g, redirect, render_template, request, session,
)
from werkzeug.security import check_password_hash, generate_password_hash

import db
from importer import import_csvs

ROOT = Path(__file__).parent
PER_PAGE = 100
FILE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".pdf": "application/pdf",
}
ATTEMPT_SORT = {"date": "a.submitted_on", "score": "a.score"}


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(ROOT / "lms.db"),
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(16),
        SESSION_COOKIE_SAMESITE="Lax",  # shortcut: no CSRF tokens, SameSite cookie only; add tokens before public exposure
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )
    if config:
        app.config.update(config)

    def conn():
        if "db" not in g:
            g.db = db.connect(app.config["DATABASE"])
        return g.db

    @app.teardown_appcontext
    def close(_):
        database = g.pop("db", None)
        if database:
            database.close()

    def rows(sql, *args):
        return conn().execute(sql, args).fetchall()

    def row(sql, *args):
        return conn().execute(sql, args).fetchone()

    def run(sql, *args):
        cursor = conn().execute(sql, args)
        conn().commit()
        return cursor

    def next_id(table, column, prefix="", width=0):
        n = row(
            f"SELECT MAX(CAST(substr({column}, {len(prefix) + 1}) AS INTEGER)) FROM {table}"
        )[0] or 0
        return f"{prefix}{n + 1:0{width}d}"

    def today():
        return date.today().isoformat()

    # ---- identity -------------------------------------------------------
    @app.before_request
    def load_user():
        g.user = None
        role, uid = session.get("role"), session.get("uid")
        if not role:
            return
        if role == "learner":
            u = row("SELECT * FROM learners WHERE learner_id = ?", uid)
            ok = u and u["account_status"] == "active"
        else:
            u = row("SELECT * FROM staff WHERE staff_id = ?", uid)
            ok = u and not (u["left_on"] and u["left_on"] <= today())
        if ok:
            g.user = {"role": role, "id": str(uid), "name": u["full_name"],
                      "client_id": u["client_id"]}
        else:
            session.clear()

    def role_required(role):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                if not g.user or g.user["role"] != role:
                    abort(403)
                return view(*args, **kwargs)
            return wrapped
        return decorator

    @app.get("/")
    def index():
        return redirect(f"/{g.user['role']}" if g.user else "/sign-in")

    @app.get("/sign-in")
    def sign_in_page():
        return render_template("sign_in.html")

    @app.post("/sign-in")
    def sign_in():
        email = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = row("SELECT staff_id AS id, role, password, left_on, NULL AS status "
                   "FROM staff WHERE email = ?", email)
        if user is None:
            user = row("SELECT learner_id AS id, 'learner' AS role, password, NULL AS left_on, "
                       "account_status AS status FROM learners WHERE email = ?", email)
        left = user and user["left_on"] and user["left_on"] <= today()
        inactive = user and user["role"] == "learner" and user["status"] != "active"
        if not user or left or inactive or not check_password_hash(user["password"], password):
            return render_template("sign_in.html", error="Sign-in failed."), 403
        session.clear()
        session["role"], session["uid"] = user["role"], user["id"]
        return redirect(f"/{user['role']}")

    @app.post("/sign-out")
    def sign_out():
        session.clear()
        return redirect("/sign-in")

    # ---- helpers --------------------------------------------------------
    def sorted_attempts(where, args):
        key = ATTEMPT_SORT.get(request.args.get("sort"), "a.submitted_on")
        direction = "ASC" if request.args.get("dir") == "asc" else "DESC"
        return rows(
            f"""SELECT a.attempt_id, a.submitted_on, a.score, s.title, s.type, c.title AS course,
                       c.cohort, g.full_name AS grader
                FROM attempts a JOIN assessments s ON s.assessment_id = a.assessment_id
                LEFT JOIN courses c ON c.course_id = a.course_id
                LEFT JOIN staff g ON g.staff_id = a.graded_by
                WHERE {where} ORDER BY {key} {direction}, a.attempt_id LIMIT 500""",
            *args,
        )

    @app.context_processor
    def helpers():
        def sort_link(label, key):
            direction = "desc" if request.args.get("sort") == key \
                and request.args.get("dir") == "asc" else "asc"
            args = {**request.args, "sort": key, "dir": direction}
            query = "&".join(f"{k}={v}" for k, v in args.items())
            return f'<a href="?{query}">{label}</a>'
        return {"sort_link": sort_link, "user": g.get("user"), "today": today()}

    def csv_response(name, header, data):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(header)
        writer.writerows(data)
        return Response(
            out.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={name}"},
        )

    def staff_name(staff_id):
        if staff_id in (None, "self", "self-signup"):
            return "the learner (self-enrolled)"
        r = row("SELECT full_name FROM staff WHERE staff_id = ?", staff_id)
        return r["full_name"] if r else staff_id

    app.jinja_env.globals["staff_name"] = staff_name

    def is_assigned(course_id):
        return row(
            "SELECT 1 FROM course_staff WHERE course_id = ? AND staff_id = ? "
            "AND (unassigned_on IS NULL OR unassigned_on > ?)",
            course_id, g.user["id"], today(),
        ) is not None

    def own_course(course_id):
        if not is_assigned(course_id):
            abort(403)
        return row("SELECT * FROM courses WHERE course_id = ?", course_id)

    def learner_in_scope(learner_id):
        learner = row("SELECT * FROM learners WHERE learner_id = ?", learner_id)
        if not learner or (g.user["client_id"] and learner["client_id"] != g.user["client_id"]):
            abort(404)
        return learner

    def enrol(learner_id, course_id, by):
        course = row("SELECT status FROM courses WHERE course_id = ?", course_id)
        if not course or course["status"] != "published":
            flash("That course is not published.")
        elif row("SELECT 1 FROM enrolments WHERE learner_id = ? AND course_id = ? "
                 "AND withdrawn_on IS NULL AND outcome IS NULL", learner_id, course_id):
            flash("Already enrolled in this cohort.")
        else:
            previous = row("SELECT COUNT(*) FROM enrolments WHERE learner_id = ? AND course_id = ?",
                           learner_id, course_id)[0]
            run("INSERT INTO enrolments (enrolment_id, learner_id, course_id, enrolled_on, "
                "previous_attempts, enrolled_by) VALUES (?, ?, ?, ?, ?, ?)",
                next_id("enrolments", "enrolment_id", "E", 6), learner_id, course_id, today(),
                previous, by)
            flash("Enrolled.")

    def withdraw(enrolment_id, learner_id=None):
        e = row("SELECT * FROM enrolments WHERE enrolment_id = ?", enrolment_id)
        if not e or (learner_id and str(e["learner_id"]) != str(learner_id)):
            abort(404)
        if g.user["role"] == "administrator":
            learner_in_scope(e["learner_id"])
        if e["withdrawn_on"] is None:
            run("UPDATE enrolments SET withdrawn_on = ? WHERE enrolment_id = ?", today(), enrolment_id)
            flash("Withdrawal recorded.")
        return e

    # ---- administrator --------------------------------------------------
    @app.get("/administrator")
    @role_required("administrator")
    def administrator_home():
        return render_template("admin_home.html", scoped=g.user["client_id"])

    @app.get("/administrator/learners")
    @role_required("administrator")
    def admin_learners():
        q = request.args.get("q", "").strip()
        page = max(request.args.get("page", 1, type=int), 1)
        where, args = ["1=1"], []
        if g.user["client_id"]:
            where.append("l.client_id = ?")
            args.append(g.user["client_id"])
        if q:
            where.append("(l.full_name LIKE ? OR l.email LIKE ?)")
            args += [f"%{q}%", f"%{q}%"]
        clause = " AND ".join(where)
        total = row(f"SELECT COUNT(*) FROM learners l WHERE {clause}", *args)[0]
        learners = rows(
            f"SELECT l.*, c.name AS client FROM learners l LEFT JOIN clients c "
            f"ON c.client_id = l.client_id WHERE {clause} ORDER BY l.learner_id DESC "
            f"LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}", *args)
        if g.user["client_id"]:
            clients = rows("SELECT client_id, name FROM clients WHERE client_id = ?",
                           g.user["client_id"])
        else:
            clients = rows("SELECT client_id, name FROM clients ORDER BY name")
        return render_template("admin_learners.html", learners=learners, clients=clients, q=q,
                               page=page, pages=(total + PER_PAGE - 1) // PER_PAGE, total=total)

    @app.post("/administrator/learners")
    @role_required("administrator")
    def admin_create_learner():
        f = request.form
        name, email = f.get("full_name", "").strip(), f.get("email", "").strip()
        password, department = f.get("password", ""), f.get("department", "").strip()
        client = g.user["client_id"] or f.get("client_id")
        if not (name and email and password and department and client):
            flash("Name, email, password, client and department are required.")
        elif not row("SELECT 1 FROM clients WHERE client_id = ?", client):
            flash("Unknown client.")
        elif row("SELECT 1 FROM learners WHERE email = ? UNION SELECT 1 FROM staff WHERE email = ?",
                 email, email):
            flash("That email is already in use.")
        else:
            lid = next_id("learners", "learner_id")
            run("INSERT INTO learners (learner_id, full_name, email, client_id, department, "
                "account_created_on, created_by, account_status, password) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)",
                lid, name, email, client, department, today(), g.user["id"],
                generate_password_hash(password))
            flash(f"Created learner {name}.")
            return redirect(f"/administrator/learners/{lid}")
        return redirect("/administrator/learners")

    @app.get("/administrator/learners/<int:learner_id>")
    @role_required("administrator")
    def admin_learner(learner_id):
        learner = learner_in_scope(learner_id)
        enrolments = rows(
            "SELECT e.*, c.title, c.cohort FROM enrolments e JOIN courses c ON c.course_id = e.course_id "
            "WHERE e.learner_id = ? ORDER BY e.enrolled_on DESC", learner_id)
        courses = rows("SELECT course_id, title, cohort FROM courses WHERE status = 'published' "
                       "ORDER BY title, starts_on")
        attempts = sorted_attempts("a.learner_id = ?", (learner_id,))
        return render_template("admin_learner.html", learner=learner, enrolments=enrolments,
                               courses=courses, attempts=attempts)

    @app.post("/administrator/learners/<int:learner_id>/status")
    @role_required("administrator")
    def admin_learner_status(learner_id):
        learner_in_scope(learner_id)
        status = "active" if request.form.get("status") == "active" else "deactivated"
        run("UPDATE learners SET account_status = ? WHERE learner_id = ?", status, learner_id)
        flash(f"Account {status}.")
        return redirect(f"/administrator/learners/{learner_id}")

    @app.post("/administrator/learners/<int:learner_id>/enrol")
    @role_required("administrator")
    def admin_enrol(learner_id):
        learner_in_scope(learner_id)
        enrol(learner_id, request.form.get("course_id"), g.user["id"])
        return redirect(f"/administrator/learners/{learner_id}")

    @app.post("/administrator/enrolments/<enrolment_id>/withdraw")
    @role_required("administrator")
    def admin_withdraw(enrolment_id):
        e = withdraw(enrolment_id)
        return redirect(f"/administrator/learners/{e['learner_id']}")

    @app.get("/administrator/staffing")
    @role_required("administrator")
    def admin_staffing():
        if g.user["client_id"]:
            abort(403)
        courses = rows("SELECT * FROM courses ORDER BY title, starts_on")
        by_course = {}
        for h in rows("SELECT cs.*, s.full_name FROM course_staff cs JOIN staff s "
                      "ON s.staff_id = cs.staff_id ORDER BY cs.assigned_on"):
            by_course.setdefault(h["course_id"], []).append(h)
        instructors = rows("SELECT staff_id, full_name FROM staff WHERE role = 'instructor' "
                           "AND (left_on IS NULL OR left_on > ?) ORDER BY full_name", today())
        return render_template("admin_staffing.html", courses=courses, by_course=by_course,
                               instructors=instructors)

    @app.post("/administrator/assignments")
    @role_required("administrator")
    def admin_assign():
        if g.user["client_id"]:
            abort(403)
        course_id, staff_id = request.form.get("course_id"), request.form.get("staff_id")
        instructor = row("SELECT 1 FROM staff WHERE staff_id = ? AND role = 'instructor' "
                         "AND (left_on IS NULL OR left_on > ?)", staff_id, today())
        if not instructor or not row("SELECT 1 FROM courses WHERE course_id = ?", course_id):
            flash("Choose a current instructor and a cohort.")
        elif row("SELECT 1 FROM course_staff WHERE course_id = ? AND staff_id = ? "
                 "AND (unassigned_on IS NULL OR unassigned_on > ?)", course_id, staff_id, today()):
            flash("Already assigned.")
        else:
            # a new row each time keeps earlier stints in the history
            run("INSERT OR IGNORE INTO course_staff (course_id, staff_id, role, assigned_on) "
                "VALUES (?, ?, 'lead', ?)", course_id, staff_id, today())
            run("UPDATE course_staff SET unassigned_on = NULL WHERE course_id = ? AND staff_id = ? "
                "AND assigned_on = ?", course_id, staff_id, today())
            flash("Instructor assigned.")
        return redirect("/administrator/staffing")

    @app.post("/administrator/assignments/<int:assignment_id>/end")
    @role_required("administrator")
    def admin_unassign(assignment_id):
        if g.user["client_id"]:
            abort(403)
        run("UPDATE course_staff SET unassigned_on = ? WHERE id = ? AND unassigned_on IS NULL",
            today(), assignment_id)
        flash("Instructor taken off the cohort; history kept.")
        return redirect("/administrator/staffing")

    def completion_report():
        scope = " WHERE l.client_id = ?" if g.user["client_id"] else ""
        data = rows(
            f"""SELECT c.name, l.department, COUNT(*) AS enrolments,
                   COALESCE(SUM(e.outcome IN ('Pass','Distinction')), 0) AS completed,
                   COALESCE(SUM(e.outcome = 'Fail'), 0) AS failed,
                   COALESCE(SUM(e.withdrawn_on IS NOT NULL OR e.outcome = 'Withdrawn'), 0) AS withdrawn
                FROM enrolments e JOIN learners l ON l.learner_id = e.learner_id
                LEFT JOIN clients c ON c.client_id = l.client_id{scope}
                GROUP BY c.name, l.department ORDER BY c.name, l.department""",
            *([g.user["client_id"]] if scope else []))
        header = ["Client", "Department", "Enrolments", "Completed", "Failed", "Withdrawn",
                  "Completion %"]
        return header, [
            [r["name"], r["department"], r["enrolments"], r["completed"], r["failed"],
             r["withdrawn"], round(100 * r["completed"] / r["enrolments"], 1)]
            for r in data
        ]

    @app.get("/administrator/report")
    @role_required("administrator")
    def admin_report():
        header, data = completion_report()
        return render_template("admin_report.html", header=header, data=data)

    @app.get("/administrator/report.csv")
    @role_required("administrator")
    def admin_report_csv():
        header, data = completion_report()
        return csv_response("completion-by-client-department.csv", header, data)

    # ---- instructor -----------------------------------------------------
    @app.get("/instructor")
    @role_required("instructor")
    def instructor_home():
        cohorts = rows(
            "SELECT c.* FROM courses c JOIN course_staff cs ON cs.course_id = c.course_id "
            "WHERE cs.staff_id = ? AND (cs.unassigned_on IS NULL OR cs.unassigned_on > ?) "
            "GROUP BY c.course_id ORDER BY c.starts_on DESC", g.user["id"], today())
        return render_template("instructor_home.html", cohorts=cohorts)

    @app.route("/instructor/courses/new", methods=["GET", "POST"])
    @role_required("instructor")
    def instructor_new_course():
        if request.method == "POST":
            f = request.form
            title, cohort = f.get("title", "").strip(), f.get("cohort", "").strip()
            if not (title and cohort and f.get("starts_on")):
                flash("Title, cohort and start date are required.")
                return render_template("course_new.html"), 400
            slug = re.sub(r"[^a-z0-9]+", "-", f"{title} {cohort}".lower()).strip("-")
            if row("SELECT 1 FROM courses WHERE course_id = ?", slug):
                slug = f"{slug}-{secrets.token_hex(2)}"
            run("INSERT INTO courses (course_id, title, category, description, cohort, starts_on, "
                "ends_on, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')", slug, title,
                f.get("category") or None, f.get("description") or None, cohort,
                f.get("starts_on"), f.get("ends_on") or None)
            run("INSERT INTO course_staff (course_id, staff_id, role, assigned_on) "
                "VALUES (?, ?, 'lead', ?)", slug, g.user["id"], today())
            return redirect(f"/instructor/courses/{slug}")
        return render_template("course_new.html")

    def course_content(course_id):
        pages = rows("SELECT * FROM pages WHERE course_id = ? ORDER BY page_id", course_id)
        files = rows("SELECT a.attachment_id, a.page_id, a.filename FROM attachments a "
                     "JOIN pages p ON p.page_id = a.page_id WHERE p.course_id = ?", course_id)
        return pages, files

    @app.get("/instructor/courses/<course_id>")
    @role_required("instructor")
    def instructor_course(course_id):
        course = own_course(course_id)
        pages, files = course_content(course_id)
        assessments = rows(
            "SELECT s.*, (SELECT COUNT(*) FROM questions q WHERE q.assessment_id = s.assessment_id) "
            "AS questions FROM assessments s WHERE s.course_id = ? ORDER BY s.assessment_id",
            course_id)
        return render_template("course_manage.html", course=course, pages=pages, files=files,
                               assessments=assessments)

    @app.post("/instructor/courses/<course_id>/publish")
    @role_required("instructor")
    def instructor_publish(course_id):
        own_course(course_id)
        run("UPDATE courses SET status = 'published' WHERE course_id = ?", course_id)
        run("UPDATE assessments SET status = 'published', published_on = ? "
            "WHERE course_id = ? AND status != 'published'", today(), course_id)
        flash("Course published.")
        return redirect(f"/instructor/courses/{course_id}")

    @app.post("/instructor/courses/<course_id>/pages")
    @role_required("instructor")
    def instructor_add_page(course_id):
        own_course(course_id)
        title = request.form.get("title", "").strip()
        upload = request.files.get("file")
        extension = Path(upload.filename).suffix.lower() if upload and upload.filename else ""
        if not title:
            flash("A page needs a title.")
        elif upload and upload.filename and extension not in FILE_TYPES:
            flash("Only images (png, jpg, gif) and PDFs can be attached.")
        else:
            page = run("INSERT INTO pages (course_id, title, body) VALUES (?, ?, ?)",
                       course_id, title, request.form.get("body", ""))
            if extension:
                run("INSERT INTO attachments (page_id, filename, mimetype, data) VALUES (?, ?, ?, ?)",
                    page.lastrowid, Path(upload.filename).name, FILE_TYPES[extension], upload.read())
            flash("Page added.")
        return redirect(f"/instructor/courses/{course_id}")

    @app.get("/files/<int:attachment_id>")
    def attachment(attachment_id):
        if not g.user:
            abort(403)
        f = row("SELECT a.*, p.course_id, c.status FROM attachments a JOIN pages p "
                "ON p.page_id = a.page_id JOIN courses c ON c.course_id = p.course_id "
                "WHERE a.attachment_id = ?", attachment_id)
        if not f:
            abort(404)
        if g.user["role"] == "instructor":
            allowed = is_assigned(f["course_id"])
        elif g.user["role"] == "learner":
            allowed = f["status"] == "published" and row(
                "SELECT 1 FROM enrolments WHERE learner_id = ? AND course_id = ? "
                "AND withdrawn_on IS NULL", g.user["id"], f["course_id"])
        else:
            allowed = False
        if not allowed:
            abort(403)
        return Response(f["data"], mimetype=f["mimetype"],
                        headers={"Content-Disposition": f'inline; filename="{f["filename"]}"',
                                 "X-Content-Type-Options": "nosniff"})

    @app.post("/instructor/courses/<course_id>/assessments")
    @role_required("instructor")
    def instructor_add_assessment(course_id):
        course = own_course(course_id)
        f = request.form
        kind = f.get("type")
        if kind not in ("Quiz", "Assignment") or not f.get("title", "").strip():
            flash("Choose a type and give it a title.")
        else:
            published = course["status"] == "published"
            run("INSERT INTO assessments (assessment_id, course_id, type, title, due_on, weight_pct, "
                "author_id, status, published_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                int(next_id("assessments", "assessment_id")), course_id, kind, f["title"].strip(),
                f.get("due_on") or None, f.get("weight_pct") or None, g.user["id"],
                "published" if published else "draft", today() if published else None)
            flash(f"{kind} added.")
        return redirect(f"/instructor/courses/{course_id}")

    def own_assessment(assessment_id):
        a = row("SELECT * FROM assessments WHERE assessment_id = ?", assessment_id)
        if not a:
            abort(404)
        own_course(a["course_id"])
        return a

    @app.post("/instructor/assessments/<int:assessment_id>/publish")
    @role_required("instructor")
    def instructor_publish_assessment(assessment_id):
        a = own_assessment(assessment_id)
        run("UPDATE assessments SET status = 'published', published_on = ? WHERE assessment_id = ?",
            today(), assessment_id)
        return redirect(f"/instructor/courses/{a['course_id']}")

    @app.get("/instructor/assessments/<int:assessment_id>")
    @role_required("instructor")
    def instructor_assessment(assessment_id):
        a = own_assessment(assessment_id)
        questions = rows("SELECT * FROM questions WHERE assessment_id = ? ORDER BY question_id",
                         assessment_id)
        submissions = rows(
            "SELECT a.attempt_id, a.submitted_on, a.score, a.submission, l.full_name FROM attempts a "
            "JOIN learners l ON l.learner_id = a.learner_id WHERE a.assessment_id = ? "
            "ORDER BY (a.score IS NOT NULL), a.submitted_on DESC LIMIT 200", assessment_id
        ) if a["type"] == "Assignment" else []
        return render_template("assessment_manage.html", a=a, questions=questions,
                               submissions=submissions)

    @app.post("/instructor/assessments/<int:assessment_id>/questions")
    @role_required("instructor")
    def instructor_add_question(assessment_id):
        a = own_assessment(assessment_id)
        f = request.form
        choices = [c.strip() for c in f.getlist("choice") if c.strip()]
        correct = f.get("correct", type=int, default=-1)
        if a["type"] != "Quiz" or not f.get("prompt", "").strip() or len(choices) < 2 \
                or not 0 <= correct < len(choices):
            flash("A question needs a prompt, at least two choices, and a valid correct answer.")
        else:
            run("INSERT INTO questions (assessment_id, prompt, choices, correct) VALUES (?, ?, ?, ?)",
                assessment_id, f["prompt"].strip(), "\n".join(choices), correct)
            flash("Question added.")
        return redirect(f"/instructor/assessments/{assessment_id}")

    @app.post("/instructor/attempts/<attempt_id>/mark")
    @role_required("instructor")
    def instructor_mark(attempt_id):
        attempt = row("SELECT a.*, s.type FROM attempts a JOIN assessments s "
                      "ON s.assessment_id = a.assessment_id WHERE a.attempt_id = ?", attempt_id)
        if not attempt or attempt["type"] != "Assignment":
            abort(404)
        own_course(attempt["course_id"])
        score = request.form.get("score", type=float, default=-1)
        if not 0 <= score <= 100:
            flash("Score must be between 0 and 100.")
        elif attempt["score"] is not None:
            flash("This attempt is already marked; attempts are never overwritten.")
        else:
            run("UPDATE attempts SET score = ?, graded_by = ? WHERE attempt_id = ?",
                score, g.user["id"], attempt_id)
            flash("Marked.")
        return redirect(f"/instructor/assessments/{attempt['assessment_id']}")

    @app.get("/instructor/cohorts/<course_id>/results")
    @role_required("instructor")
    def instructor_results(course_id):
        course = own_course(course_id)
        page = max(request.args.get("page", 1, type=int), 1)
        data = rows(
            """SELECT l.learner_id, l.full_name, l.department, e.enrolled_on, e.withdrawn_on,
                      e.outcome, COALESCE(t.n, 0) AS attempts, t.average, t.best
               FROM enrolments e JOIN learners l ON l.learner_id = e.learner_id
               LEFT JOIN (SELECT learner_id, COUNT(*) AS n, ROUND(AVG(score), 1) AS average,
                                 MAX(score) AS best FROM attempts WHERE course_id = ?
                          GROUP BY learner_id) t ON t.learner_id = e.learner_id
               WHERE e.course_id = ? ORDER BY l.full_name, e.enrolled_on LIMIT ? OFFSET ?""",
            course_id, course_id, PER_PAGE, (page - 1) * PER_PAGE)
        total = row("SELECT COUNT(*) FROM enrolments WHERE course_id = ?", course_id)[0]
        return render_template("cohort_results.html", course=course, data=data, page=page,
                               pages=(total + PER_PAGE - 1) // PER_PAGE, total=total)

    @app.get("/instructor/cohorts/<course_id>/results.csv")
    @role_required("instructor")
    def instructor_results_csv(course_id):
        own_course(course_id)
        data = rows(
            """SELECT l.full_name, l.department, s.title, a.submitted_on, a.score
               FROM attempts a JOIN learners l ON l.learner_id = a.learner_id
               JOIN assessments s ON s.assessment_id = a.assessment_id
               WHERE a.course_id = ? ORDER BY l.full_name, a.submitted_on""", course_id)
        return csv_response(f"{course_id}-results.csv",
                            ["Learner", "Department", "Assessment", "Submitted", "Score"],
                            [list(r) for r in data])

    @app.get("/instructor/cohorts/<course_id>/learners/<int:learner_id>")
    @role_required("instructor")
    def instructor_learner(course_id, learner_id):
        course = own_course(course_id)
        learner = row("SELECT * FROM learners WHERE learner_id = ?", learner_id)
        if not learner or not row("SELECT 1 FROM enrolments WHERE learner_id = ? AND course_id = ?",
                                  learner_id, course_id):
            abort(404)
        attempts = sorted_attempts("a.learner_id = ? AND a.course_id = ?", (learner_id, course_id))
        return render_template("learner_attempts.html", course=course, learner=learner,
                               attempts=attempts)

    # ---- learner --------------------------------------------------------
    @app.get("/learner")
    @role_required("learner")
    def learner_home():
        lid = g.user["id"]
        enrolments = rows(
            "SELECT e.*, c.title, c.cohort, c.status, (SELECT MAX(a.score) FROM attempts a "
            "WHERE a.learner_id = e.learner_id AND a.course_id = e.course_id) AS best "
            "FROM enrolments e JOIN courses c "
            "ON c.course_id = e.course_id WHERE e.learner_id = ? ORDER BY e.enrolled_on DESC", lid)
        available = rows(
            "SELECT * FROM courses c WHERE status = 'published' AND NOT EXISTS (SELECT 1 FROM "
            "enrolments e WHERE e.course_id = c.course_id AND e.learner_id = ? "
            "AND e.withdrawn_on IS NULL AND e.outcome IS NULL) AND (ends_on IS NULL OR ends_on >= ?) "
            "ORDER BY title, starts_on", lid, today())
        attempts = sorted_attempts("a.learner_id = ?", (lid,))
        return render_template("learner_home.html", enrolments=enrolments, available=available,
                               attempts=attempts)

    @app.post("/learner/enrol/<course_id>")
    @role_required("learner")
    def learner_enrol(course_id):
        enrol(g.user["id"], course_id, "self")
        return redirect("/learner")

    @app.post("/learner/enrolments/<enrolment_id>/withdraw")
    @role_required("learner")
    def learner_withdraw(enrolment_id):
        withdraw(enrolment_id, g.user["id"])
        return redirect("/learner")

    def enrolled_course(course_id):
        course = row("SELECT * FROM courses WHERE course_id = ? AND status = 'published'", course_id)
        if not course or not row(
                "SELECT 1 FROM enrolments WHERE learner_id = ? AND course_id = ? "
                "AND withdrawn_on IS NULL", g.user["id"], course_id):
            abort(403)
        return course

    @app.get("/learner/courses/<course_id>")
    @role_required("learner")
    def learner_course(course_id):
        course = enrolled_course(course_id)
        pages, files = course_content(course_id)
        assessments = rows("SELECT * FROM assessments WHERE course_id = ? AND status = 'published' "
                           "ORDER BY assessment_id", course_id)
        return render_template("learner_course.html", course=course, pages=pages, files=files,
                               assessments=assessments)

    @app.route("/learner/assessments/<int:assessment_id>", methods=["GET", "POST"])
    @role_required("learner")
    def learner_assessment(assessment_id):
        a = row("SELECT * FROM assessments WHERE assessment_id = ? AND status = 'published'",
                assessment_id)
        if not a:
            abort(404)
        course = enrolled_course(a["course_id"])
        questions = rows("SELECT * FROM questions WHERE assessment_id = ? ORDER BY question_id",
                         assessment_id)
        if request.method == "POST":
            score = submission = None
            if a["type"] == "Quiz":
                if not questions:
                    flash("This quiz has no questions yet.")
                    return redirect(request.path)
                right = sum(request.form.get(f"q{q['question_id']}") == str(q["correct"])
                            for q in questions)
                score = round(100 * right / len(questions), 1)
            else:
                submission = request.form.get("submission", "").strip()
                if not submission:
                    flash("Write your answer before submitting.")
                    return redirect(request.path)
            run("INSERT INTO attempts (attempt_id, assessment_id, learner_id, course_id, submitted_on, "
                "score, submission) VALUES (?, ?, ?, ?, ?, ?, ?)",
                next_id("attempts", "attempt_id", "A", 6), assessment_id, g.user["id"],
                a["course_id"], datetime.now().strftime("%Y-%m-%d %H:%M"), score, submission)
            flash(f"Submitted. Score: {score}%." if score is not None else "Submitted for marking.")
            return redirect(request.path)
        attempts = sorted_attempts("a.learner_id = ? AND a.assessment_id = ?",
                                   (g.user["id"], assessment_id))
        return render_template("learner_assessment.html", a=a, course=course, attempts=attempts,
                               questions=[{**dict(q), "options": q["choices"].split("\n")}
                                          for q in questions])

    return app


def ensure_data(database):
    connection = db.connect(database)
    empty = connection.execute("SELECT COUNT(*) FROM staff").fetchone()[0] == 0
    connection.close()
    if empty:
        print("First start: importing data/ ...", flush=True)
        result = import_csvs(ROOT / "data", database)
        print(f"Imported {result['accepted']} rows, rejected {len(result['rejected'])}.")


if __name__ == "__main__":
    application = create_app()
    ensure_data(application.config["DATABASE"])
    application.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)))
