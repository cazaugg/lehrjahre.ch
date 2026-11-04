import secrets
from functools import wraps
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from flask import session, request, jsonify, g
from backend.models import db, User, UserRelation

ph = PasswordHasher()
DUMMY_PASSWORD_HASH = ph.hash("timing-only-dummy-password")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def hash_password(plain_password: str) -> str:
    return ph.hash(plain_password)


def verify_password(password_hash: str, plain_password: str) -> bool:
    if not password_hash or not plain_password:
        return False
    try:
        return ph.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return ph.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return False


def bump_session_version(user: User) -> None:
    """Revoke all existing sessions for `user` on the next request."""
    user.session_version = int(user.session_version or 0) + 1


def ensure_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    return token


def verify_csrf():
    if request.method in SAFE_METHODS:
        return None
    # Login creates a fresh session, exempt from pre-existing CSRF requirement
    if request.endpoint == "api_auth.login":
        return None
    expected = session.get("csrf_token")
    provided = request.headers.get("X-CSRF-Token")
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        return jsonify({"error": "Ungültiges oder fehlendes CSRF-Token."}), 403
    return None


def get_current_user() -> User | None:
    if hasattr(g, "current_user"):
        return g.current_user
    user_id = session.get("user_id")
    if not user_id:
        g.current_user = None
        return None
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        g.current_user = None
        return None
    try:
        version_ok = int(session.get("session_version")) == int(
            user.session_version or 0
        )
    except (TypeError, ValueError):
        version_ok = False
    if not version_ok:
        session.clear()
        g.current_user = None
        return None
    g.current_user = user
    return user


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Nicht angemeldet."}), 401
        return f(*args, **kwargs)

    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Nicht angemeldet."}), 401
            if user.role not in roles:
                return jsonify({"error": "Keine Berechtigung für diese Aktion."}), 403
            return f(*args, **kwargs)

        return decorated

    return decorator


def is_admin_or_hr(user: User) -> bool:
    """All supervisors (ausbildner) have uniform supervisor permissions."""
    return bool(user and user.role == "ausbildner")


def can_access_student(actor: User, student_id: int) -> bool:
    """Check whether actor can view/manage data for student_id."""
    from backend.policies import can_access_student as policy_can_access_student

    return policy_can_access_student(actor, student_id)
