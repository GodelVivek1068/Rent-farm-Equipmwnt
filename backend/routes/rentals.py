from flask import Blueprint, request, jsonify
from bson import ObjectId
import datetime
import hashlib
import hmac
import os
import razorpay
from config.db import mongo
from utils.auth_middleware import get_current_user, require_auth
from routes.admin_marketplace import apply_commission_for_rental

rentals_bp = Blueprint('rentals', __name__)
ACTIVE_RENTAL_STATUSES = {'pending', 'confirmed'}


def _equipment_id_variants(equipment_id):
    variants = []
    if isinstance(equipment_id, ObjectId):
        variants.append(equipment_id)
        variants.append(str(equipment_id))
        return variants

    equipment_id_str = str(equipment_id or '').strip()
    if not equipment_id_str:
        return variants

    variants.append(equipment_id_str)
    try:
        variants.append(ObjectId(equipment_id_str))
    except Exception:
        pass
    return variants


def _expire_overdue_rentals_for_equipment(equipment_id):
    equipment_id_variants = _equipment_id_variants(equipment_id)
    if not equipment_id_variants:
        return 0

    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    base_query = {
        'equipment_id': {'$in': equipment_id_variants},
        'status': {'$in': list(ACTIVE_RENTAL_STATUSES)},
        'end_date': {'$lt': today}
    }

    confirm_to_complete = mongo.db.rentals.update_many(
        {**base_query, 'status': 'confirmed'},
        {
            '$set': {
                'status': 'completed',
                'auto_completed_at': datetime.datetime.utcnow()
            }
        }
    )
    pending_to_cancel = mongo.db.rentals.update_many(
        {**base_query, 'status': 'pending'},
        {
            '$set': {
                'status': 'cancelled',
                'cancel_reason': 'Booking auto-cancelled after rental end date passed',
                'cancelled_at': datetime.datetime.utcnow()
            }
        }
    )

    return (confirm_to_complete.modified_count or 0) + (pending_to_cancel.modified_count or 0)


def _sync_equipment_availability(equipment_id):
    equipment_id_variants = _equipment_id_variants(equipment_id)
    if not equipment_id_variants:
        return

    _expire_overdue_rentals_for_equipment(equipment_id)

    equipment_object_id = None
    for value in equipment_id_variants:
        if isinstance(value, ObjectId):
            equipment_object_id = value
            break
    if equipment_object_id is None:
        return

    active_booking = mongo.db.rentals.find_one({
        'equipment_id': {'$in': equipment_id_variants},
        'status': {'$in': list(ACTIVE_RENTAL_STATUSES)}
    })
    mongo.db.equipment.update_one(
        {'_id': equipment_object_id},
        {'$set': {'available': active_booking is None}}
    )

def rental_to_dict(r):
    commission = r.get('commission', {}) if isinstance(r.get('commission', {}), dict) else {}
    return {
        '_id': str(r['_id']),
        'equipment_id': str(r.get('equipment_id', '')),
        'equipment_name': r.get('equipment_name', ''),
        'category': r.get('category', 'tractor'),
        'renter_id': str(r.get('renter_id', '')),
        'renter_name': r.get('renter_name', ''),
        'owner_id': str(r.get('owner_id', '')),
        'owner_name': r.get('owner_name', ''),
        'owner_phone': r.get('owner_phone', ''),
        'start_date': r.get('start_date', ''),
        'end_date': r.get('end_date', ''),
        'delivery_address': r.get('delivery_address', ''),
        'notes': r.get('notes', ''),
        'total_amount': r.get('total_amount', 0),
        'payment_status': r.get('payment_status', 'pending'),
        'payment_id': r.get('payment_id', ''),
        'payment_order_id': r.get('payment_order_id', ''),
        'status': r.get('status', 'pending'),
        'farmer_rating': int(r.get('farmer_rating', 0) or 0),
        'farmer_review': r.get('farmer_review', ''),
        'rated_at': str(r.get('rated_at', '')),
        'commission': {
            'commission_percent': commission.get('commission_percent', 0),
            'commission_amount': commission.get('commission_amount', 0),
            'owner_payout': commission.get('owner_payout', 0)
        },
        'created_at': str(r.get('created_at', ''))
    }


def _recalculate_equipment_rating(equipment_id):
    eq_variants = _equipment_id_variants(equipment_id)
    if not eq_variants:
        return

    ratings = []
    for rental in mongo.db.rentals.find({
        'equipment_id': {'$in': eq_variants},
        'status': 'completed',
        'farmer_rating': {'$gte': 1, '$lte': 5}
    }, {'farmer_rating': 1}):
        try:
            ratings.append(int(rental.get('farmer_rating', 0)))
        except (TypeError, ValueError):
            continue

    rating_count = len(ratings)
    rating_avg = round(sum(ratings) / rating_count, 2) if rating_count else 0

    equipment_object_id = None
    for value in eq_variants:
        if isinstance(value, ObjectId):
            equipment_object_id = value
            break

    if equipment_object_id is None:
        return

    mongo.db.equipment.update_one(
        {'_id': equipment_object_id},
        {'$set': {'rating_avg': rating_avg, 'rating_count': rating_count}}
    )


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

    _sync_equipment_availability(eq['_id'])
    eq = mongo.db.equipment.find_one({'_id': eq['_id']}) or eq

    if str(eq.get('owner_id')) == str(user_id):
        return None, 'You cannot rent your own equipment', 400
    if eq.get('available', True) is False:
        return None, 'This equipment is currently unavailable', 400
    return eq, None, None


def _create_rental_doc(user, eq, booking, payment):
    owner_id = eq.get('owner_id')
    owner_name = eq.get('owner_name', '')
    owner_phone = eq.get('owner_phone', '')
    return {
        'equipment_id': ObjectId(booking['equipment_id']),
        'equipment_name': eq['name'],
        'category': eq.get('category', 'tractor'),
        'renter_id': user['_id'],
        'renter_name': user.get('name', ''),
        'owner_id': owner_id,
        'owner_id_str': str(owner_id) if owner_id is not None else '',
        'owner_name': owner_name,
        'owner_phone': owner_phone,
        'start_date': booking['start_date'],
        'end_date': booking['end_date'],
        'delivery_address': booking['delivery_address'],
        'notes': booking['notes'],
        'total_amount': booking['total_amount'],
        'payment_status': 'paid',
        'payment_id': payment.get('payment_id', ''),
        'payment_order_id': payment.get('order_id', ''),
        'status': 'pending',
        'commission': {
            'commission_percent': 0,
            'commission_amount': 0,
            'owner_payout': 0
        },
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
        eq_id = equipment.get('_id')
        if not eq_id:
            continue
        equipment_ids.extend(_equipment_id_variants(eq_id))

    # Preserve order while removing duplicates.
    unique_ids = []
    seen = set()
    for value in equipment_ids:
        key = (type(value).__name__, str(value))
        if key in seen:
            continue
        seen.add(key)
        unique_ids.append(value)
    return unique_ids


def _rental_belongs_to_owner(rental, user_id, owner_equipment_id_strs, owner_name='', owner_phone=''):
    user_id_str = str(user_id)
    user_name = str(owner_name or '').strip().lower()
    user_phone = str(owner_phone or '').strip()

    rental_owner_id = rental.get('owner_id')
    rental_owner_id_str = rental.get('owner_id_str')
    if str(rental_owner_id) == user_id_str:
        return True
    if str(rental_owner_id_str) == user_id_str:
        return True

    rental_equipment_id = rental.get('equipment_id')
    if str(rental_equipment_id) in owner_equipment_id_strs:
        return True

    rental_equipment_id_str = rental.get('equipment_id_str')
    if str(rental_equipment_id_str) in owner_equipment_id_strs:
        return True

    rental_owner_name = str(rental.get('owner_name', '')).strip().lower()
    if user_name and rental_owner_name and rental_owner_name == user_name:
        return True

    rental_owner_phone = str(rental.get('owner_phone', '')).strip()
    if user_phone and rental_owner_phone and rental_owner_phone == user_phone:
        return True

    return False


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
        _sync_equipment_availability(doc['equipment_id'])
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
        _sync_equipment_availability(doc['equipment_id'])
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
    owner_equipment_ids = _owner_equipment_ids(user['_id'])
    owner_equipment_id_strs = {str(value) for value in owner_equipment_ids}
    user_name = str(user.get('name', '')).strip().lower()
    user_phone = str(user.get('phone', '')).strip()

    # Fetch then filter to tolerate legacy ObjectId/string field mismatches.
    rentals = []
    for rental in mongo.db.rentals.find().sort('created_at', -1):
        belongs_to_owner = _rental_belongs_to_owner(rental, user['_id'], owner_equipment_id_strs, user_name, user_phone)
        if not belongs_to_owner:
            continue

        # Backfill legacy records so older bookings remain visible after the first match.
        rental_owner_name = str(rental.get('owner_name', '')).strip().lower()
        rental_owner_phone = str(rental.get('owner_phone', '')).strip()
        if not rental.get('owner_id') or not rental.get('owner_id_str') or not rental_owner_name or not rental_owner_phone:
            mongo.db.rentals.update_one(
                {'_id': rental['_id']},
                {
                    '$set': {
                        'owner_id': user['_id'],
                        'owner_id_str': str(user['_id']),
                        'owner_name': user.get('name', ''),
                        'owner_phone': user.get('phone', '')
                    }
                }
            )
            rental['owner_id'] = user['_id']
            rental['owner_id_str'] = str(user['_id'])
            rental['owner_name'] = user.get('name', '')
            rental['owner_phone'] = user.get('phone', '')

        rentals.append(rental)

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
        owner_equipment_id_strs = {str(value) for value in _owner_equipment_ids(user['_id'])}
        is_owner = _rental_belongs_to_owner(
            rental,
            user['_id'],
            owner_equipment_id_strs,
            user.get('name', ''),
            user.get('phone', '')
        )
        is_renter = str(rental['renter_id']) == str(user['_id'])
        if not is_owner and not is_renter:
            return jsonify({'error': 'Unauthorized'}), 403

        # Renter is only allowed to cancel their own booking request.
        if is_renter and not is_owner and status != 'cancelled':
            return jsonify({'error': 'Renter can only cancel booking'}), 403

        # Owner should not set booking back to pending manually.
        if is_owner and status == 'pending':
            return jsonify({'error': 'Owner cannot set status back to pending'}), 400

        update_fields = {'status': status}
        if status == 'completed':
            commission_doc = apply_commission_for_rental(rental, actor_id=str(user['_id']))
            if commission_doc:
                update_fields['commission'] = {
                    'commission_percent': commission_doc.get('commission_percent', 0),
                    'commission_amount': commission_doc.get('commission_amount', 0),
                    'owner_payout': commission_doc.get('owner_payout', 0)
                }

        mongo.db.rentals.update_one({'_id': ObjectId(rental_id)}, {'$set': update_fields})

        auto_cancelled_count = 0
        if is_owner and status == 'confirmed':
            equipment_variants = _equipment_id_variants(rental.get('equipment_id'))
            if equipment_variants:
                auto_cancel_result = mongo.db.rentals.update_many(
                    {
                        '_id': {'$ne': ObjectId(rental_id)},
                        'equipment_id': {'$in': equipment_variants},
                        'status': 'pending'
                    },
                    {
                        '$set': {
                            'status': 'cancelled',
                            'cancel_reason': 'Another booking was confirmed by owner',
                            'cancelled_at': datetime.datetime.utcnow()
                        }
                    }
                )
                auto_cancelled_count = auto_cancel_result.modified_count

        updated = mongo.db.rentals.find_one({'_id': ObjectId(rental_id)})
        _sync_equipment_availability(updated['equipment_id'])
        return jsonify({
            'rental': rental_to_dict(updated),
            'auto_cancelled_pending_requests': auto_cancelled_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@rentals_bp.route('/<rental_id>/rating', methods=['PUT'])
@require_auth
def rate_rental(rental_id):
    user = get_current_user()
    data = request.get_json() or {}

    try:
        rental = mongo.db.rentals.find_one({'_id': ObjectId(rental_id)})
    except Exception:
        return jsonify({'error': 'Invalid rental ID'}), 400

    if not rental:
        return jsonify({'error': 'Rental not found'}), 404

    if str(rental.get('renter_id', '')) != str(user.get('_id', '')):
        return jsonify({'error': 'Only renter can rate this equipment'}), 403

    if str(rental.get('status', '')).lower() != 'completed':
        return jsonify({'error': 'You can rate equipment only after rental is completed'}), 400

    try:
        rating = int(data.get('rating', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Rating must be a number between 1 and 5'}), 400

    if rating < 1 or rating > 5:
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400

    review = str(data.get('review', '')).strip()
    if len(review) > 500:
        return jsonify({'error': 'Review cannot exceed 500 characters'}), 400

    update_doc = {
        'farmer_rating': rating,
        'farmer_review': review,
        'rated_at': datetime.datetime.utcnow()
    }
    mongo.db.rentals.update_one({'_id': rental['_id']}, {'$set': update_doc})

    _recalculate_equipment_rating(rental.get('equipment_id'))

    updated = mongo.db.rentals.find_one({'_id': rental['_id']})
    return jsonify({'rental': rental_to_dict(updated)})
