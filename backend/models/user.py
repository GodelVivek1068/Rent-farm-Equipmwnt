"""
User model schema reference (MongoDB — schemaless, but documented here).

Collection: users
Fields:
  - name         : str
  - email        : str (unique, lowercase)
  - phone        : str
  - location     : str
  - password     : str (hashed with werkzeug)
  - role         : str ('renter' | 'owner' | 'admin')
  - kyc_status   : str ('not_required'|'pending'|'approved'|'rejected')
  - kyc_details  : dict
  - kyc_review_notes : str
  - created_at   : datetime
"""

USER_SCHEMA = {
    'name': str,
    'email': str,
    'phone': str,
    'location': str,
    'password': str,
    'role': str,
    'kyc_status': str,
    'kyc_details': dict,
    'kyc_review_notes': str,
    'created_at': 'datetime'
}
