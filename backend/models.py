import hashlib
import json
import re
import secrets
from datetime import date, datetime, timezone
import sqlite3

from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy import Table as sa_Table
from sqlalchemy.sql import dml as sa_dml
from sqlalchemy.engine import Engine
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session as FlaskSQLAlchemySession


def _profile_table_names(mapper, clause) -> set[str]:
    """Best-effort extraction of table names from a mapper/statement."""
    names: set[str] = set()
    if mapper is not None:
        try:
            inspected = sa_inspect(mapper)
        except BaseException:
            inspected = mapper
        table = getattr(inspected, "local_table", None)
        if table is not None:
            if isinstance(table, sa_Table):
                names.add(table.name)
            else:
                names.add(getattr(table, "name", ""))
    if clause is not None:
        if isinstance(clause, sa_Table):
            names.add(clause.name)
        elif isinstance(clause, sa_dml.UpdateBase) and isinstance(
            clause.table, sa_Table
        ):
            names.add(clause.table.name)
        else:
            stack = []
            try:
                stack.extend(clause.get_final_froms())
            except Exception:
                pass
            seen: set[int] = set()
            while stack and len(seen) < 100:
                element = stack.pop()
                if element is None or id(element) in seen:
                    continue
                seen.add(id(element))
                if isinstance(element, sa_Table):
                    names.add(element.name)
                    continue
                inner = getattr(element, "element", None)
                if inner is not None:
                    stack.append(inner)
    return {name for name in names if name}


class RoutingSession(FlaskSQLAlchemySession):
    """Flask-SQLAlchemy session with company-level database routing.

    Tenant tables (everything in a company database, including the full
    ``user`` records) resolve to the active company's engine via
    ``tenants.engine_for_tables``. Control tables (``company``,
    ``user_routing``) and everything else resolve to the default engine, the
    global control database.
    """

    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        if bind is None:
            tables = _profile_table_names(mapper, clause)
            if tables:
                from backend import tenants

                tenant_engine = tenants.engine_for_tables(tables)
                if tenant_engine is not None:
                    return tenant_engine
        return super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)


db = SQLAlchemy(session_options={"class_": RoutingSession})

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$"
)


def normalize_email_domain(value: str) -> str:
    """Return a normalized email domain (lowercase, without leading @)."""
    domain = (value or "").strip().lower().lstrip("@")
    if not domain or not _DOMAIN_RE.match(domain):
        raise ValueError("Ungültige E-Mail-Domain.")
    return domain


def email_domain(email: str) -> str | None:
    """Return the normalized domain of a valid email address, else None."""
    value = (email or "").strip().lower()
    if value.count("@") != 1:
        return None
    local, domain = value.split("@", 1)
    if not local or not domain or not _DOMAIN_RE.match(domain):
        return None
    return domain


# Public/free-mail providers may never become a company's email domain:
# the claim is unprovable (anyone can create such a mailbox) and all future
# users of the company would need an address on that third-party domain.
PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        "aol.com", "bluewin.ch", "freenet.de", "gmail.com", "googlemail.com",
        "gmx.at", "gmx.ch", "gmx.de", "gmx.net", "hotmail.at", "hotmail.ch",
        "hotmail.com", "hotmail.de", "icloud.com", "live.at", "live.ch",
        "live.com", "live.de", "mail.com", "me.com", "msn.com", "orange.fr",
        "outlook.at", "outlook.ch", "outlook.com", "outlook.de", "pm.me",
        "proton.me", "protonmail.ch", "protonmail.com", "sunrise.ch",
        "t-online.de", "web.de", "yahoo.ch", "yahoo.co.uk", "yahoo.com",
        "yahoo.de", "yahoo.fr", "yandex.com", "yandex.ru",
    }
)


def is_public_email_domain(domain: str) -> bool:
    return (domain or "").strip().lower().lstrip("@") in PUBLIC_EMAIL_DOMAINS


def semester_for_date(exam_date, start_date, end_date):
    """Return the 1-based semester of an exam, counted forward to end_date."""
    if not exam_date or not start_date or not end_date or start_date >= end_date:
        return None
    if exam_date > end_date:
        return None

    def months_between(first, second):
        return (
            (second.year - first.year) * 12
            + (second.month - first.month)
            + (second.day - first.day) / 30.4375
        )

    total = max(1, round(months_between(start_date, end_date) / 6))
    offset = int(months_between(exam_date, end_date) // 6)
    return max(1, min(total, total - offset))


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Company(db.Model):
    """Control-database row: the company registry used to route to the
    company's own database file. Real company data lives in the tenant DB."""

    __tablename__ = "company"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    email_domain = db.Column(db.String(150), nullable=False, unique=True)
    address = db.Column(db.String(255), default="")

    @db.validates("name")
    def validate_name(self, key, value):
        name = (value or "").strip()
        if not name:
            raise ValueError("Firmenname ist erforderlich.")
        return name

    @db.validates("email_domain")
    def validate_email_domain(self, key, value):
        return normalize_email_domain(value)

    def matches_email(self, email: str) -> bool:
        return email_domain(email) == (self.email_domain or "").lower()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email_domain": self.email_domain,
            "address": self.address or "",
        }


class UserRouting(db.Model):
    """Control-database routing index.

    Maps a login e-mail address to a user *inside* a company database. Holds
    no profile data and no credentials: it exists so a login attempt can be
    routed to the correct company database file. The authoritative user
    record (including password hash and session state) lives in that
    company's ``app.db`` only.
    """

    __tablename__ = "user_routing"

    # Equal to the user's primary key inside the company database; the
    # (company_id, id) pair is globally unique.
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=False,
        primary_key=True,
    )
    company_email = db.Column(db.String(150), unique=True, nullable=False)
    private_email = db.Column(db.String(150), default="", nullable=False)
    school_email = db.Column(db.String(150), default="", nullable=False)


def _utcnow_naive() -> datetime:
    """SQLite stores DateTime columns without a timezone; keep everything
    in UTC-naive representation so comparisons stay consistent."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompanySignup(db.Model):
    """Control-database row: a pending (or completed) self-service company
    registration.

    The company and its admin account are only created once the signup
    e-mail was confirmed via a one-time verification link. Only the hashed
    token is stored (the raw token lives exclusively in the mail); the
    password is stored hashed (Argon2id) and reused for the admin account
    that is created upon verification.
    """

    __tablename__ = "company_signup"

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    surname = db.Column(db.String(120), nullable=False)
    job_title = db.Column(db.String(150), nullable=False)
    # The signup e-mail doubles as the company's email domain claim.
    email = db.Column(db.String(150), unique=True, nullable=False)
    email_domain = db.Column(db.String(150), nullable=False)
    company_name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    # SHA-256 hex digest of the one-time verification token; the raw token
    # is never persisted.
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    resend_count = db.Column(db.Integer, nullable=False, default=0)
    last_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: _utcnow_naive(),
        nullable=False,
    )
    completed_at = db.Column(db.DateTime, nullable=True)

    def is_expired(self) -> bool:
        return _utcnow_naive() >= self.expires_at


def company_signup_apply_token(signup: CompanySignup, expires_at) -> str:
    """Bind a fresh one-time token to the signup; returns the raw token."""
    token = secrets.token_urlsafe(32)
    signup.token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    signup.expires_at = expires_at
    return token



class User(db.Model):
    """Full user record. Rows of this table live in the company's own
    database (one company per database); `company_id` mirrors the control-DB
    company registry id. A user can never be assigned to another company."""

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50), nullable=False)  # 'ausbildner' | 'lernender'
    name = db.Column(db.String(120), nullable=False)
    surname = db.Column(db.String(120), nullable=False)
    # References the control-DB company registry (no cross-database FK).
    company_id = db.Column(db.Integer, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # Incremented to revoke all existing sessions for this user.
    session_version = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )

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

    # Pending first-login invitation (e-mailed link); NULL once the user
    # has set their own password via the link.
    invite_token_hash = db.Column(db.String(64), nullable=True)
    invite_expires_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        # All rows of this table belong to the active company database; the
        # company registry row comes from the control DB via the tenant
        # context set before any tenant query runs.
        from backend import tenants

        company = tenants.current_company_optional()
        return {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "surname": self.surname,
            "full_name": f"{self.name} {self.surname}".strip(),
            "company_id": self.company_id,
            "company": company.name if company else "",
            "company_domain": (
                company.email_domain if company else ""
            ),
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
    __table_args__ = (
        db.UniqueConstraint("supervisor", "student", name="uq_user_relation_pair"),
        db.CheckConstraint("supervisor != student", name="ck_user_relation_not_self"),
    )

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
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    author = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    goals = db.Column(db.Text, default="[]")  # Stored as JSON list of strings/objects
    assigned_students = db.Column(db.Text, default="[]")  # Stored as JSON list of student IDs
    start_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    global_eval_text = db.Column(db.Text, default="")
    # Access-management flag, kept in sync with is_published.
    planning_released = db.Column(db.Boolean, default=False, nullable=False)

    author_user = db.relationship("User", foreign_keys=[author], lazy="joined")
    document = db.relationship("Documents", foreign_keys=[document_id], lazy="joined")

    def parsed_goals(self):
        if not self.goals:
            return []
        try:
            data = json.loads(self.goals)
            return data if isinstance(data, list) else [str(self.goals)]
        except Exception:
            return [line.strip() for line in self.goals.splitlines() if line.strip()]

    def parsed_assigned_students(self):
        if not self.assigned_students:
            return []
        try:
            data = json.loads(self.assigned_students)
            if isinstance(data, list):
                result = []
                for x in data:
                    try:
                        result.append(int(x))
                    except (TypeError, ValueError):
                        pass
                return result
            return []
        except Exception:
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "parent_project": self.parent_project,
            "title": self.title,
            "description": self.description or "",
            "document_id": self.document_id,
            "document": self.document.to_dict() if self.document else None,
            "author": self.author,
            "author_name": (
                f"{self.author_user.name} {self.author_user.surname}"
                if self.author_user
                else ""
            ),
            "goals": self.parsed_goals(),
            "assigned_students": self.parsed_assigned_students(),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_published": bool(self.is_published),
            "is_completed": bool(self.is_completed),
            "global_eval_text": self.global_eval_text or "",
            "planning_released": bool(self.planning_released),
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
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    is_done = db.Column(db.Boolean, default=False, nullable=False)

    student_user = db.relationship("User", foreign_keys=[student], lazy="joined")
    supervisor_user = db.relationship("User", foreign_keys=[supervisor], lazy="joined")
    project_rel = db.relationship("Project", foreign_keys=[project], lazy="joined")
    document = db.relationship("Documents", foreign_keys=[document_id], lazy="joined")

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
            "document_id": self.document_id,
            "document": self.document.to_dict() if self.document else None,
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
    target_type = db.Column(
        db.String(50), default="goal", nullable=False
    )  # 'project' | 'task' | 'goal'
    goal = db.Column(db.String(255), default="", nullable=False)
    student = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    supervisor = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    planning_text = db.Column(db.Text, default="")
    eval_text = db.Column(db.Text, default="")
    score_type = db.Column(db.String(50), nullable=True)  # 'grade' | 'percent' | None
    score_value = db.Column(db.Float, nullable=True)
    is_released = db.Column(db.Boolean, default=False, nullable=False)
    # Optional attached evaluation file (PDF / Word), owned by the supervisor.
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    # Access-management flag, kept in sync with is_released.
    eval_released = db.Column(db.Boolean, default=False, nullable=False)

    student_user = db.relationship("User", foreign_keys=[student], lazy="joined")
    supervisor_user = db.relationship("User", foreign_keys=[supervisor], lazy="joined")
    project_rel = db.relationship("Project", foreign_keys=[project], lazy="joined")
    document = db.relationship("Documents", foreign_keys=[document_id], lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "project": self.project,
            "project_title": self.project_rel.title if self.project_rel else "",
            "participation": self.participation,
            "target_type": self.target_type or "goal",
            "goal": self.goal or "",
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
            "document_id": self.document_id,
            "document": (
                {
                    "id": self.document.id,
                    "name": self.document.name,
                    "filename": self.document.filename,
                }
                if self.document
                else None
            ),
            "score_type": self.score_type,
            "score_value": (
                round(float(self.score_value), 2)
                if self.score_value is not None
                else None
            ),
            "is_released": bool(self.is_released),
            "eval_released": bool(self.eval_released),
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
    goals = db.Column(db.Text, default="[]")  # JSON list of goal strings (like Project.goals)

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
            "goals": self.parsed_goals(),
            "semester": (
                semester_for_date(
                    self.date,
                    self.student_user.start_date,
                    self.student_user.end_date,
                )
                if self.student_user
                else None
            ),
        }

    def parsed_goals(self):
        if not self.goals:
            return []
        try:
            data = json.loads(self.goals)
            return data if isinstance(data, list) else []
        except Exception:
            return []


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
    feedback = db.Column(db.Text, default="")
    goals = db.Column(db.Text, default="[]")  # JSON list of goal strings (like Project.goals)
    feedback_author = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    owner_user = db.relationship("User", foreign_keys=[owner], lazy="joined")
    author_user = db.relationship("User", foreign_keys=[author], lazy="joined")
    feedback_author_user = db.relationship(
        "User", foreign_keys=[feedback_author], lazy="joined"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "filename": self.filename,
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
            "goals": self.parsed_goals(),
            "feedback": self.feedback or "",
            "feedback_author": self.feedback_author,
            "feedback_author_name": (
                f"{self.feedback_author_user.name} {self.feedback_author_user.surname}"
                if self.feedback_author_user
                else ""
            ),
            "goals": self.parsed_goals(),
        }

    def parsed_goals(self):
        if not self.goals:
            return []
        try:
            data = json.loads(self.goals)
            return data if isinstance(data, list) else []
        except Exception:
            return []


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
        doc = self.document
        owner_name = (
            f"{doc.owner_user.name} {doc.owner_user.surname}"
            if doc and doc.owner_user
            else ""
        )
        author_name = (
            f"{doc.author_user.name} {doc.author_user.surname}"
            if doc and doc.author_user
            else ""
        )
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "title": self.title,
            "description": self.description or "",
            "document_id": self.document_id,
            "document": doc.to_dict() if doc else None,
            "owner": doc.owner if doc else None,
            "owner_name": owner_name,
            "author": doc.author if doc else None,
            "author_name": author_name,
        }


def user_apply_invite(user: User, expires_at) -> str:
    """Bind a fresh one-time invitation token to a user; returns the raw
    token (its SHA-256 hash is stored on the tenant user row)."""
    token = secrets.token_urlsafe(32)
    user.invite_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    user.invite_expires_at = expires_at
    return token


def user_clear_invite(user: User) -> None:
    user.invite_token_hash = None
    user.invite_expires_at = None


# Unusable stand-in hash for invited (not yet activated) users: variants of
# argon2 keep the login timing identical to real accounts while making any
# password fail.
INVITED_PASSWORD_HASH = "argon2id$v=19$m=65536,t=3,p=4$invited$"


def _table_columns(cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def tenant_tables() -> list:
    """Table objects that live in every company (tenant) database."""
    return [
        User.__table__,
        UserRelation.__table__,
        Project.__table__,
        Participation.__table__,
        Eval.__table__,
        Grades.__table__,
        Documents.__table__,
        Knowledge.__table__,
    ]


def ensure_tenant_columns(engine: Engine) -> None:
    """Ensure newly added columns exist on a pre-existing company database.

    Runs per tenant engine (cheap PRAGMA checks); control tables live in the
    global database and are created fresh with their current schema.
    """
    migrations = [
        ("user", "session_version", "INTEGER NOT NULL DEFAULT 0"),
        ("user", "invite_token_hash", "VARCHAR(64)"),
        ("user", "invite_expires_at", "DATETIME"),
        ("project", "document_id", "INTEGER REFERENCES documents(id) ON DELETE SET NULL"),
        ("project", "assigned_students", "TEXT DEFAULT '[]'"),
        ("project", "is_published", "BOOLEAN NOT NULL DEFAULT 0"),
        ("project", "is_completed", "BOOLEAN NOT NULL DEFAULT 0"),
        ("project", "global_eval_text", "TEXT DEFAULT ''"),
        ("project", "planning_released", "BOOLEAN NOT NULL DEFAULT 0"),
        ("participation", "document_id", "INTEGER REFERENCES documents(id) ON DELETE SET NULL"),
        ("eval", "target_type", "VARCHAR(50) NOT NULL DEFAULT 'goal'"),
        ("eval", "score_type", "VARCHAR(50)"),
        ("eval", "score_value", "FLOAT"),
        ("documents", "goals", "TEXT DEFAULT '[]'"),
        ("grades", "goals", "TEXT DEFAULT '[]'"),
        ("eval", "is_released", "BOOLEAN NOT NULL DEFAULT 0"),
        ("eval", "eval_released", "BOOLEAN NOT NULL DEFAULT 0"),
        ("documents", "feedback", "TEXT DEFAULT ''"),
        (
            "documents",
            "feedback_author",
            "INTEGER REFERENCES user(id) ON DELETE SET NULL",
        ),
    ]
    original_cols = {}
    added_cols = {}
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        for table, column, col_def in migrations:
            if table not in original_cols:
                original_cols[table] = _table_columns(cursor, table)
            cols = original_cols[table] | added_cols.get(table, set())
            if column not in cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
                added_cols.setdefault(table, set()).add(column)

        # Keep the legacy release flags and the access-management flags in sync
        # when one side was introduced by this migration.
        project_added = added_cols.get("project", set())
        if "planning_released" in project_added and "is_published" not in project_added:
            cursor.execute("UPDATE project SET planning_released = is_published")
        elif "is_published" in project_added and "planning_released" not in project_added:
            cursor.execute("UPDATE project SET is_published = planning_released")

        eval_added = added_cols.get("eval", set())
        if "eval_released" in eval_added and "is_released" not in eval_added:
            cursor.execute("UPDATE eval SET eval_released = is_released")
        elif "is_released" in eval_added and "eval_released" not in eval_added:
            cursor.execute("UPDATE eval SET is_released = eval_released")

        conn.commit()
        cursor.close()
    finally:
        conn.close()
