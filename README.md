# PHRMS — Procam HR Management System

Full-stack Flask application connecting directly to your existing Proconnect MySQL database.
**No data migration needed** — reads your live 732 employee records, 453,843 attendance records, and all historical data.

---

## Quick Start (Mac)

### Step 1 — Import Proconnect SQL into MySQL

```bash
# If MySQL not installed
brew install mysql
brew services start mysql
mysql_secure_installation

# Create the database and import
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS proconnect CHARACTER SET utf8;"
mysql -u root -p proconnect < ~/desktop/"PROCONNECT DATA.sql"
# This will take 10–30 minutes for 728MB
```

### Step 2 — Set up Python environment

```bash
cd ~/desktop
git clone <this-repo> phrms   # or copy the phrms folder here
cd phrms

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3 — Configure environment

```bash
cp .env.template .env
# Edit .env and set your MySQL password:
nano .env
```

Set these values:
```
MYSQL_PASSWORD=your_actual_mysql_root_password
MYSQL_DB=proconnect
SECRET_KEY=any-long-random-string
```

### Step 4 — Run

```bash
source venv/bin/activate
python run.py
```

Open: **http://localhost:5050**

Login with your **existing Proconnect username and password** — same credentials, no new accounts needed.

---

## Architecture

```
phrms/
├── run.py                  ← Entry point
├── config.py               ← MySQL config (reads .env)
├── requirements.txt
├── app/
│   ├── __init__.py         ← Flask app factory
│   ├── db.py               ← All database queries (real Proconnect schema)
│   ├── routes/
│   │   ├── auth.py         ← Login/logout, User model
│   │   ├── admin.py        ← Admin dashboard + all HR functions
│   │   ├── hr.py           ← HR dashboard
│   │   ├── employee.py     ← Employee self-service
│   │   └── __init__.py     ← All other blueprints
│   └── templates/
│       ├── base.html       ← Layout with sidebar, responsive
│       ├── auth/login.html
│       ├── admin/dashboard.html
│       ├── hr/dashboard.html
│       └── employee/dashboard.html
```

---

## Three Dashboards

| Role | Dashboard | Access |
|------|-----------|--------|
| **Admin** | Full system — all employees, all attendance, all approvals, KPI, recruitment, grievances, holidays | `usertypes.typename = 'Admin'` or `roleid = 1` |
| **HR** | HR view — employees, attendance, leave approvals, recruitment, grievances | `rolename LIKE '%HR%'` |
| **Employee** | Self-service — own attendance, leave balance, claims, loans, KPI, grievances | All other users |

---

## Key Features

### Real Data (no dummy data)
- **732 employees** from `employees` table (historical + active)
- **453,843 attendance records** from `dailyattendance`
- **57,962 mobile check-ins** from `mobileattendancereason` with GPS coordinates
- **1,667 leave requests** with full approval chain
- **42,125 claim payments** historical
- **6,970 attendance regulation requests**

### Mobile Attendance
- Employees with `mobileattendanceflag=1` see the GPS check-in button
- Captures latitude, longitude, address (reverse-geocoded via OpenStreetMap)
- Stored in `mobileattendancereason` exactly as the original Proconnect schema
- Works on any modern mobile browser — no app install needed

### Approval Workflows
- Leave requests → `leaverequest` + `leaverequestapproval` + `approvalrequest`
- Attendance regulation → `attendanceregulationrequest` + `attendanceregulationapproval`
- All flags match original Proconnect: 0=Pending, 1=Approved, 2=Rejected

### Authentication
- Uses existing `users` table with same username/password
- Supports MD5, SHA1, SHA256, and bcrypt password hashes (Proconnect uses MD5)
- Role-based access via `roles` + `rolemodules` + `usertypes`

---

## Production Deployment (Render / VPS)

```bash
# Install gunicorn (already in requirements.txt)
gunicorn -w 4 -b 0.0.0.0:5050 "run:app"
```

For Render:
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn run:app`
- Set environment variables in Render dashboard

---

## Extending

To add more modules (IOU, Travel, Payroll processing):
1. Add queries to `app/db.py` using exact Proconnect column names
2. Add routes to appropriate blueprint in `app/routes/`
3. Create template in `app/templates/`

All 140 HR tables are already mapped in `db.py` — just write the queries.

---

## Password Reset

If a user's Proconnect password doesn't work:
```sql
-- Set password to 'Procam@2024'
UPDATE users SET pwd = MD5('Procam@2024') WHERE username = 'their_username';
```
