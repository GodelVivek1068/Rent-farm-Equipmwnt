from flask import Blueprint, request, jsonify
from bson import ObjectId
import datetime
import hashlib
import hmac
import os
import razorpay
from config.db import mongo
from utils.auth_middleware import get_current_user, require_auth

rentals_bp = Blueprint('rentals', __name__)

def rental_to_dict(r):
    return {
        '_id': str(r['_id']),
        'equipment_id': str(r.get('equipment_id', '')),
        'equipment_name': r.get('equipment_name', ''),
        'category': r.get('category', 'tractor'),
        'renter_id': str(r.get('renter_id', '')),
        'renter_name': r.get('renter_name', ''),
        'owner_id': str(r.get('owner_id', '')),
        'start_date': r.get('start_date', ''),
        'end_date': r.get('end_date', ''),
        'delivery_address': r.get('delivery_address', ''),
        'notes': r.get('notes', ''),
        'total_amount': r.get('total_amount', 0),
        'payment_status': r.get('payment_status', 'pending'),
        'payment_id': r.get('payment_id', ''),
        'payment_order_id': r.get('payment_order_id', ''),
        'status': r.get('status', 'pending'),
        'created_at': str(r.get('created_at', ''))
    }


def _validate_booking_payload(data):
    equipment_id = data.get('equipment_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    delivery_address = data.get('delivery_address', '').strip()
    notes = data.get('notes', '')
    total_amount = int(data.get('total_amount', 0) or 0)
    if not all([equipment_id, start_date, end_date, delivery_address]):
        return None, 'equipment_id, start_date, end_date, and delivery_address are required'
    if total_amount <= 0:
        return None, 'total_amount must be greater than 0'
    return {
        'equipment_id': equipment_id,
        'start_date': start_date,
        'end_date': end_date,
        'delivery_address': delivery_address,
        'notes': notes,
        'total_amount': total_amount
    }, None


def _get_equipment_for_booking(equipment_id, user_id):
    eq = mongo.db.equipment.find_one({'_id': ObjectId(equipment_id)})
    if not eq:
        return None, 'Equipment not found', 404
    if str(eq.get('owner_id')) == str(user_id):
        return None, 'You cannot rent your own equipment', 400
    if eq.get('available', True) is False:
        return None, 'This equipment is currently unavailable', 400
    return eq, None, None


def _create_rental_doc(user, eq, booking, payment):
    owner_id = eq.get('owner_id')
    return {
        'equipment_id': ObjectId(booking['equipment_id']),
        'equipment_name': eq['name'],
        'category': eq.get('category', 'tractor'),
        'renter_id': user['_id'],
        'renter_name': user.get('name', ''),
        'owner_id': owner_id,
        'owner_id_str': str(owner_id) if owner_id is not None else '',
        'start_date': booking['start_date'],
        'end_date': booking['end_date'],
        'delivery_address': booking['delivery_address'],
        'notes': booking['notes'],
        'total_amount': booking['total_amount'],
        'payment_status': 'paid',
        'payment_id': payment.get('payment_id', ''),
        'payment_order_id': payment.get('order_id', ''),
        'status': 'pending',
        'created_at': datetime.datetime.utcnow()
    }


def _owner_equipment_ids(user_id):
    equipment_ids = []
    user_id_str = str(user_id)
    equipment_query = {
        '$or': [
            {'owner_id': user_id},
            {'owner_id': user_id_str},
            {'owner_id_str': user_id_str}
        ]
    }
    for equipment in mongo.db.equipment.find(equipment_query, {'_id': 1}):
        equipment_ids.append(equipment['_id'])
    return equipment_ids


@rentals_bp.route('/', methods=['POST'])
@require_auth
def create_rental():
    user = get_current_user()
    data = request.get_json()

    booking, error = _validate_booking_payload(data)
    if error:
        return jsonify({'error': error}), 400

    # Keep existing endpoint functional for fallback/manual testing without Razorpay.
    payment_verified = bool(data.get('payment_verified', False))
    if not payment_verified:
        return jsonify({'error': 'Payment is required before booking confirmation'}), 400

    try:
        eq, eq_error, eq_status = _get_equipment_for_booking(booking['equipment_id'], user['_id'])
        if eq_error:
            return jsonify({'error': eq_error}), eq_status

        doc = _create_rental_doc(user, eq, booking, {
            'payment_id': data.get('payment_id', ''),
            'order_id': data.get('payment_order_id', '')
        })
        result = mongo.db.rentals.insert_one(doc)
        doc['_id'] = result.inserted_id
        return jsonify({'rental': rental_to_dict(doc)}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@rentals_bp.route('/payment/order', methods=['POST'])
@require_auth
def create_payment_order():
    user = get_current_user()
    data = request.get_json()
    booking, error = _validate_booking_payload(data)
    if error:
        return jsonify({'error': error}), 400

    key_id = os.getenv('RAZORPAY_KEY_ID', '').strip()
    key_secret = os.getenv('RAZORPAY_KEY_SECRET', '').strip()
    if not key_id or not key_secret:
        return jsonify({'error': 'Payment gateway is not configured on server'}), 500

    try:
        _, eq_error, eq_status = _get_equipment_for_booking(booking['equipment_id'], user['_id'])
        if eq_error:
            return jsonify({'error': eq_error}), eq_status

        client = razorpay.Client(auth=(key_id, key_secret))
        receipt = f"rent_{str(user['_id'])[-6:]}_{int(datetime.datetime.utcnow().timestamp())}"
        order = client.order.create({
            'amount': booking['total_amount'] * 100,
            'currency': 'INR',
            'receipt': receipt,
            'notes': {
                'equipment_id': booking['equipment_id'],
                'start_date': booking['start_date'],
                'end_date': booking['end_date']
            }
        })

        return jsonify({
            'order_id': order.get('id'),
            'amount': order.get('amount'),
            'currency': order.get('currency', 'INR'),
            'key_id': key_id,
            'prefill': {
                'name': user.get('name', ''),
                'email': user.get('email', ''),
                'contact': user.get('phone', '')
            }
        })
    except Exception as e:
        return jsonify({'error': f'Failed to create payment order: {str(e)}'}), 400


@rentals_bp.route('/payment/verify', methods=['POST'])
@require_auth
def verify_payment_and_create_rental():
    user = get_current_user()
    data = request.get_json()

    key_secret = os.getenv('RAZORPAY_KEY_SECRET', '').strip()
    if not key_secret:
        return jsonify({'error': 'Payment gateway is not configured on server'}), 500

    booking, error = _validate_booking_payload(data)
    if error:
        return jsonify({'error': error}), 400

    order_id = data.get('razorpay_order_id', '').strip()
    payment_id = data.get('razorpay_payment_id', '').strip()
    signature = data.get('razorpay_signature', '').strip()
    if not order_id or not payment_id or not signature:
        return jsonify({'error': 'Missing payment verification fields'}), 400

    try:
        generated = hmac.new(
            key_secret.encode('utf-8'),
            f'{order_id}|{payment_id}'.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(generated, signature):
            return jsonify({'error': 'Payment signature verification failed'}), 400

        eq, eq_error, eq_status = _get_equipment_for_booking(booking['equipment_id'], user['_id'])
        if eq_error:
            return jsonify({'error': eq_error}), eq_status

        doc = _create_rental_doc(user, eq, booking, {
            'payment_id': payment_id,
            'order_id': order_id
        })
        result = mongo.db.rentals.insert_one(doc)
        doc['_id'] = result.inserted_id
        return jsonify({'rental': rental_to_dict(doc)}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@rentals_bp.route('/my', methods=['GET'])
@require_auth
def my_rentals():
    user = get_current_user()
    rentals = list(mongo.db.rentals.find({'renter_id': user['_id']}).sort('created_at', -1))
    return jsonify({'rentals': [rental_to_dict(r) for r in rentals]})


@rentals_bp.route('/owner', methods=['GET'])
@require_auth
def owner_rentals():
    """Rentals for equipment owned by this user"""
    user = get_current_user()
    user_id_str = str(user['_id'])
    owner_equipment_ids = _owner_equipment_ids(user['_id'])

    query = {
        '$or': [
            {'owner_id': user['_id']},
            {'owner_id': user_id_str},
            {'owner_id_str': user_id_str}
        ]
    }
    if owner_equipment_ids:
        query['$or'].append({'equipment_id': {'$in': owner_equipment_ids}})

    rentals = list(mongo.db.rentals.find(query).sort('created_at', -1))
    return jsonify({'rentals': [rental_to_dict(r) for r in rentals]})


@rentals_bp.route('/<rental_id>/status', methods=['PUT'])
@require_auth
def update_rental_status(rental_id):
    user = get_current_user()
    data = request.get_json()
    status = data.get('status')
    if status not in ['pending', 'confirmed', 'cancelled', 'completed']:
        return jsonify({'error': 'Invalid status'}), 400
    try:
        rental = mongo.db.rentals.find_one({'_id': ObjectId(rental_id)})
        if not rental:
            return jsonify({'error': 'Not found'}), 404
        # Owner can confirm/cancel, renter can cancel
        if str(rental['owner_id']) != str(user['_id']) and str(rental['renter_id']) != str(user['_id']):
            return jsonify({'error': 'Unauthorized'}), 403
        mongo.db.rentals.update_one({'_id': ObjectId(rental_id)}, {'$set': {'status': status}})
        updated = mongo.db.rentals.find_one({'_id': ObjectId(rental_id)})
        return jsonify({'rental': rental_to_dict(updated)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
