from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
from config.db import mongo

auth_bp = Blueprint('auth', __name__)


def _serialize_user(user):
    role = user.get('role', 'renter')
    kyc_status = user.get('kyc_status')
    if not kyc_status:
        kyc_status = 'approved' if role in {'owner', 'admin'} else 'not_required'

    return {
        'id': str(user['_id']),
        'name': user.get('name', ''),
        'email': user.get('email', ''),
        'role': role,
        'phone': user.get('phone', ''),
        'location': user.get('location', ''),
        'kyc_status': kyc_status,
        'kyc_review_notes': user.get('kyc_review_notes', '')
    }


def _admin_emails():
    raw = os.getenv('ADMIN_EMAILS', '').strip()
    if not raw:
        return set()
    return {email.strip().lower() for email in raw.split(',') if email.strip()}

def generate_token(user_id):
    payload = {
        'user_id': str(user_id),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    location = data.get('location', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'renter')
    role = role if role in {'renter', 'owner'} else 'renter'

    is_admin_email = email in _admin_emails()
    if is_admin_email:
        role = 'admin'

    if not all([name, email, phone, password]):
        return jsonify({'error': 'All fields are required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    # Check if user exists
    existing = mongo.db.users.find_one({'email': email})
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    hashed_pw = generate_password_hash(password)

    kyc_status = 'pending' if role == 'owner' else ('approved' if role == 'admin' else 'not_required')
    user_doc = {
        'name': name,
        'email': email,
        'phone': phone,
        'location': location,
        'password': hashed_pw,
        'role': role,
        'kyc_status': kyc_status,
        'kyc_details': {},
        'kyc_review_notes': '',
        'created_at': datetime.datetime.utcnow()
    }
    result = mongo.db.users.insert_one(user_doc)
    token = generate_token(result.inserted_id)

    created_user = dict(user_doc)
    created_user['_id'] = result.inserted_id

    return jsonify({
        'token': token,
        'user': _serialize_user(created_user)
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
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
        'user': _serialize_user(user)
    })


@auth_bp.route('/login-owner', methods=['POST'])
def login_owner():
    data = request.get_json() or {}
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
        'user': _serialize_user(user)
    })


@auth_bp.route('/login-admin', methods=['POST'])
def login_admin():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = mongo.db.users.find_one({'email': email})
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if str(user.get('role', 'renter')).lower() != 'admin':
        return jsonify({'error': 'This account is not registered as admin'}), 403

    token = generate_token(user['_id'])
    return jsonify({
        'token': token,
        'user': _serialize_user(user)
    })


@auth_bp.route('/me', methods=['GET'])
def me():
    from utils.auth_middleware import get_current_user
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'user': _serialize_user(user)})
