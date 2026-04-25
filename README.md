# 🚜 KrishiYantra — Mobile-Based Farm Equipment Rental Platform

A full-stack web application for renting and listing farm equipment, built for Indian farmers.

---

## 📁 Project Structure

```
farm_rental/
├── frontend/
│   ├── index.html               ← Home page
│   ├── css/
│   │   ├── main.css             ← Global styles, navbar, footer
│   │   └── home.css             ← Hero, categories, how-it-works
│   ├── js/
│   │   ├── main.js              ← API helpers, auth, shared functions
│   │   └── home.js              ← Home page logic
│   └── pages/
│       ├── equipment.html       ← Browse & filter all equipment
│       ├── equipment-detail.html← Equipment detail + booking form
│       ├── login.html           ← Login page
│       ├── register.html        ← Registration page
│       ├── list-equipment.html  ← List your own equipment
│       ├── my-rentals.html      ← View your bookings
│       └── contact.html         ← Contact form
│
└── backend/
    ├── app.py                   ← Flask app entry point
    ├── requirements.txt         ← Python dependencies
    ├── .env.example             ← Environment variable template
    ├── seed.py                  ← Database seed script
    ├── config/
    │   └── db.py                ← MongoDB connection setup
    ├── models/
    │   ├── user.py              ← User schema reference
    │   ├── equipment.py         ← Equipment schema reference
    │   └── rental.py            ← Rental schema reference
    ├── routes/
    │   ├── auth.py              ← /api/auth — register, login, me
    │   ├── equipment.py         ← /api/equipment — CRUD
    │   ├── rentals.py           ← /api/rentals — booking management
    │   └── contact.py           ← /api/contact — contact form
    └── utils/
        └── auth_middleware.py   ← JWT authentication helpers
```

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.9+ installed
- MongoDB installed locally
- A browser (Chrome/Firefox/Safari)

---

### Step 1 — Set Up MongoDB

**Local MongoDB**
1. Download and install MongoDB Community: https://www.mongodb.com/try/download/community
2. Start MongoDB: `mongod` (or use MongoDB Compass GUI)

---

### Step 2 — Configure Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it:
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
```

Edit `.env` and set your MongoDB URI:
```
MONGO_URI=mongodb://localhost:27017/krishiyantra
SECRET_KEY=your_strong_secret_key_here
```

---

### Step 3 — Seed Demo Data (Optional)

```bash
# Make sure you're in the backend/ folder with venv active
python seed.py
```

This creates demo users, equipment, and one sample rental.

**Demo Login Accounts:**
| Email | Password | Role |
|-------|----------|------|
| rajesh@demo.com | password123 | Owner |
| meena@demo.com | password123 | Renter |

---

### Step 4 — Run the Backend

```bash
python app.py
```

Backend runs at: **http://localhost:5000**

Test it: Open http://localhost:5000 in your browser — you should see:
```json
{"message": "KrishiYantra API is running 🚜", "version": "1.0"}
```

---

### Step 5 — Open the Frontend

Simply open `frontend/index.html` in your browser.

> **Tip:** For best results, use a local server (avoids CORS issues with file://):
>
> ```bash
> # Option 1 — Python built-in server (from frontend/ folder)
> cd frontend
> python -m http.server 8080
> # Then open: http://localhost:8080
>
> # Option 2 — VS Code Live Server extension
> # Right-click index.html → "Open with Live Server"
> ```

---

## ☁️ Deployment (Render + Netlify)

### 1. Deploy Backend to Render

1. Push this repository to GitHub.
2. In Render, create a new **Web Service** from the repo.
3. Use these settings:
    - Root Directory: `backend`
    - Build Command: `pip install -r requirements.txt`
    - Start Command: `gunicorn "app:create_app()"`
4. Add environment variables in Render:
    - `MONGO_URI` = your MongoDB URI
    - `SECRET_KEY` = long random secret
    - `RAZORPAY_KEY_ID` = your Razorpay key id
    - `RAZORPAY_KEY_SECRET` = your Razorpay key secret
    - `SMTP_HOST` = SMTP server host (example: `smtp.gmail.com`)
    - `SMTP_PORT` = SMTP server port (example: `587`)
    - `SMTP_USER` = SMTP login username/email
    - `SMTP_PASSWORD` = SMTP app password
    - `SMTP_FROM_EMAIL` = sender email address shown to farmer
    - `SMTP_USE_TLS` = `1` to enable TLS (`0` to disable)
    - `ADMIN_EMAILS` = comma-separated admin emails (auto-admin on register)
    - `CORS_ORIGINS` = `https://<your-netlify-site>.netlify.app`
    - `FLASK_DEBUG` = `0`
5. Deploy and copy your backend URL, for example:
    - `https://krishiyantra-api.onrender.com`

### 2. Deploy Frontend to Netlify

1. In Netlify, create a new site from the same repo.
2. Build settings:
    - Base directory: `frontend`
    - Publish directory: `.`
    - Build command: *(leave empty)*
3. Open [netlify.toml](netlify.toml) and replace:
    - `https://YOUR-RENDER-SERVICE.onrender.com`
    with your real Render backend URL if your Render service name is different.
    - If you used the provided blueprint name, the URL is `https://krishiyantra-api.onrender.com`.
4. Trigger a new deploy in Netlify.

### 3. Verify Production

1. Open your Netlify site.
2. Register/login and load equipment pages.
3. Check backend health:
    - `https://<your-render-service>.onrender.com/api/health`

Notes:
- Frontend now uses `http://localhost:5000/api` on localhost and `/api` on hosted domains.
- Netlify proxies `/api/*` to Render using [netlify.toml](netlify.toml).
- Keep CORS locked to your Netlify domain in production.
- If equipment still returns 500, verify `MONGO_URI` points to a reachable MongoDB instance.

---

## 🔌 API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login and get JWT |
| GET | `/api/auth/me` | Get current user (auth required) |

### Equipment
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/equipment/` | List all equipment (with filters) |
| GET | `/api/equipment/<id>` | Get equipment detail |
| POST | `/api/equipment/` | Create equipment listing (auth) |
| GET | `/api/equipment/my` | Get my listed equipment (auth) |
| PUT | `/api/equipment/<id>` | Update equipment (auth, owner only) |
| DELETE | `/api/equipment/<id>` | Delete equipment (auth, owner only) |

**Query Parameters for GET `/api/equipment/`:**
- `search` — keyword search
- `category` — filter by category
- `location` — filter by location
- `max_price` — filter by max price/day
- `sort` — `newest`, `price_asc`, `price_desc`
- `limit` — number of results (default 50)

### Rentals
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/rentals/` | Create a booking (auth) |
| GET | `/api/rentals/my` | Get my rentals as renter (auth) |
| GET | `/api/rentals/owner` | Get rentals for my equipment (auth) |
| PUT | `/api/rentals/<id>/status` | Update rental status (auth) |
| POST | `/api/rentals/<id>/email-confirmation` | Owner sends booking confirmation email to farmer (auth) |

### Admin + Marketplace Ops
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/owner-kyc` | Owner submits KYC details |
| GET | `/api/admin/owner-kyc/status` | Get current owner KYC status |
| GET | `/api/admin/owner-kyc/pending` | List owner KYC submissions pending review (admin) |
| PUT | `/api/admin/owner-kyc/<owner_id>/decision` | Approve/reject owner KYC (admin) |
| GET | `/api/admin/dashboard` | Admin summary metrics |
| GET | `/api/admin/commission` | Get default commission setting (admin) |
| PUT | `/api/admin/commission` | Update default commission setting (admin) |
| GET | `/api/admin/commissions` | List commission records (admin) |
| POST | `/api/admin/disputes` | Raise a dispute for a rental |
| GET | `/api/admin/disputes/my` | List current user's disputes |
| GET | `/api/admin/disputes` | List disputes (admin) |
| PUT | `/api/admin/disputes/<dispute_id>/status` | Update dispute status (admin) |

### Contact
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/contact/` | Submit contact form |

---

## 🌾 Features

- **Home Page** — Hero search, category browse, featured equipment, how it works, testimonials
- **Equipment Browse** — Filter by category, location, price, keyword; sort options
- **Equipment Detail** — Full info, owner contact, date picker booking with total calculation
- **Authentication** — JWT-based register/login, role selection (owner/renter)
- **Owner KYC Approval** — Owner KYC submission and admin review before listing equipment
- **List Equipment** — Owners can list their equipment with all details
- **My Rentals** — View all booked rentals and owned equipment listings
- **Nearby Multi-owner Discovery** — Distance-aware alternatives from nearby owners when selected equipment is unavailable
- **Admin Panel** — KYC approvals, commission management, dispute handling and marketplace analytics
- **Commission Automation** — Commission and owner payout computed on rental completion
- **Dispute Workflow** — Renter/owner can raise disputes and admin can resolve/reject
- **Contact Page** — Contact form with topic selection
- **Mobile Responsive** — Hamburger menu, responsive grids, mobile-friendly forms

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Python, Flask |
| Database | MongoDB (via Flask-PyMongo) |
| Auth | JWT (PyJWT) |
| Password | Werkzeug (bcrypt-based hashing) |
| CORS | flask-cors |

---

## 🔐 Security Notes

- Passwords are hashed using Werkzeug's `generate_password_hash`
- JWT tokens expire after 30 days
- All protected routes require `Authorization: Bearer <token>` header
- Equipment can only be modified/deleted by the owner
- Rentals can only be created by logged-in users who don't own the equipment

---

## 📱 Mobile Optimization

The frontend is fully mobile-responsive:
- Hamburger nav for small screens
- Flexible grid layouts (auto-fill, minmax)
- Touch-friendly buttons and form inputs
- Hero search stacks vertically on mobile
- Equipment grid adapts to screen width

---

## 🌱 Future Enhancements

- Payment gateway (Razorpay integration)
- SMS/WhatsApp notifications on booking
- Equipment photo upload
- Ratings & reviews system
- Admin dashboard
- Map-based equipment search
- Multi-language support (Marathi, Hindi)
