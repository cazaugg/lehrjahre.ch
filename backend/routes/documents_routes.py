import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, send_file
from backend.models import db, Documents, User
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
    "sonstiges",
}


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
        u.id for u in User.query.filter_by(company=actor.company).all()
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
    return send_file(
        abs_path,
        as_attachment=as_attachment,
        download_name=doc.filename,
    )


@bp.route("", methods=["POST"])
@login_required
def create_document():
    actor = get_current_user()

    # Support both multipart/form-data (file upload) and JSON (text/markdown document)
    if request.content_type and "multipart/form-data" in request.content_type:
        form = request.form
        uploaded_file = request.files.get("file")
        name = (form.get("name") or "").strip()
        description = (form.get("description") or "").strip()
        doc_type = (form.get("type") or "sonstiges").strip().lower()
        owner_id = form.get("owner", type=int) or actor.id
        is_template = form.get("is_template", "false").lower() == "true"
        is_done = form.get("is_done", "false").lower() == "true"
        text_content = form.get("content")
        feedback = (form.get("feedback") or "").strip()
    else:
        data = request.get_json(silent=True) or {}
        uploaded_file = None
        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        doc_type = (data.get("type") or "sonstiges").strip().lower()
        owner_id = int(data.get("owner") or actor.id)
        is_template = bool(data.get("is_template", False))
        is_done = bool(data.get("is_done", False))
        text_content = data.get("content")
        feedback = (data.get("feedback") or "").strip()

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
                uploaded_file, owner_user.company
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    elif text_content is not None:
        if not name:
            return jsonify({"error": "Dokumentname ist erforderlich."}), 400
        clean_filename, rel_path = save_text_document(
            text_content, name, owner_user.company
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
        feedback=feedback if is_supervisor(actor) else "",
    )
    db.session.add(doc)
    db.session.commit()

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

    data = request.get_json(silent=True) or {}

    if doc.is_template:
        if not is_supervisor(actor):
            return jsonify({"error": "Keine Berechtigung."}), 403
    elif doc.type == "lernjournal":
        if is_student(actor):
            if doc.owner != actor.id:
                return jsonify({"error": "Keine Berechtigung."}), 403
            if "feedback" in data and (data.get("feedback") or "").strip() != (
                doc.feedback or ""
            ):
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
                ("name" in data and data["name"].strip() != doc.name)
                or (
                    "description" in data
                    and (data.get("description") or "").strip()
                    != (doc.description or "")
                )
                or (
                    "content" in data
                    and data["content"] is not None
                    and data["content"] != current_content
                )
                or ("is_done" in data and bool(data.get("is_done")) != bool(doc.is_done))
            )
            if has_entry_changes or "feedback" not in data:
                return jsonify(
                    {
                        "error": "Der Lernjournal-Eintrag selbst kann nur vom Lernenden bearbeitet werden."
                    }
                ), 403
            doc.feedback = (data.get("feedback") or "").strip()
            doc.updated_date = datetime.now(timezone.utc)
            db.session.commit()
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

    if "name" in data and data["name"].strip():
        doc.name = data["name"].strip()
    if "description" in data:
        doc.description = (data.get("description") or "").strip()
    if "is_done" in data:
        doc.is_done = bool(data.get("is_done"))
    if is_supervisor(actor) and "is_template" in data:
        doc.is_template = bool(data.get("is_template"))
    if is_supervisor(actor) and "feedback" in data:
        doc.feedback = (data.get("feedback") or "").strip()

    if "content" in data and data["content"] is not None:
        owner_user = db.session.get(User, doc.owner) or actor
        _, rel_path = save_text_document(
            data["content"], doc.name, owner_user.company, existing_rel_path=doc.path
        )
        doc.path = rel_path

    doc.updated_date = datetime.now(timezone.utc)
    db.session.commit()

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

    rel_path = doc.path
    db.session.delete(doc)
    db.session.commit()
    delete_stored_file(rel_path)

    return jsonify({"data": {"deleted": doc_id}})
