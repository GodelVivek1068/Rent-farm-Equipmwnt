from flask import Flask, send_from_directory
from flask_cors import CORS
import os
from config.db import init_db
from routes.auth import auth_bp
from routes.equipment import equipment_bp
from routes.rentals import rentals_bp
from routes.contact import contact_bp
from routes.admin_marketplace import marketplace_admin_bp


FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

def create_app():
    app = Flask(__name__)
    cors_origins = os.getenv('CORS_ORIGINS', '*').strip()
    if cors_origins == '*':
        CORS(app, origins='*')
    else:
        origins = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]
        CORS(app, origins=origins)

    # Initialize DB
    init_db(app)

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(equipment_bp, url_prefix='/api/equipment')
    app.register_blueprint(rentals_bp, url_prefix='/api/rentals')
    app.register_blueprint(contact_bp, url_prefix='/api/contact')
    app.register_blueprint(marketplace_admin_bp, url_prefix='/api/admin')

    @app.route('/')
    def index():
        return send_from_directory(FRONTEND_DIR, 'index.html')

    @app.route('/index.html')
    def index_html():
        return send_from_directory(FRONTEND_DIR, 'index.html')

    @app.route('/pages/<path:filename>')
    def pages(filename):
        return send_from_directory(os.path.join(FRONTEND_DIR, 'pages'), filename)

    @app.route('/pages/pages/<path:filename>')
    def pages_compat(filename):
        # Backward compatibility for older cached frontend links.
        return send_from_directory(os.path.join(FRONTEND_DIR, 'pages'), filename)

    @app.route('/css/<path:filename>')
    def css(filename):
        return send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename)

    @app.route('/js/<path:filename>')
    def js(filename):
        return send_from_directory(os.path.join(FRONTEND_DIR, 'js'), filename)

    @app.route('/api')
    def api_root():
        return {"message": "KrishiYantra API is running 🚜", "version": "1.0"}

    @app.route('/api/health')
    def health():
        return {"status": "ok"}

    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
