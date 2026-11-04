from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from backend.models import db, Knowledge, Documents
from backend.auth import login_required, get_current_user
from backend.audit import audit
from backend.policies import visible_knowledge_owner_ids
from backend.storage import save_text_document, read_text_document, delete_stored_file
from backend.validation import parse_int, parse_str

bp = Blueprint("api_knowledge", __name__, url_prefix="/api/knowledge")


def visible_owner_ids(actor):
    """Return the user IDs whose knowledge entries the actor may read."""
    return visible_knowledge_owner_ids(actor)


def can_view_node(actor, node):
    return bool(node.document) and node.document.owner in visible_owner_ids(actor)


def can_edit_node(actor, node):
    return bool(node.document) and node.document.owner == actor.id


@bp.route("", methods=["GET"])
@login_required
def list_knowledge():
    actor = get_current_user()
    owner_ids = visible_owner_ids(actor)

    nodes = Knowledge.query.order_by(Knowledge.id.desc()).all()
    result = []
    for node in nodes:
        if not node.document or node.document.owner not in owner_ids:
            continue
        item = node.to_dict()
        item["content"] = read_text_document(node.document.path)
        result.append(item)

    return jsonify({"data": result})


@bp.route("/<int:node_id>", methods=["GET"])
@login_required
def get_knowledge_node(node_id):
    actor = get_current_user()
    node = db.session.get(Knowledge, node_id)
    if not node or not can_view_node(actor, node):
        return jsonify({"error": "Wissenseintrag nicht gefunden."}), 404

    item = node.to_dict()
    item["content"] = read_text_document(node.document.path) if node.document else ""
    return jsonify({"data": item})


@bp.route("", methods=["POST"])
@login_required
def create_knowledge_node():
    actor = get_current_user()
    data = request.get_json(silent=True) or {}

    title = parse_str(data.get("title"), "Titel")
    if not title:
        return jsonify({"error": "Titel ist erforderlich."}), 400

    parent_id = parse_int(
        data.get("parent_id"), "Übergeordnetes Thema", allow_none=True, min_value=1
    )
    if parent_id:
        parent = db.session.get(Knowledge, parent_id)
        if not parent:
            return jsonify({"error": "Übergeordnetes Thema nicht gefunden."}), 400
        if not can_edit_node(actor, parent):
            return jsonify({"error": "Übergeordnetes Thema gehört nicht Ihnen."}), 403
        parent_id = parent.id

    description = parse_str(data.get("description"), "Beschreibung")
    content = parse_str(
        data.get("content"), "Inhalt", allow_none=True
    ) or f"# {title}\n\n{description}"

    # Every knowledge node stores its page content as a document in /data/documents/<company-slug>/
    clean_filename, rel_path = save_text_document(
        content, title, actor.company_rel.name
    )
    doc = Documents(
        name=title,
        description=description,
        filename=clean_filename,
        path=rel_path,
        type="wissen",
        owner=actor.id,
        author=actor.id,
        is_template=False,
        updated_date=datetime.now(timezone.utc),
        is_done=True,
    )
    db.session.add(doc)
    db.session.flush()

    node = Knowledge(
        parent_id=parent_id,
        title=title,
        description=description,
        document_id=doc.id,
    )
    db.session.add(node)
    db.session.commit()
    audit("knowledge_created", knowledge_id=node.id, owner_id=actor.id)

    res = node.to_dict()
    res["content"] = content
    return jsonify({"data": res}), 201


@bp.route("/<int:node_id>", methods=["PUT"])
@login_required
def update_knowledge_node(node_id):
    actor = get_current_user()
    node = db.session.get(Knowledge, node_id)
    if not node or not can_view_node(actor, node):
        return jsonify({"error": "Wissenseintrag nicht gefunden."}), 404
    if not can_edit_node(actor, node):
        return jsonify({"error": "Keine Berechtigung."}), 403

    data = request.get_json(silent=True) or {}
    if "title" in data:
        title = parse_str(data.get("title"), "Titel")
        if title:
            node.title = title
    if "description" in data:
        node.description = parse_str(data.get("description"), "Beschreibung")
    if "parent_id" in data:
        pid = parse_int(
            data.get("parent_id"),
            "Übergeordnetes Thema",
            allow_none=True,
            min_value=1,
        )
        if pid and pid != node.id:
            parent = db.session.get(Knowledge, pid)
            if not parent:
                return jsonify({"error": "Übergeordnetes Thema nicht gefunden."}), 400
            if not can_edit_node(actor, parent):
                return jsonify({"error": "Übergeordnetes Thema gehört nicht Ihnen."}), 403
            node.parent_id = parent.id
        else:
            node.parent_id = None

    content = parse_str(data.get("content"), "Inhalt", allow_none=True)
    if node.document:
        node.document.name = node.title
        node.document.description = node.description
        node.document.updated_date = datetime.now(timezone.utc)
        if content is not None:
            save_text_document(
                content,
                node.title,
                actor.company_rel.name,
                existing_rel_path=node.document.path,
            )
    elif content is not None:
        clean_filename, rel_path = save_text_document(
            content, node.title, actor.company_rel.name
        )
        doc = Documents(
            name=node.title,
            description=node.description,
            filename=clean_filename,
            path=rel_path,
            type="wissen",
            owner=actor.id,
            author=actor.id,
            is_template=False,
            updated_date=datetime.now(timezone.utc),
            is_done=True,
        )
        db.session.add(doc)
        db.session.flush()
        node.document_id = doc.id

    db.session.commit()
    audit("knowledge_updated", knowledge_id=node.id)
    res = node.to_dict()
    res["content"] = (
        content
        if content is not None
        else (read_text_document(node.document.path) if node.document else "")
    )
    return jsonify({"data": res})


@bp.route("/<int:node_id>", methods=["DELETE"])
@login_required
def delete_knowledge_node(node_id):
    actor = get_current_user()
    node = db.session.get(Knowledge, node_id)
    if not node or not can_view_node(actor, node):
        return jsonify({"error": "Wissenseintrag nicht gefunden."}), 404
    if not can_edit_node(actor, node):
        return jsonify({"error": "Keine Berechtigung."}), 403

    # Delete child nodes first
    children = Knowledge.query.filter_by(parent_id=node.id).all()
    for child in children:
        if child.document:
            delete_stored_file(child.document.path)
            db.session.delete(child.document)
        db.session.delete(child)

    if node.document:
        delete_stored_file(node.document.path)
        db.session.delete(node.document)

    db.session.delete(node)
    db.session.commit()
    audit("knowledge_deleted", knowledge_id=node_id)
    return jsonify({"data": {"deleted": node_id}})
