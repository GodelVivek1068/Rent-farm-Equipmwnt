from flask import Blueprint, request, jsonify
import datetime
import os
import smtplib
from email.message import EmailMessage
from config.db import mongo

contact_bp = Blueprint('contact', __name__)


def _send_contact_email(name, contact, topic, message):
    receiver_email = os.getenv('CONTACT_RECEIVER_EMAIL', 'vj572483@gmail.com').strip() or 'vj572483@gmail.com'
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com').strip() or 'smtp.gmail.com'
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '').strip()
    smtp_password = os.getenv('SMTP_PASSWORD', '').strip()
    from_email = os.getenv('SMTP_FROM_EMAIL', smtp_user).strip() if smtp_user else ''

    if not smtp_user or not smtp_password or not from_email:
        raise RuntimeError('Email sending is not configured on server (SMTP_USER/SMTP_PASSWORD missing).')

    subject = f"[KrishiYantra Contact] {topic}"
    body = (
        "New contact message received.\n\n"
        f"Name: {name}\n"
        f"Contact: {contact}\n"
        f"Topic: {topic}\n\n"
        "Message:\n"
        f"{message}\n"
    )

    email = EmailMessage()
    email['Subject'] = subject
    email['From'] = from_email
    email['To'] = receiver_email
    email['Reply-To'] = contact
    email.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(email)

@contact_bp.route('/', methods=['POST'])
def send_message():
    data = request.get_json() or {}
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
        'created_at': datetime.datetime.utcnow(),
        'email_delivery_status': 'pending'
    }

    insert_result = mongo.db.contact_messages.insert_one(doc)
    message_id = insert_result.inserted_id

    try:
        _send_contact_email(name=name, contact=contact, topic=topic, message=message)
        mongo.db.contact_messages.update_one(
            {'_id': message_id},
            {'$set': {'email_delivery_status': 'sent', 'email_sent_at': datetime.datetime.utcnow()}}
        )
    except Exception as exc:
        mongo.db.contact_messages.update_one(
            {'_id': message_id},
            {'$set': {'email_delivery_status': 'failed', 'email_delivery_error': str(exc)}}
        )
        return jsonify({'error': 'Message saved, but email delivery failed. Please contact support directly at vj572483@gmail.com.'}), 500

    return jsonify({'message': 'Message received. We will get back to you soon!'}), 201


@contact_bp.route('/', methods=['GET'])
def get_messages():
    messages = list(mongo.db.contact_messages.find().sort('created_at', -1).limit(100))
    for m in messages:
        m['_id'] = str(m['_id'])
        m['created_at'] = str(m['created_at'])
    return jsonify({'messages': messages})
