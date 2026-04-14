from flask_pymongo import PyMongo
from dotenv import load_dotenv
import os

load_dotenv()

mongo = PyMongo()

def init_db(app):
    app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/krishiyantra")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "krishi_secret_key_change_in_production")
    mongo.init_app(app)
    return mongo
