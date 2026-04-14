from flask import Blueprint, request, jsonify
from bson import ObjectId
import datetime
from config.db import mongo
from utils.auth_middleware import get_current_user, require_auth

equipment_bp = Blueprint('equipment', __name__)

def eq_to_dict(eq):
    return {
        '_id': str(eq['_id']),
        'name': eq.get('name'),
        'category': eq.get('category'),
        'image_url': eq.get('image_url', ''),
        'price_per_day': eq.get('price_per_day'),
        'location': eq.get('location'),
        'description': eq.get('description', ''),
        'brand': eq.get('brand', ''),
        'year': eq.get('year'),
        'owner_name': eq.get('owner_name', ''),
        'owner_phone': eq.get('owner_phone', ''),
        'owner_id': str(eq.get('owner_id', '')),
        'available': eq.get('available', True),
        'created_at': str(eq.get('created_at', ''))
    }


@equipment_bp.route('/', methods=['GET'])
def get_equipment():
    query = {}
    search = request.args.get('search')
    category = request.args.get('category')
    location = request.args.get('location')
    max_price = request.args.get('max_price')
    limit = int(request.args.get('limit', 50))
    sort = request.args.get('sort', 'newest')

    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'description': {'$regex': search, '$options': 'i'}}
        ]
    if category:
        query['category'] = category
    if location:
        query['location'] = {'$regex': location, '$options': 'i'}
    if max_price:
        query['price_per_day'] = {'$lte': int(max_price)}

    query['available'] = True

    sort_field = [('created_at', -1)]
    if sort == 'price_asc':
        sort_field = [('price_per_day', 1)]
    elif sort == 'price_desc':
        sort_field = [('price_per_day', -1)]

    equipment = list(mongo.db.equipment.find(query).sort(sort_field).limit(limit))
    return jsonify({'equipment': [eq_to_dict(e) for e in equipment], 'total': len(equipment)})


@equipment_bp.route('/<eq_id>', methods=['GET'])
def get_equipment_detail(eq_id):
    try:
        eq = mongo.db.equipment.find_one({'_id': ObjectId(eq_id)})
        if not eq:
            return jsonify({'error': 'Equipment not found'}), 404
        return jsonify({'equipment': eq_to_dict(eq)})
    except Exception:
        return jsonify({'error': 'Invalid ID'}), 400


@equipment_bp.route('/', methods=['POST'])
@require_auth
def create_equipment():
    user = get_current_user()
    data = request.get_json()

    if user.get('role', 'renter') != 'owner':
        return jsonify({'error': 'Only owners can list equipment'}), 403

    name = data.get('name', '').strip()
    category = data.get('category', '').strip()
    price_per_day = data.get('price_per_day')
    location = data.get('location', '').strip()

    if not all([name, category, price_per_day, location]):
        return jsonify({'error': 'Name, category, price, and location are required'}), 400

    doc = {
        'name': name,
        'category': category,
        'image_url': data.get('image_url', '').strip(),
        'price_per_day': int(price_per_day),
        'location': location,
        'description': data.get('description', ''),
        'brand': data.get('brand', ''),
        'year': data.get('year'),
        'owner_phone': data.get('owner_phone', user.get('phone', '')),
        'owner_name': user.get('name', ''),
        'owner_id': user['_id'],
        'available': True,
        'created_at': datetime.datetime.utcnow()
    }
    result = mongo.db.equipment.insert_one(doc)
    doc['_id'] = result.inserted_id
    return jsonify({'equipment': eq_to_dict(doc)}), 201


@equipment_bp.route('/my', methods=['GET'])
@require_auth
def my_equipment():
    user = get_current_user()
    equipment = list(mongo.db.equipment.find({'owner_id': user['_id']}))
    return jsonify({'equipment': [eq_to_dict(e) for e in equipment]})


@equipment_bp.route('/<eq_id>', methods=['PUT'])
@require_auth
def update_equipment(eq_id):
    user = get_current_user()
    data = request.get_json()
    try:
        eq = mongo.db.equipment.find_one({'_id': ObjectId(eq_id)})
        if not eq:
            return jsonify({'error': 'Not found'}), 404
        if str(eq['owner_id']) != str(user['_id']):
            return jsonify({'error': 'Unauthorized'}), 403
        update_fields = {k: v for k, v in data.items() if k not in ['_id', 'owner_id']}
        mongo.db.equipment.update_one({'_id': ObjectId(eq_id)}, {'$set': update_fields})
        updated = mongo.db.equipment.find_one({'_id': ObjectId(eq_id)})
        return jsonify({'equipment': eq_to_dict(updated)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@equipment_bp.route('/<eq_id>', methods=['DELETE'])
@require_auth
def delete_equipment(eq_id):
    user = get_current_user()
    try:
        eq = mongo.db.equipment.find_one({'_id': ObjectId(eq_id)})
        if not eq:
            return jsonify({'error': 'Not found'}), 404
        if str(eq['owner_id']) != str(user['_id']):
            return jsonify({'error': 'Unauthorized'}), 403
        mongo.db.equipment.delete_one({'_id': ObjectId(eq_id)})
        return jsonify({'message': 'Equipment deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
