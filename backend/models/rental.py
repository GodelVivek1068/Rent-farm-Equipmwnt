"""
Rental model schema reference (MongoDB — schemaless).

Collection: rentals
Fields:
  - equipment_id     : ObjectId (ref: equipment)
  - equipment_name   : str (denormalized)
  - category         : str (denormalized)
  - renter_id        : ObjectId (ref: users)
  - renter_name      : str (denormalized)
  - renter_email     : str (denormalized)
  - renter_phone     : str (denormalized)
  - owner_id         : ObjectId (ref: users)
  - start_date       : str (YYYY-MM-DD)
  - end_date         : str (YYYY-MM-DD)
  - delivery_address : str
  - notes            : str
  - total_amount     : int (INR)
  - commission       : dict {'commission_percent','commission_amount','owner_payout'}
  - status           : str ('pending'|'confirmed'|'cancelled'|'completed')
  - created_at       : datetime
"""

RENTAL_SCHEMA = {
    'equipment_id': 'ObjectId',
    'equipment_name': str,
    'category': str,
    'renter_id': 'ObjectId',
    'renter_name': str,
    'renter_email': str,
    'renter_phone': str,
    'owner_id': 'ObjectId',
    'start_date': str,
    'end_date': str,
    'delivery_address': str,
    'notes': str,
    'total_amount': int,
    'commission': dict,
    'status': str,
    'created_at': 'datetime'
}

VALID_STATUSES = ['pending', 'confirmed', 'cancelled', 'completed']
