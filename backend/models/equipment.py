"""
Equipment model schema reference (MongoDB — schemaless).

Collection: equipment
Fields:
  - name           : str
  - category       : str ('tractor'|'harvester'|'rotavator'|'sprayer'|'thresher'|'plough'|'seeder'|'pump')
  - price_per_day  : int (in INR)
  - location       : str
  - city           : str
  - district       : str
  - latitude       : float
  - longitude      : float
  - description    : str
  - brand          : str
  - year           : int
  - owner_name     : str
  - owner_phone    : str
  - owner_id       : ObjectId (ref: users)
  - available      : bool
  - created_at     : datetime
"""

EQUIPMENT_SCHEMA = {
    'name': str,
    'category': str,
    'price_per_day': int,
    'location': str,
    'city': str,
    'district': str,
    'latitude': float,
    'longitude': float,
    'description': str,
    'brand': str,
    'year': int,
    'owner_name': str,
    'owner_phone': str,
    'owner_id': 'ObjectId',
    'available': bool,
    'created_at': 'datetime'
}

VALID_CATEGORIES = ['tractor', 'harvester', 'rotavator', 'sprayer', 'thresher', 'plough', 'seeder', 'pump']
