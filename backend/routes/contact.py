from flask import Blueprint, request, jsonify
import datetime
from config.db import mongo

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/', methods=['POST'])
def send_message():
    data = request.get_json()
    name = data.get('name', '').strip()
    contact = data.get('contact', '').strip()
    topic = data.get('topic', 'General')
    message = data.get('message', '').strip()

    if not all([name, contact, message]):
        return jsonify({'error': 'Name, contact and message are required'}), 400

    doc = {
        'name': name,
        'contact': contact,
        'topic': topic,
        'message': message,
        'created_at': datetime.datetime.utcnow()
    }
    mongo.db.contact_messages.insert_one(doc)
    return jsonify({'message': 'Message received. We will get back to you soon!'}), 201


@contact_bp.route('/', methods=['GET'])
def get_messages():
    messages = list(mongo.db.contact_messages.find().sort('created_at', -1).limit(100))
    for m in messages:
        m['_id'] = str(m['_id'])
        m['created_at'] = str(m['created_at'])
    return jsonify({'messages': messages})
