import json
from datetime import date, datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50), nullable=False)  # 'ausbildner' | 'lernender'
    name = db.Column(db.String(120), nullable=False)
    surname = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Contacts: private, school, company
    private_address = db.Column(db.String(255), default="")
    private_email = db.Column(db.String(150), default="")
    private_phone = db.Column(db.String(60), default="")

    school_address = db.Column(db.String(255), default="")
    school_email = db.Column(db.String(150), default="")
    school_phone = db.Column(db.String(60), default="")

    company_address = db.Column(db.String(255), default="")
    company_email = db.Column(db.String(150), unique=True, nullable=False)
    company_phone = db.Column(db.String(60), default="")

    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    job_title = db.Column(db.String(150), nullable=False)
    picture_document = db.Column(
        db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "surname": self.surname,
            "full_name": f"{self.name} {self.surname}".strip(),
            "company": self.company,
            "private_address": self.private_address or "",
            "private_email": self.private_email or "",
            "private_phone": self.private_phone or "",
            "school_address": self.school_address or "",
            "school_email": self.school_email or "",
            "school_phone": self.school_phone or "",
            "company_address": self.company_address or "",
            "company_email": self.company_email or "",
            "company_phone": self.company_phone or "",
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "job_title": self.job_title,
            "picture_document": self.picture_document,
        }


class UserRelation(db.Model):
    __tablename__ = "user_relation"

    id = db.Column(db.Integer, primary_key=True)
    supervisor = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    student = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )

    supervisor_user = db.relationship("User", foreign_keys=[supervisor], lazy="joined")
    student_user = db.relationship("User", foreign_keys=[student], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "supervisor": self.supervisor,
            "student": self.student,
            "supervisor_name": (
                f"{self.supervisor_user.name} {self.supervisor_user.surname}"
                if self.supervisor_user
                else ""
            ),
            "supervisor_job_title": (
                self.supervisor_user.job_title if self.supervisor_user else ""
            ),
            "student_name": (
                f"{self.student_user.name} {self.student_user.surname}"
                if self.student_user
                else ""
            ),
        }


class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)
    parent_project = db.Column(
        db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=True
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    author = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    goals = db.Column(db.Text, default="[]")  # Stored as JSON list of strings/objects
    start_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)

    author_user = db.relationship("User", foreign_keys=[author], lazy="joined")

    def parsed_goals(self):
        if not self.goals:
            return []
        try:
            data = json.loads(self.goals)
            return data if isinstance(data, list) else [str(self.goals)]
        except Exception:
            return [line.strip() for line in self.goals.splitlines() if line.strip()]

    def to_dict(self):
        return {
            "id": self.id,
            "parent_project": self.parent_project,
            "title": self.title,
            "description": self.description or "",
            "author": self.author,
            "author_name": (
                f"{self.author_user.name} {self.author_user.surname}"
                if self.author_user
                else ""
            ),
            "goals": self.parsed_goals(),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
        }


class Participation(db.Model):
    __tablename__ = "participation"

    id = db.Column(db.Integer, primary_key=True)
    supervisor = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    student = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    project = db.Column(
        db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(200), nullable=False)
    text = db.Column(db.Text, default="")
    is_done = db.Column(db.Boolean, default=False, nullable=False)

    student_user = db.relationship("User", foreign_keys=[student], lazy="joined")
    supervisor_user = db.relationship("User", foreign_keys=[supervisor], lazy="joined")
    project_rel = db.relationship("Project", foreign_keys=[project], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "supervisor": self.supervisor,
            "supervisor_name": (
                f"{self.supervisor_user.name} {self.supervisor_user.surname}"
                if self.supervisor_user
                else ""
            ),
            "student": self.student,
            "student_name": (
                f"{self.student_user.name} {self.student_user.surname}"
                if self.student_user
                else ""
            ),
            "project": self.project,
            "project_title": self.project_rel.title if self.project_rel else "",
            "title": self.title,
            "text": self.text or "",
            "is_done": bool(self.is_done),
        }


class Eval(db.Model):
    __tablename__ = "eval"

    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(
        db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    participation = db.Column(
        db.Integer,
        db.ForeignKey("participation.id", ondelete="SET NULL"),
        nullable=True,
    )
    goal = db.Column(db.String(255), nullable=False)
    student = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    supervisor = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    planning_text = db.Column(db.Text, default="")
    eval_text = db.Column(db.Text, default="")

    student_user = db.relationship("User", foreign_keys=[student], lazy="joined")
    supervisor_user = db.relationship("User", foreign_keys=[supervisor], lazy="joined")
    project_rel = db.relationship("Project", foreign_keys=[project], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "project": self.project,
            "project_title": self.project_rel.title if self.project_rel else "",
            "participation": self.participation,
            "goal": self.goal,
            "student": self.student,
            "student_name": (
                f"{self.student_user.name} {self.student_user.surname}"
                if self.student_user
                else ""
            ),
            "supervisor": self.supervisor,
            "supervisor_name": (
                f"{self.supervisor_user.name} {self.supervisor_user.surname}"
                if self.supervisor_user
                else ""
            ),
            "planning_text": self.planning_text or "",
            "eval_text": self.eval_text or "",
        }


class Grades(db.Model):
    __tablename__ = "grades"

    id = db.Column(db.Integer, primary_key=True)
    student = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    subject = db.Column(db.String(150), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    grade = db.Column(db.Float, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    comment = db.Column(db.Text, default="")

    student_user = db.relationship("User", foreign_keys=[student], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "student": self.student,
            "student_name": (
                f"{self.student_user.name} {self.student_user.surname}"
                if self.student_user
                else ""
            ),
            "subject": self.subject,
            "date": self.date.isoformat() if self.date else None,
            "grade": round(float(self.grade), 2),
            "title": self.title,
            "comment": self.comment or "",
        }


class Documents(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(500), nullable=False)
    type = db.Column(db.String(80), nullable=False)
    owner = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    author = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    is_template = db.Column(db.Boolean, default=False, nullable=False)
    updated_date = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    is_done = db.Column(db.Boolean, default=False, nullable=False)

    owner_user = db.relationship("User", foreign_keys=[owner], lazy="joined")
    author_user = db.relationship("User", foreign_keys=[author], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "filename": self.filename,
            "path": self.path,
            "type": self.type,
            "owner": self.owner,
            "owner_name": (
                f"{self.owner_user.name} {self.owner_user.surname}"
                if self.owner_user
                else ""
            ),
            "author": self.author,
            "author_name": (
                f"{self.author_user.name} {self.author_user.surname}"
                if self.author_user
                else ""
            ),
            "is_template": bool(self.is_template),
            "updated_date": (
                self.updated_date.isoformat() if self.updated_date else None
            ),
            "is_done": bool(self.is_done),
        }


class Knowledge(db.Model):
    __tablename__ = "knowledge"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(
        db.Integer, db.ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=True
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    document = db.relationship("Documents", foreign_keys=[document_id], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "title": self.title,
            "description": self.description or "",
            "document_id": self.document_id,
            "document": self.document.to_dict() if self.document else None,
        }
