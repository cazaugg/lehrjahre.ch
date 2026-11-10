import os
import json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, send_file
from backend.models import db, Documents, Participation, User
from backend.auth import login_required, get_current_user, can_access_student
from backend.policies import (
    is_supervisor,
    is_student,
    is_supervisor_of,
    can_view_document,
    can_create_document,
    can_delete_document,
    visible_knowledge_owner_ids,
)
from backend.storage import (
    save_uploaded_file,
    save_text_document,
    read_text_document,
    resolve_safe_path,
    delete_stored_file,
)
from backend.audit import audit
from backend import tenants
from backend.validation import parse_bool, parse_int, parse_str

bp = Blueprint("api_documents", __name__, url_prefix="/api/documents")

VALID_TYPES = {
    "zeugnis",
    "ausbildungsgespraech",
    "kursnachweis",
    "lernjournal",
    "wissen",
    "vertrag",
    "bewerbung",
    "profilbild",
    "projekt",
    "sonstiges",
}


def project_document_is_released(doc):
    """A project document linked to a released participation is immutable."""
    if not doc or doc.type != "projekt":
        return False
    return (
        Participation.query.filter_by(document_id=doc.id, is_done=True).first()
        is not None
    )


def serialize_goals(goals_input) -> str:
    """Store goal strings as a JSON list (same format as Project.goals)."""
    if goals_input is None:
        return "[]"
    if isinstance(goals_input, list):
        cleaned = [str(g).strip() for g in goals_input if str(g).strip()]
        return json.dumps(cleaned, ensure_ascii=False)
    if isinstance(goals_input, str):
        lines = [line.strip() for line in goals_input.splitlines() if line.strip()]
        return json.dumps(lines, ensure_ascii=False)
    return "[]"


# Dokumenttypen, die Lernziele tragen dürfen (Ziele-Pflege im Editor).
GOAL_DOCUMENT_TYPES = {"lernjournal", "zeugnis", "kursnachweis"}


def parse_form_goals(raw):
    """Goals from a multipart form field (JSON array string or multiline text)."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except (ValueError, TypeError):
        pass
    return raw


@bp.route("", methods=["GET"])
@login_required
def list_documents():
    actor = get_current_user()
    doc_type = request.args.get("type")
    owner_id = request.args.get("owner", type=int)
    is_template = request.args.get("is_template")
    include_content = request.args.get("include_content") == "true"

    if owner_id is not None and doc_type != "profilbild":
        if doc_type == "wissen":
            if owner_id not in visible_knowledge_owner_ids(actor):
                return jsonify({"error": "Keine Berechtigung."}), 403
        elif owner_id != actor.id and not can_access_student(actor, owner_id):
            return jsonify({"error": "Keine Berechtigung."}), 403

    company_user_ids = [
        u.id for u in User.query.filter_by(company_id=actor.company_id).all()
    ]
    query = Documents.query.filter(Documents.owner.in_(company_user_ids))

    if doc_type:
        query = query.filter_by(type=doc_type)

    if is_template is not None:
        query = query.filter_by(is_template=(is_template.lower() == "true"))
    elif owner_id is not None:
        query = query.filter(
            (Documents.owner == owner_id) | (Documents.is_template.is_(True))
        )

    docs = query.order_by(Documents.updated_date.desc(), Documents.id.desc()).all()
    result = []
    for d in docs:
        if not can_view_document(actor, d):
            continue
        item = d.to_dict()
        if include_content or d.type in {"lernjournal", "wissen", "ausbildungsgespraech"}:
            item["content"] = read_text_document(d.path)
        result.append(item)

    return jsonify({"data": result})


@bp.route("/<int:doc_id>", methods=["GET"])
@login_required
def get_document(doc_id):
    actor = get_current_user()
    doc = db.session.get(Documents, doc_id)
    if not doc or not can_view_document(actor, doc):
        return jsonify({"error": "Dokument nicht gefunden."}), 404

    data = doc.to_dict()
    data["content"] = read_text_document(doc.path)
    return jsonify({"data": data})


@bp.route("/<int:doc_id>/file", methods=["GET"])
@login_required
def download_document(doc_id):
    actor = get_current_user()
    doc = db.session.get(Documents, doc_id)
    if not doc or not can_view_document(actor, doc):
        return jsonify({"error": "Dokument nicht gefunden."}), 404

    try:
        abs_path = resolve_safe_path(doc.path)
    except (ValueError, PermissionError):
        return jsonify({"error": "Ungültiger Dateipfad."}), 400

    if not os.path.isfile(abs_path):
        return jsonify({"error": "Datei auf dem Server nicht gefunden."}), 404

    as_attachment = request.args.get("download") == "1"
    response = send_file(
        abs_path,
        as_attachment=as_attachment,
        download_name=doc.filename,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.route("", methods=["POST"])
@login_required
def create_document():
    actor = get_current_user()

    # Support both multipart/form-data (file upload) and JSON (text/markdown document)
    if request.content_type and "multipart/form-data" in request.content_type:
        form = request.form
        uploaded_file = request.files.get("file")
        name = parse_str(form.get("name"), "Dokumentname")
        description = parse_str(form.get("description"), "Beschreibung")
        doc_type = parse_str(form.get("type"), "Dokumenttyp", default="sonstiges").lower()
        owner_id = form.get("owner", type=int) or actor.id
        is_template = form.get("is_template", "false").lower() == "true"
        is_done = form.get("is_done", "false").lower() == "true"
        text_content = parse_str(form.get("content"), "Inhalt", allow_none=True)
        feedback = parse_str(form.get("feedback"), "Rückmeldung")
        goals_input = parse_form_goals(form.get("goals"))
    else:
        data = request.get_json(silent=True) or {}
        uploaded_file = None
        name = parse_str(data.get("name"), "Dokumentname")
        description = parse_str(data.get("description"), "Beschreibung")
        doc_type = parse_str(data.get("type"), "Dokumenttyp", default="sonstiges").lower()
        owner_id = (
            parse_int(data.get("owner"), "Eigentümer", min_value=1)
            if data.get("owner") not in (None, "")
            else actor.id
        )
        is_template = parse_bool(data.get("is_template"), "Vorlage")
        is_done = parse_bool(data.get("is_done"), "Abgeschlossen")
        text_content = parse_str(data.get("content"), "Inhalt", allow_none=True)
        feedback = parse_str(data.get("feedback"), "Rückmeldung")
        goals_input = parse_form_goals(data.get("goals"))

    if doc_type not in VALID_TYPES:
        doc_type = "sonstiges"

    if is_student(actor):
        if owner_id != actor.id or is_template:
            return jsonify({"error": "Keine Berechtigung."}), 403
        if feedback:
            return jsonify(
                {"error": "Rückmeldungen können nur von Vorgesetzten erfasst werden."}
            ), 403

    if not can_create_document(actor, doc_type, owner_id, is_template=is_template):
        return jsonify({"error": "Keine Berechtigung zum Erstellen dieses Dokuments."}), 403

    owner_user = db.session.get(User, owner_id)
    if not owner_user:
        return jsonify({"error": "Eigentümer nicht gefunden."}), 404

    if uploaded_file and uploaded_file.filename:
        if not name:
            name = uploaded_file.filename
        try:
            clean_filename, rel_path = save_uploaded_file(
                uploaded_file, tenants.current_company().name
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    elif text_content is not None:
        if not name:
            return jsonify({"error": "Dokumentname ist erforderlich."}), 400
        clean_filename, rel_path = save_text_document(
            text_content, name, tenants.current_company().name
        )
    else:
        return jsonify(
            {"error": "Bitte eine Datei hochladen oder Textinhalt angeben."}
        ), 400

    doc = Documents(
        name=name,
        description=description,
        filename=clean_filename,
        path=rel_path,
        type=doc_type,
        owner=owner_user.id,
        author=actor.id,
        is_template=is_template,
        updated_date=datetime.now(timezone.utc),
        is_done=is_done,
        goals=serialize_goals(
            goals_input if doc_type in GOAL_DOCUMENT_TYPES else None
        ),
        feedback=feedback if is_supervisor(actor) else "",
        feedback_author=(
            actor.id if is_supervisor(actor) and feedback else None
        ),
    )
    db.session.add(doc)
    db.session.commit()
    audit(
        "document_created",
        document_id=doc.id,
        owner_id=doc.owner,
        document_type=doc.type,
        is_template=bool(doc.is_template),
    )

    res = doc.to_dict()
    if text_content is not None:
        res["content"] = text_content
    return jsonify({"data": res}), 201


@bp.route("/<int:doc_id>", methods=["PUT"])
@login_required
def update_document(doc_id):
    actor = get_current_user()
    doc = db.session.get(Documents, doc_id)
    if not doc or not can_view_document(actor, doc):
        return jsonify({"error": "Dokument nicht gefunden."}), 404

    if project_document_is_released(doc):
        return jsonify(
            {
                "error": "Abgegebene Projektdokumente können nicht mehr geändert werden. Bitte zuerst die Freigabe rückgängig machen."
            }
        ), 403

    # Support both multipart/form-data (file upload/replacement) and JSON
    uploaded_file = None
    if request.content_type and "multipart/form-data" in request.content_type:
        form = request.form
        uploaded_file = request.files.get("file")
        data = {key: value for key, value in form.items() if key != "file"}
    else:
        data = request.get_json(silent=True) or {}

    # Never let a supervisor turn someone else's private document into a
    # company-wide template. Templates must be created as templates.
    new_template = parse_bool(data.get("is_template"), "Vorlage")
    if new_template and not doc.is_template and doc.owner != actor.id:
        return jsonify(
            {"error": "Vorlagen können nur aus eigenen Dokumenten erstellt werden."}
        ), 403

    if doc.is_template:
        if not is_supervisor(actor):
            return jsonify({"error": "Keine Berechtigung."}), 403
    elif doc.type == "lernjournal":
        if is_student(actor):
            if doc.owner != actor.id:
                return jsonify({"error": "Keine Berechtigung."}), 403
            if "feedback" in data and parse_str(
                data.get("feedback"), "Rückmeldung"
            ) != (doc.feedback or ""):
                return jsonify(
                    {
                        "error": "Lernjournal-Rückmeldungen können nur von Vorgesetzten bearbeitet werden."
                    }
                ), 403
        elif is_supervisor(actor):
            if not is_supervisor_of(actor, doc.owner):
                return jsonify({"error": "Keine Berechtigung."}), 403
            current_content = read_text_document(doc.path)
            has_entry_changes = (
                (
                    "name" in data
                    and parse_str(data.get("name"), "Dokumentname") != doc.name
                )
                or (
                    "description" in data
                    and parse_str(data.get("description"), "Beschreibung")
                    != (doc.description or "")
                )
                or (
                    "content" in data
                    and data.get("content") is not None
                    and parse_str(data.get("content"), "Inhalt", allow_none=True)
                    != current_content
                )
                or (
                    "is_done" in data
                    and parse_bool(data.get("is_done"), "Abgeschlossen")
                    != bool(doc.is_done)
                )
            )
            # Vorgesetzte dürfen zusätzlich die Lernziele pflegen.
            if has_entry_changes or (
                "feedback" not in data and "goals" not in data
            ):
                return jsonify(
                    {
                        "error": "Der Lernjournal-Eintrag selbst kann nur vom Lernenden bearbeitet werden."
                    }
                ), 403
            if "goals" in data:
                doc.goals = serialize_goals(data.get("goals"))
            if "feedback" in data:
                doc.feedback = parse_str(data.get("feedback"), "Rückmeldung")
                doc.feedback_author = actor.id if doc.feedback else None
            doc.updated_date = datetime.now(timezone.utc)
            db.session.commit()
            audit(
                "document_feedback_updated",
                document_id=doc.id,
                owner_id=doc.owner,
            )
            res = doc.to_dict()
            res["content"] = current_content
            return jsonify({"data": res})
    elif doc.type in {"ausbildungsgespraech", "vertrag", "bewerbung"}:
        if not is_supervisor_of(actor, doc.owner):
            return jsonify({"error": "Keine Berechtigung."}), 403
    elif doc.type in {"zeugnis", "kursnachweis"}:
        if is_student(actor) and doc.owner != actor.id:
            return jsonify({"error": "Keine Berechtigung."}), 403
        if (
            is_supervisor(actor)
            and doc.owner != actor.id
            and not is_supervisor_of(actor, doc.owner)
        ):
            return jsonify({"error": "Keine Berechtigung."}), 403
    elif doc.type == "wissen":
        if doc.owner != actor.id:
            return jsonify({"error": "Keine Berechtigung."}), 403
    else:
        if is_student(actor) and doc.owner != actor.id:
            return jsonify({"error": "Keine Berechtigung."}), 403
        if is_supervisor(actor) and doc.owner != actor.id and not is_supervisor_of(
            actor, doc.owner
        ):
            return jsonify({"error": "Keine Berechtigung."}), 403

    if "name" in data:
        name = parse_str(data.get("name"), "Dokumentname")
        if name:
            doc.name = name
    if "description" in data:
        doc.description = parse_str(data.get("description"), "Beschreibung")
    if "is_done" in data:
        doc.is_done = parse_bool(data.get("is_done"), "Abgeschlossen")
    if doc.type in GOAL_DOCUMENT_TYPES and "goals" in data:
        doc.goals = serialize_goals(data.get("goals"))
    if is_supervisor(actor) and "is_template" in data:
        doc.is_template = new_template
    if is_supervisor(actor) and "feedback" in data:
        doc.feedback = parse_str(data.get("feedback"), "Rückmeldung")
        doc.feedback_author = actor.id if doc.feedback else None

    if "content" in data and data.get("content") is not None:
        content = parse_str(data.get("content"), "Inhalt", allow_none=True)
        owner_user = db.session.get(User, doc.owner) or actor
        _, rel_path = save_text_document(
            content,
            doc.name,
            tenants.current_company().name,
            existing_rel_path=doc.path,
        )
        doc.path = rel_path

    # Replace the stored file (e.g. new PDF/Word version) when a file was
    # uploaded together with the metadata update.
    old_file_path = None
    if uploaded_file and uploaded_file.filename:
        try:
            clean_filename, rel_path = save_uploaded_file(
                uploaded_file, tenants.current_company().name
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if rel_path != doc.path:
            old_file_path = doc.path
        doc.filename = clean_filename
        doc.path = rel_path

    doc.updated_date = datetime.now(timezone.utc)
    db.session.commit()
    if old_file_path:
        delete_stored_file(old_file_path)
    audit(
        "document_updated",
        document_id=doc.id,
        owner_id=doc.owner,
        document_type=doc.type,
    )

    res = doc.to_dict()
    res["content"] = read_text_document(doc.path)
    return jsonify({"data": res})


@bp.route("/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(doc_id):
    actor = get_current_user()
    doc = db.session.get(Documents, doc_id)
    if not doc or not can_view_document(actor, doc):
        return jsonify({"error": "Dokument nicht gefunden."}), 404

    if not can_delete_document(actor, doc):
        return jsonify({"error": "Keine Berechtigung zum Löschen."}), 403

    if project_document_is_released(doc):
        return jsonify(
            {
                "error": "Abgegebene Projektdokumente können nicht mehr gelöscht werden. Bitte zuerst die Freigabe rückgängig machen."
            }
        ), 403

    rel_path = doc.path
    owner_id = doc.owner
    document_type = doc.type
    db.session.delete(doc)
    db.session.commit()
    delete_stored_file(rel_path)
    audit(
        "document_deleted",
        document_id=doc_id,
        owner_id=owner_id,
        document_type=document_type,
    )

    return jsonify({"data": {"deleted": doc_id}})
