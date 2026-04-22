from flask import Blueprint, request, jsonify
from bson import ObjectId
import datetime
import math
import re
from config.db import mongo
from utils.auth_middleware import get_current_user, require_auth

equipment_bp = Blueprint('equipment', __name__)
ACTIVE_RENTAL_STATUSES = {'pending', 'confirmed'}

# Seeded coordinates for common Maharashtra cities/districts used by this project.
LOCATION_COORDS = {
    'pune': (18.5204, 73.8567),
    'nashik': (19.9975, 73.7898),
    'solapur': (17.6599, 75.9064),
    'kolhapur': (16.7050, 74.2433),
    'latur': (18.4088, 76.5604),
    'aurangabad': (19.8762, 75.3433),
    'satara': (17.6805, 74.0183),
    'jalgaon': (21.0077, 75.5626),
    'sangli': (16.8524, 74.5815),
    'ahilyanagar': (19.0952, 74.7496),
    'ahmednagar': (19.0952, 74.7496)
}


def _safe_float(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_text(value):
    return str(value or '').strip()


def _normalize_location_key(value):
    text = _normalize_text(value).lower()
    text = re.sub(r'[^a-z0-9\s]+', ' ', text)
    return ' '.join(text.split())


def _extract_city_district(location):
    parts = [part.strip() for part in str(location or '').split(',') if part.strip()]
    if not parts:
        return '', ''
    city = parts[0]
    district = parts[1] if len(parts) > 1 else parts[0]
    return city, district


def _coords_from_text(value):
    normalized = _normalize_location_key(value)
    if not normalized:
        return None, None

    if normalized in LOCATION_COORDS:
        return LOCATION_COORDS[normalized]

    for key, coords in LOCATION_COORDS.items():
        if key in normalized or normalized in key:
            return coords

    tokens = normalized.split()
    for token in tokens:
        if token in LOCATION_COORDS:
            return LOCATION_COORDS[token]
    return None, None


def _resolve_coordinates(location='', city='', district='', latitude=None, longitude=None):
    lat = _safe_float(latitude)
    lng = _safe_float(longitude)

    if lat is not None and lng is not None:
        return lat, lng

    for candidate in [city, district, location]:
        inferred_lat, inferred_lng = _coords_from_text(candidate)
        if inferred_lat is not None and inferred_lng is not None:
            return inferred_lat, inferred_lng

    return lat, lng


def _haversine_km(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return round(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def _equipment_has_active_booking(eq_id):
    eq_variants = []
    if isinstance(eq_id, ObjectId):
        eq_variants = [eq_id, str(eq_id)]
    else:
        eq_id_str = str(eq_id or '').strip()
        if not eq_id_str:
            return False
        eq_variants.append(eq_id_str)
        try:
            eq_variants.append(ObjectId(eq_id_str))
        except Exception:
            pass

    return mongo.db.rentals.find_one({
        'equipment_id': {'$in': eq_variants},
        'status': {'$in': list(ACTIVE_RENTAL_STATUSES)}
    }) is not None

def eq_to_dict(eq):
    lat, lng = _resolve_coordinates(
        eq.get('location', ''),
        eq.get('city', ''),
        eq.get('district', ''),
        eq.get('latitude'),
        eq.get('longitude')
    )
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
        'city': eq.get('city', ''),
        'district': eq.get('district', ''),
        'latitude': lat,
        'longitude': lng,
        'owner_name': eq.get('owner_name', ''),
        'owner_phone': eq.get('owner_phone', ''),
        'owner_id': str(eq.get('owner_id', '')),
        'available': bool(eq.get('available', True)) and not _equipment_has_active_booking(eq['_id']),
        'created_at': str(eq.get('created_at', ''))
    }


def _location_tokens(location):
    text = str(location or '').strip().lower()
    # Keep only meaningful tokens so fuzzy matching is less noisy.
    tokens = [token for token in re.split(r'[^a-z0-9]+', text) if len(token) >= 3]
    return list(dict.fromkeys(tokens))


def _location_score(base_location, candidate_location):
    base_tokens = _location_tokens(base_location)
    candidate_tokens = _location_tokens(candidate_location)
    if not base_tokens or not candidate_tokens:
        return 0
    base_set = set(base_tokens)
    candidate_set = set(candidate_tokens)
    overlap = base_set.intersection(candidate_set)
    if not overlap:
        return 0
    # Reward stronger overlap but keep score simple and deterministic.
    return (len(overlap) * 10) + (5 if base_tokens[0] in candidate_set else 0)


def _with_distance(eq_doc, origin_lat=None, origin_lng=None):
    payload = eq_to_dict(eq_doc)
    distance_km = _haversine_km(origin_lat, origin_lng, payload.get('latitude'), payload.get('longitude'))
    if distance_km is not None:
        payload['distance_km'] = distance_km
    return payload


def _sort_with_distance(docs, origin_lat, origin_lng):
    def key_fn(eq_doc):
        lat, lng = _resolve_coordinates(
            eq_doc.get('location', ''),
            eq_doc.get('city', ''),
            eq_doc.get('district', ''),
            eq_doc.get('latitude'),
            eq_doc.get('longitude')
        )
        distance = _haversine_km(origin_lat, origin_lng, lat, lng)
        if distance is None:
            return (1, float('inf'))
        return (0, distance)

    return sorted(docs, key=key_fn)


@equipment_bp.route('/', methods=['GET'])
def get_equipment():
    try:
        query = {}
        search = request.args.get('search')
        category = request.args.get('category')
        location = request.args.get('location')
        max_price = request.args.get('max_price')
        limit = int(request.args.get('limit', 50))
        sort = request.args.get('sort', 'newest')
        origin_lat = _safe_float(request.args.get('lat'))
        origin_lng = _safe_float(request.args.get('lng'))

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

        sort_field = [('created_at', -1)]
        if sort == 'price_asc':
            sort_field = [('price_per_day', 1)]
        elif sort == 'price_desc':
            sort_field = [('price_per_day', -1)]

        if sort == 'distance' and origin_lat is not None and origin_lng is not None:
            equipment_docs = _sort_with_distance(list(mongo.db.equipment.find(query).limit(limit)), origin_lat, origin_lng)
        else:
            equipment_docs = list(mongo.db.equipment.find(query).sort(sort_field).limit(limit))

        equipment = [_with_distance(eq_doc, origin_lat, origin_lng) for eq_doc in equipment_docs]

        return jsonify({'equipment': equipment, 'total': len(equipment)})
    except Exception as e:
        return jsonify({
            'error': 'Failed to load equipment. Check MONGO_URI and make sure MongoDB is running and reachable.',
            'details': str(e)
        }), 503


@equipment_bp.route('/<eq_id>', methods=['GET'])
def get_equipment_detail(eq_id):
    try:
        eq = mongo.db.equipment.find_one({'_id': ObjectId(eq_id)})
        if not eq:
            return jsonify({'error': 'Equipment not found'}), 404
        return jsonify({'equipment': eq_to_dict(eq)})
    except Exception:
        return jsonify({'error': 'Invalid ID'}), 400


@equipment_bp.route('/<eq_id>/alternatives', methods=['GET'])
def get_equipment_alternatives(eq_id):
    try:
        base_eq = mongo.db.equipment.find_one({'_id': ObjectId(eq_id)})
        if not base_eq:
            return jsonify({'error': 'Equipment not found'}), 404

        limit = int(request.args.get('limit', 6))
        limit = max(1, min(limit, 20))
        owner_id = base_eq.get('owner_id')
        owner_id_str = str(owner_id) if owner_id is not None else ''
        base_lat, base_lng = _resolve_coordinates(
            base_eq.get('location', ''),
            base_eq.get('city', ''),
            base_eq.get('district', ''),
            base_eq.get('latitude'),
            base_eq.get('longitude')
        )

        query = {
            '_id': {'$ne': base_eq['_id']},
            'category': base_eq.get('category'),
            'available': True,
            '$and': [
                {
                    '$or': [
                        {'owner_id': {'$ne': owner_id}},
                        {'owner_id': {'$exists': False}}
                    ]
                },
                {
                    '$or': [
                        {'owner_id_str': {'$ne': owner_id_str}},
                        {'owner_id_str': {'$exists': False}}
                    ]
                }
            ]
        }

        candidates = list(mongo.db.equipment.find(query).limit(120))
        scored = []
        for eq in candidates:
            candidate_lat, candidate_lng = _resolve_coordinates(
                eq.get('location', ''),
                eq.get('city', ''),
                eq.get('district', ''),
                eq.get('latitude'),
                eq.get('longitude')
            )
            distance_km = _haversine_km(base_lat, base_lng, candidate_lat, candidate_lng)
            location_score = _location_score(base_eq.get('location', ''), eq.get('location', ''))

            # True distance first when coordinates are available; fallback to token overlap.
            if distance_km is not None:
                rank_key = (0, distance_km, int(eq.get('price_per_day') or 0), -location_score)
            else:
                rank_key = (1, 99999, int(eq.get('price_per_day') or 0), -location_score)
            scored.append((rank_key, eq, distance_km))

        scored.sort(key=lambda item: item[0])
        alternatives = []
        for _, eq_doc, distance_km in scored[:limit]:
            item = eq_to_dict(eq_doc)
            if not item.get('available', True):
                continue
            if distance_km is not None:
                item['distance_km'] = distance_km
            alternatives.append(item)

        return jsonify({
            'base_equipment_id': str(base_eq['_id']),
            'base_location': base_eq.get('location', ''),
            'base_latitude': base_lat,
            'base_longitude': base_lng,
            'category': base_eq.get('category', ''),
            'alternatives': alternatives,
            'total': len(alternatives)
        })
    except Exception:
        return jsonify({'error': 'Invalid ID'}), 400


@equipment_bp.route('/alternatives', methods=['GET'])
def get_listing_alternatives():
    """Fallback suggestions for listing page when exact filters return no result."""
    try:
        search = _normalize_text(request.args.get('search', ''))
        category = _normalize_text(request.args.get('category', ''))
        location = _normalize_text(request.args.get('location', ''))
        max_price = request.args.get('max_price')
        limit = int(request.args.get('limit', 8))
        limit = max(1, min(limit, 20))

        origin_lat = _safe_float(request.args.get('lat'))
        origin_lng = _safe_float(request.args.get('lng'))
        if origin_lat is None or origin_lng is None:
            origin_lat, origin_lng = _resolve_coordinates(location)

        search_tokens = _location_tokens(search)
        location_tokens = _location_tokens(location)

        base_query = {'available': True}
        if category:
            base_query['category'] = category
        if max_price:
            base_query['price_per_day'] = {'$lte': int(max_price)}

        docs = list(mongo.db.equipment.find(base_query).limit(250))
        ranked = []
        for eq in docs:
            candidate_text = f"{eq.get('name', '')} {eq.get('description', '')} {eq.get('category', '')}".lower()
            candidate_location = eq.get('location', '')
            relevance = 0

            for token in search_tokens:
                if token in candidate_text:
                    relevance += 10
            for token in location_tokens:
                if token in str(candidate_location).lower():
                    relevance += 8

            if category and eq.get('category') == category:
                relevance += 12

            eq_lat, eq_lng = _resolve_coordinates(
                eq.get('location', ''),
                eq.get('city', ''),
                eq.get('district', ''),
                eq.get('latitude'),
                eq.get('longitude')
            )
            distance_km = _haversine_km(origin_lat, origin_lng, eq_lat, eq_lng)
            price = int(eq.get('price_per_day') or 0)

            if distance_km is not None:
                rank = (0, distance_km, -relevance, price)
            else:
                rank = (1, 99999, -relevance, price)
            ranked.append((rank, eq, distance_km))

        ranked.sort(key=lambda item: item[0])
        alternatives = []
        for _, eq_doc, distance_km in ranked[:limit]:
            item = eq_to_dict(eq_doc)
            if not item.get('available', True):
                continue
            if distance_km is not None:
                item['distance_km'] = distance_km
            alternatives.append(item)

        return jsonify({
            'alternatives': alternatives,
            'total': len(alternatives)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


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
    city = _normalize_text(data.get('city', ''))
    district = _normalize_text(data.get('district', ''))
    latitude = _safe_float(data.get('latitude'))
    longitude = _safe_float(data.get('longitude'))

    if not city or not district:
        inferred_city, inferred_district = _extract_city_district(location)
        city = city or inferred_city
        district = district or inferred_district

    latitude, longitude = _resolve_coordinates(location, city, district, latitude, longitude)

    if not all([name, category, price_per_day, location]):
        return jsonify({'error': 'Name, category, price, and location are required'}), 400

    doc = {
        'name': name,
        'category': category,
        'image_url': data.get('image_url', '').strip(),
        'price_per_day': int(price_per_day),
        'location': location,
        'city': city,
        'district': district,
        'latitude': latitude,
        'longitude': longitude,
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

        if any(field in data for field in ['location', 'city', 'district', 'latitude', 'longitude']):
            location = _normalize_text(data.get('location', eq.get('location', '')))
            city = _normalize_text(data.get('city', eq.get('city', '')))
            district = _normalize_text(data.get('district', eq.get('district', '')))
            latitude = _safe_float(data.get('latitude', eq.get('latitude')))
            longitude = _safe_float(data.get('longitude', eq.get('longitude')))

            if not city or not district:
                inferred_city, inferred_district = _extract_city_district(location)
                city = city or inferred_city
                district = district or inferred_district

            latitude, longitude = _resolve_coordinates(location, city, district, latitude, longitude)
            update_fields['location'] = location
            update_fields['city'] = city
            update_fields['district'] = district
            update_fields['latitude'] = latitude
            update_fields['longitude'] = longitude

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
