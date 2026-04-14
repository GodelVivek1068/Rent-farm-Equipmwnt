"""
User model schema reference (MongoDB — schemaless, but documented here).

Collection: users
Fields:
  - name         : str
  - email        : str (unique, lowercase)
  - phone        : str
  - location     : str
  - password     : str (hashed with werkzeug)
  - role         : str ('renter' | 'owner')
  - created_at   : datetime
"""

USER_SCHEMA = {
    'name': str,
    'email': str,
    'phone': str,
    'location': str,
    'password': str,
    'role': str,         # 'renter' or 'owner'
    'created_at': 'datetime'
}
