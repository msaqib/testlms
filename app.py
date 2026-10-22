import sqlite3
from pathlib import Path

from flask import Flask, abort, redirect, render_template_string, request, session
from werkzeug.security import check_password_hash


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(DATABASE=str(Path("lms.db")), SECRET_KEY="development")
    if config:
        app.config.update(config)

    def connection():
        database = sqlite3.connect(app.config["DATABASE"])
        database.row_factory = sqlite3.Row
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL
            )
            """
        )
        database.commit()
        return database

    @app.get("/sign-in")
    def sign_in_page():
        return render_template_string(
            """
            <form method="post">
              <label>Username <input name="username" required></label>
              <label>Password <input name="password" type="password" required></label>
              <button>Sign in</button>
            </form>
            """
        )

    @app.post("/sign-in")
    def sign_in():
        database = connection()
        user = database.execute(
            "SELECT * FROM users WHERE username = ?",
            (request.form.get("username"),),
        ).fetchone()
        database.close()
        if (
            user is None
            or not user["active"]
            or not check_password_hash(user["password"], request.form.get("password", ""))
        ):
            abort(403)
        session["role"] = user["role"]
        return redirect(f"/{user['role']}")

    @app.get("/administrator")
    def administrator_home():
        if session.get("role") != "administrator":
            abort(403)
        return "Administrator home"

    @app.get("/instructor")
    def instructor_home():
        if session.get("role") != "instructor":
            abort(403)
        return "Instructor home"

    @app.get("/learner")
    def learner_home():
        if session.get("role") != "learner":
            abort(403)
        return "Learner home"

    return app


if __name__ == "__main__":
    create_app().run()
