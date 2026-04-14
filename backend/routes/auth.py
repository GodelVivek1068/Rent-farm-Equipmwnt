from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from config.db import mongo

auth_bp = Blueprint('auth', __name__)

def generate_token(user_id):
    payload = {
        'user_id': str(user_id),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    location = data.get('location', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'renter')  # 'renter' or 'owner'

    if not all([name, email, phone, password]):
        return jsonify({'error': 'All fields are required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    # Check if user exists
    existing = mongo.db.users.find_one({'email': email})
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    hashed_pw = generate_password_hash(password)
    user_doc = {
        'name': name,
        'email': email,
        'phone': phone,
        'location': location,
        'password': hashed_pw,
        'role': role,
        'created_at': datetime.datetime.utcnow()
    }
    result = mongo.db.users.insert_one(user_doc)
    token = generate_token(result.inserted_id)

    return jsonify({
        'token': token,
        'user': {
            'id': str(result.inserted_id),
            'name': name,
            'email': email,
            'role': role,
            'phone': phone,
            'location': location
        }
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = mongo.db.users.find_one({'email': email})
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = generate_token(user['_id'])
    return jsonify({
        'token': token,
        'user': {
            'id': str(user['_id']),
            'name': user['name'],
            'email': user['email'],
            'role': user.get('role', 'renter'),
            'phone': user.get('phone', ''),
            'location': user.get('location', '')
        }
    })


@auth_bp.route('/login-owner', methods=['POST'])
def login_owner():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = mongo.db.users.find_one({'email': email})
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if user.get('role', 'renter') != 'owner':
        return jsonify({'error': 'This account is not registered as owner'}), 403

    token = generate_token(user['_id'])
    return jsonify({
        'token': token,
        'user': {
            'id': str(user['_id']),
            'name': user['name'],
            'email': user['email'],
            'role': user.get('role', 'renter'),
            'phone': user.get('phone', ''),
            'location': user.get('location', '')
        }
    })


@auth_bp.route('/me', methods=['GET'])
def me():
    from utils.auth_middleware import get_current_user
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'user': {
        'id': str(user['_id']),
        'name': user['name'],
        'email': user['email'],
        'role': user.get('role', 'renter'),
        'phone': user.get('phone', ''),
        'location': user.get('location', '')
    }})
