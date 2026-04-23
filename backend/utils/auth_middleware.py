from flask import request, jsonify, current_app
from functools import wraps
import jwt
from bson import ObjectId
from config.db import mongo


def get_current_user():
    """Extract user from JWT token in Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ', 1)[1]
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(payload['user_id'])})
        return user
    except Exception:
        return None


def require_auth(f):
    """Decorator: requires valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def require_roles(allowed_roles):
    """Decorator: requires valid JWT and one of allowed roles."""
    normalized = {str(role).strip().lower() for role in (allowed_roles or [])}

    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401

            user_role = str(user.get('role', 'renter')).strip().lower()
            if user_role not in normalized:
                return jsonify({'error': 'Forbidden'}), 403
            return f(*args, **kwargs)

        return decorated

    return wrapper


def is_admin(user):
    if not user:
        return False
    return str(user.get('role', '')).strip().lower() == 'admin'
