from flask import Blueprint, request, jsonify
from bson import ObjectId
import datetime
from config.db import mongo
from utils.auth_middleware import get_current_user, require_auth, require_roles, is_admin

marketplace_admin_bp = Blueprint('marketplace_admin', __name__)
DEFAULT_COMMISSION_PERCENT = 8.0


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _normalize_status(value, allowed, default):
    normalized = str(value or '').strip().lower()
    return normalized if normalized in allowed else default


def _get_platform_settings():
    settings = mongo.db.platform_settings.find_one({'key': 'commission'})
    if settings:
        return settings

    default_doc = {
        'key': 'commission',
        'default_percent': DEFAULT_COMMISSION_PERCENT,
        'updated_by': 'system',
        'updated_at': datetime.datetime.utcnow()
    }
    mongo.db.platform_settings.insert_one(default_doc)
    return default_doc


def get_default_commission_percent():
    settings = _get_platform_settings()
    percent = _safe_float(settings.get('default_percent', DEFAULT_COMMISSION_PERCENT), DEFAULT_COMMISSION_PERCENT)
    return max(0.0, min(percent, 100.0))


def _user_to_admin_card(user_doc):
    role = user_doc.get('role', 'renter')
    kyc_status = user_doc.get('kyc_status')
    if not kyc_status:
        kyc_status = 'approved' if role in {'owner', 'admin'} else 'not_required'

    return {
        'id': str(user_doc.get('_id', '')),
        'name': user_doc.get('name', ''),
        'email': user_doc.get('email', ''),
        'phone': user_doc.get('phone', ''),
        'location': user_doc.get('location', ''),
        'role': role,
        'kyc_status': kyc_status,
        'kyc_details': user_doc.get('kyc_details', {}),
        'kyc_review_notes': user_doc.get('kyc_review_notes', ''),
        'kyc_submitted_at': str(user_doc.get('kyc_submitted_at', '')),
        'kyc_reviewed_at': str(user_doc.get('kyc_reviewed_at', ''))
    }


def _dispute_to_dict(dispute):
    return {
        'id': str(dispute.get('_id', '')),
        'rental_id': str(dispute.get('rental_id', '')),
        'raised_by': str(dispute.get('raised_by', '')),
        'raised_by_name': dispute.get('raised_by_name', ''),
        'owner_id': str(dispute.get('owner_id', '')),
        'renter_id': str(dispute.get('renter_id', '')),
        'issue_type': dispute.get('issue_type', 'other'),
        'description': dispute.get('description', ''),
        'status': dispute.get('status', 'open'),
        'admin_notes': dispute.get('admin_notes', ''),
        'resolution_note': dispute.get('resolution_note', ''),
        'created_at': str(dispute.get('created_at', '')),
        'updated_at': str(dispute.get('updated_at', ''))
    }


def _commission_to_dict(doc):
    return {
        'id': str(doc.get('_id', '')),
        'rental_id': str(doc.get('rental_id', '')),
        'rental_amount': doc.get('rental_amount', 0),
        'commission_percent': doc.get('commission_percent', 0),
        'commission_amount': doc.get('commission_amount', 0),
        'owner_payout': doc.get('owner_payout', 0),
        'currency': doc.get('currency', 'INR'),
        'status': doc.get('status', 'applied'),
        'created_at': str(doc.get('created_at', '')),
        'updated_at': str(doc.get('updated_at', ''))
    }


def apply_commission_for_rental(rental_doc, actor_id='system'):
    rental_id = rental_doc.get('_id')
    if not rental_id:
        return None

    existing = mongo.db.commissions.find_one({'rental_id': rental_id})
    if existing:
        return existing

    rental_amount = _safe_int(rental_doc.get('total_amount', 0), 0)
    commission_percent = get_default_commission_percent()
    commission_amount = int(round((rental_amount * commission_percent) / 100.0))
    owner_payout = max(0, rental_amount - commission_amount)

    doc = {
        'rental_id': rental_id,
        'rental_amount': rental_amount,
        'commission_percent': commission_percent,
        'commission_amount': commission_amount,
        'owner_payout': owner_payout,
        'currency': 'INR',
        'status': 'applied',
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow(),
        'updated_by': str(actor_id)
    }
    inserted = mongo.db.commissions.insert_one(doc)
    doc['_id'] = inserted.inserted_id
    return doc


@marketplace_admin_bp.route('/owner-kyc', methods=['POST'])
@require_auth
def submit_owner_kyc():
    user = get_current_user()
    if str(user.get('role', '')).lower() != 'owner':
        return jsonify({'error': 'Only owner accounts can submit KYC'}), 403

    data = request.get_json() or {}
    business_name = str(data.get('business_name', '')).strip()
    id_number = str(data.get('id_number', '')).strip()
    pan_number = str(data.get('pan_number', '')).strip()
    id_proof_url = str(data.get('id_proof_url', '')).strip()
    address_proof_url = str(data.get('address_proof_url', '')).strip()

    if not business_name or not id_number:
        return jsonify({'error': 'business_name and id_number are required'}), 400

    update_doc = {
        'kyc_status': 'pending',
        'kyc_details': {
            'business_name': business_name,
            'id_number': id_number,
            'pan_number': pan_number,
            'id_proof_url': id_proof_url,
            'address_proof_url': address_proof_url
        },
        'kyc_review_notes': '',
        'kyc_submitted_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow()
    }

    mongo.db.users.update_one({'_id': user['_id']}, {'$set': update_doc})
    updated = mongo.db.users.find_one({'_id': user['_id']})
    return jsonify({'message': 'KYC submitted. Admin approval pending.', 'owner': _user_to_admin_card(updated)})


@marketplace_admin_bp.route('/owner-kyc/status', methods=['GET'])
@require_auth
def owner_kyc_status():
    user = get_current_user()
    return jsonify({'owner': _user_to_admin_card(user)})


@marketplace_admin_bp.route('/owner-kyc/pending', methods=['GET'])
@require_roles(['admin'])
def pending_owner_kyc():
    users = list(mongo.db.users.find({'role': 'owner', 'kyc_status': 'pending'}).sort('kyc_submitted_at', 1))
    return jsonify({'owners': [_user_to_admin_card(user) for user in users]})


@marketplace_admin_bp.route('/owner-kyc/<owner_id>/decision', methods=['PUT'])
@require_roles(['admin'])
def review_owner_kyc(owner_id):
    data = request.get_json() or {}
    decision = _normalize_status(data.get('decision'), {'approved', 'rejected'}, 'rejected')
    notes = str(data.get('notes', '')).strip()
    reviewer = get_current_user()

    try:
        owner_object_id = ObjectId(owner_id)
    except Exception:
        return jsonify({'error': 'Invalid owner id'}), 400

    owner = mongo.db.users.find_one({'_id': owner_object_id, 'role': 'owner'})
    if not owner:
        return jsonify({'error': 'Owner not found'}), 404

    mongo.db.users.update_one(
        {'_id': owner_object_id},
        {
            '$set': {
                'kyc_status': decision,
                'kyc_review_notes': notes,
                'kyc_reviewed_at': datetime.datetime.utcnow(),
                'kyc_reviewed_by': str(reviewer['_id']),
                'updated_at': datetime.datetime.utcnow()
            }
        }
    )
    updated = mongo.db.users.find_one({'_id': owner_object_id})
    return jsonify({'owner': _user_to_admin_card(updated)})


@marketplace_admin_bp.route('/commission', methods=['GET'])
@require_roles(['admin'])
def get_commission_settings():
    settings = _get_platform_settings()
    return jsonify({
        'default_percent': get_default_commission_percent(),
        'updated_at': str(settings.get('updated_at', '')),
        'updated_by': settings.get('updated_by', '')
    })


@marketplace_admin_bp.route('/commission', methods=['PUT'])
@require_roles(['admin'])
def update_commission_settings():
    data = request.get_json() or {}
    value = _safe_float(data.get('default_percent'), DEFAULT_COMMISSION_PERCENT)
    if value < 0 or value > 100:
        return jsonify({'error': 'default_percent must be between 0 and 100'}), 400

    user = get_current_user()
    mongo.db.platform_settings.update_one(
        {'key': 'commission'},
        {
            '$set': {
                'default_percent': value,
                'updated_at': datetime.datetime.utcnow(),
                'updated_by': str(user['_id'])
            }
        },
        upsert=True
    )
    return jsonify({'message': 'Commission updated', 'default_percent': value})


@marketplace_admin_bp.route('/commissions', methods=['GET'])
@require_roles(['admin'])
def list_commissions():
    limit = _safe_int(request.args.get('limit', 50), 50)
    limit = max(1, min(limit, 200))
    docs = list(mongo.db.commissions.find().sort('created_at', -1).limit(limit))
    return jsonify({'commissions': [_commission_to_dict(doc) for doc in docs]})


@marketplace_admin_bp.route('/disputes', methods=['POST'])
@require_auth
def create_dispute():
    user = get_current_user()
    data = request.get_json() or {}

    rental_id = str(data.get('rental_id', '')).strip()
    issue_type = _normalize_status(data.get('issue_type'), {'payment', 'damage', 'delivery', 'quality', 'other'}, 'other')
    description = str(data.get('description', '')).strip()

    if not rental_id or not description:
        return jsonify({'error': 'rental_id and description are required'}), 400

    try:
        rental_obj_id = ObjectId(rental_id)
    except Exception:
        return jsonify({'error': 'Invalid rental id'}), 400

    rental = mongo.db.rentals.find_one({'_id': rental_obj_id})
    if not rental:
        return jsonify({'error': 'Rental not found'}), 404

    user_id_str = str(user['_id'])
    participants = {str(rental.get('owner_id', '')), str(rental.get('renter_id', ''))}
    if user_id_str not in participants and not is_admin(user):
        return jsonify({'error': 'Only rental participants can raise disputes'}), 403

    doc = {
        'rental_id': rental_obj_id,
        'raised_by': user['_id'],
        'raised_by_name': user.get('name', ''),
        'owner_id': rental.get('owner_id'),
        'renter_id': rental.get('renter_id'),
        'issue_type': issue_type,
        'description': description,
        'status': 'open',
        'admin_notes': '',
        'resolution_note': '',
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow()
    }

    inserted = mongo.db.disputes.insert_one(doc)
    doc['_id'] = inserted.inserted_id
    return jsonify({'dispute': _dispute_to_dict(doc)}), 201


@marketplace_admin_bp.route('/disputes/my', methods=['GET'])
@require_auth
def my_disputes():
    user = get_current_user()
    user_id = user['_id']
    docs = list(mongo.db.disputes.find({
        '$or': [
            {'raised_by': user_id},
            {'owner_id': user_id},
            {'renter_id': user_id}
        ]
    }).sort('created_at', -1))
    return jsonify({'disputes': [_dispute_to_dict(doc) for doc in docs]})


@marketplace_admin_bp.route('/disputes', methods=['GET'])
@require_roles(['admin'])
def all_disputes():
    status = _normalize_status(request.args.get('status'), {'open', 'reviewing', 'resolved', 'rejected'}, '')
    query = {}
    if status:
        query['status'] = status

    docs = list(mongo.db.disputes.find(query).sort('created_at', -1).limit(200))
    return jsonify({'disputes': [_dispute_to_dict(doc) for doc in docs]})


@marketplace_admin_bp.route('/disputes/<dispute_id>/status', methods=['PUT'])
@require_roles(['admin'])
def update_dispute_status(dispute_id):
    data = request.get_json() or {}
    status = _normalize_status(data.get('status'), {'open', 'reviewing', 'resolved', 'rejected'}, 'reviewing')
    admin_notes = str(data.get('admin_notes', '')).strip()
    resolution_note = str(data.get('resolution_note', '')).strip()

    try:
        dispute_obj_id = ObjectId(dispute_id)
    except Exception:
        return jsonify({'error': 'Invalid dispute id'}), 400

    existing = mongo.db.disputes.find_one({'_id': dispute_obj_id})
    if not existing:
        return jsonify({'error': 'Dispute not found'}), 404

    mongo.db.disputes.update_one(
        {'_id': dispute_obj_id},
        {
            '$set': {
                'status': status,
                'admin_notes': admin_notes,
                'resolution_note': resolution_note,
                'updated_at': datetime.datetime.utcnow()
            }
        }
    )
    updated = mongo.db.disputes.find_one({'_id': dispute_obj_id})
    return jsonify({'dispute': _dispute_to_dict(updated)})


@marketplace_admin_bp.route('/dashboard', methods=['GET'])
@require_roles(['admin'])
def admin_dashboard():
    pending_kyc = mongo.db.users.count_documents({'role': 'owner', 'kyc_status': 'pending'})
    approved_owners = mongo.db.users.count_documents({'role': 'owner', 'kyc_status': 'approved'})
    open_disputes = mongo.db.disputes.count_documents({'status': {'$in': ['open', 'reviewing']}})

    commission_totals = list(mongo.db.commissions.aggregate([
        {
            '$group': {
                '_id': None,
                'total_commission': {'$sum': '$commission_amount'},
                'total_owner_payout': {'$sum': '$owner_payout'}
            }
        }
    ]))

    totals = commission_totals[0] if commission_totals else {
        'total_commission': 0,
        'total_owner_payout': 0
    }

    return jsonify({
        'pending_kyc': pending_kyc,
        'approved_owners': approved_owners,
        'open_disputes': open_disputes,
        'default_commission_percent': get_default_commission_percent(),
        'total_commission': int(totals.get('total_commission', 0) or 0),
        'total_owner_payout': int(totals.get('total_owner_payout', 0) or 0)
    })
