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
