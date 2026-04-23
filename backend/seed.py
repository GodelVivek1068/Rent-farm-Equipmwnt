"""
seed.py — Populate MongoDB with demo equipment data for KrishiYantra.
Run once: python seed.py
"""

from pymongo import MongoClient
from werkzeug.security import generate_password_hash
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/krishiyantra")
client = MongoClient(MONGO_URI)
db = client.krishiyantra

# ---- Clear existing demo data ----
print("Clearing existing data...")
db.users.delete_many({})
db.equipment.delete_many({})
db.rentals.delete_many({})

# ---- Seed Users ----
print("Seeding users...")
users = [
    {
        "name": "Vivek Jadhav",
        "email": "rajesh@demo.com",
        "phone": "9699391891",
        "location": "Pune, Maharashtra",
        "password": generate_password_hash("password123"),
        "role": "owner",
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Yash Jadhav",
        "email": "yash@demo.com",
        "phone": "9876543211",
        "location": "Nashik, Maharashtra",
        "password": generate_password_hash("password123"),
        "role": "owner",
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Meena Jadhav",
        "email": "meena@demo.com",
        "phone": "9876543212",
        "location": "Nashik, Maharashtra",
        "password": generate_password_hash("password123"),
        "role": "renter",
        "created_at": datetime.datetime.utcnow()
    }
]
user_ids = db.users.insert_many(users).inserted_ids
print(f"  Inserted {len(user_ids)} users")

owner1_id = user_ids[0]
owner2_id = user_ids[1]
renter_id = user_ids[2]

# ---- Seed Equipment ----
print("Seeding equipment...")
equipment_list = [
    {
        "name": "Mahindra 575 DI Tractor",
        "category": "tractor",
        "price_per_day": 2500,
        "location": "Kolhapur, Maharashtra",
        "description": "Well-maintained Mahindra 575 DI, 47HP. Ideal for field prep, sowing, and transport. Rotavator attachment available.",
        "brand": "Mahindra",
        "year": 2020,
        "owner_name": "Vivek Jadhav",
        "owner_phone": "9699391891",
        "owner_id": owner1_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "John Deere 5310 Tractor",
        "category": "tractor",
        "price_per_day": 3200,
        "location": "Kolhapur, Maharashtra",
        "description": "Powerful John Deere 5310, 55HP. Perfect for heavy field operations and transportation.",
        "brand": "John Deere",
        "year": 2021,
        "owner_name": "Vivek Jadhav",
        "owner_phone": "9699391891",
        "owner_id": owner1_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Combine Harvester (Self-Propelled)",
        "category": "harvester",
        "price_per_day": 5500,
        "location": "Kolhapur, Maharashtra",
        "description": "Self-propelled combine harvester for wheat and paddy. Minimal crop loss, very efficient.",
        "brand": "CLAAS",
        "year": 2019,
        "owner_name": "Vivek Jadhav",
        "owner_phone": "9699391891",
        "owner_id": owner1_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Rotavator 7 ft",
        "category": "rotavator",
        "price_per_day": 1200,
        "location": "Kolhapur, Maharashtra",
        "description": "Heavy duty 7ft rotavator. Prepares seedbed with excellent soil tilth for all crops.",
        "brand": "Shaktiman",
        "year": 2022,
        "owner_name": "Vivek Jadhav",
        "owner_phone": "9699391891",
        "owner_id": owner1_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Power Sprayer 16L",
        "category": "sprayer",
        "price_per_day": 600,
        "location": "Kolhapur, Maharashtra",
        "description": "Battery-powered knapsack sprayer, 16L capacity. Ideal for pesticide and fertilizer application.",
        "brand": "Neptune",
        "year": 2023,
        "owner_name": "Vivek Jadhav",
        "owner_phone": "9699391891",
        "owner_id": owner1_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Paddy Thresher",
        "category": "thresher",
        "price_per_day": 1400,
        "location": "Kolhapur, Maharashtra",
        "description": "Efficient paddy thresher. Separates grain quickly with low breakage. Diesel powered.",
        "brand": "Agrimaster",
        "year": 2021,
        "owner_name": "Vivek Jadhav",
        "owner_phone": "9699391891",
        "owner_id": owner1_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "MB Plough 3 Furrow",
        "category": "plough",
        "price_per_day": 900,
        "location": "Sangli, Maharashtra",
        "description": "3-furrow MB plough for deep primary tillage. Suitable for heavy clay soils.",
        "brand": "Fieldking",
        "year": 2020,
        "owner_name": "Yash Jadhav",
        "owner_phone": "9876543211",
        "owner_id": owner2_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Seed Drill 9-Row",
        "category": "seeder",
        "price_per_day": 1100,
        "location": "Sangli, Maharashtra",
        "description": "9-row seed drill for precise sowing of soybean, wheat, gram. Uniform row spacing.",
        "brand": "Agro Master",
        "year": 2022,
        "owner_name": "Yash Jadhav",
        "owner_phone": "9876543211",
        "owner_id": owner2_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Diesel Water Pump 5HP",
        "category": "pump",
        "price_per_day": 550,
        "location": "Sangli, Maharashtra",
        "description": "5HP diesel water pump. High discharge rate for field irrigation. Easy to transport.",
        "brand": "Kirloskar",
        "year": 2021,
        "owner_name": "Yash Jadhav",
        "owner_phone": "9876543211",
        "owner_id": owner2_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Mini Power Tiller",
        "category": "tractor",
        "price_per_day": 1600,
        "location": "Sangli, Maharashtra",
        "description": "Versatile mini power tiller for small farms and hilly terrain. 7HP, lightweight.",
        "brand": "VST Shakti",
        "year": 2022,
        "owner_name": "Yash Jadhav",
        "owner_phone": "9876543211",
        "owner_id": owner2_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "Laser Land Leveler",
        "category": "tractor",
        "price_per_day": 3800,
        "location": "Sangli, Maharashtra",
        "description": "GPS-guided laser land leveler. Levels fields accurately for water-efficient irrigation.",
        "brand": "Trimble",
        "year": 2020,
        "owner_name": "Yash Jadhav",
        "owner_phone": "9876543211",
        "owner_id": owner2_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
    {
        "name": "John Deere Combine Harvester W70",
        "category": "harvester",
        "price_per_day": 4800,
        "location": "Sangli, Maharashtra",
        "description": "John Deere W70 combine for wheat, soybean, and sunflower. Excellent threshing quality.",
        "brand": "John Deere",
        "year": 2021,
        "owner_name": "Yash Jadhav",
        "owner_phone": "9876543211",
        "owner_id": owner2_id,
        "available": True,
        "created_at": datetime.datetime.utcnow()
    },
]

eq_ids = db.equipment.insert_many(equipment_list).inserted_ids
print(f"  Inserted {len(eq_ids)} equipment records")

# ---- Seed Sample Rental ----
print("Seeding sample rental...")
rental = {
    "equipment_id": eq_ids[0],
    "equipment_name": "Mahindra 575 DI Tractor",
    "category": "tractor",
    "renter_id": renter_id,
    "renter_name": "Meena Jadhav",
    "owner_id": owner1_id,
    "start_date": "2024-11-10",
    "end_date": "2024-11-12",
    "delivery_address": "Koregaon Village, Pune",
    "notes": "Please bring rotavator attachment",
    "total_amount": 5000,
    "status": "confirmed",
    "created_at": datetime.datetime.utcnow()
}
db.rentals.insert_one(rental)
print("  Inserted 1 sample rental")

print("\n✅ Seeding complete!")
print("\nDemo Login Credentials:")
print("  Email: rajesh@demo.com  | Password: password123  (Owner)")
print("  Email: meena@demo.com   | Password: password123  (Renter)")
