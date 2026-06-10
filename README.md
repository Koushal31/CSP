# PapersNav - Previous Year Papers Navigator

A Flask-based web application for engineering students to search, upload, and download previous year question papers organized by college, branch, semester, and subject.

## Features

- **Search & Browse**: Filter papers by college, branch, semester, subject, and year
- **User Registration**: Students can register and create accounts
- **Paper Upload**: Authenticated users can upload PDF papers
- **Admin Panel**: Admin dashboard for approving/rejecting papers, managing colleges, branches, and subjects
- **Dynamic Content**: College/Branch/Subject relationships managed through database (no hardcoding)
- **Responsive Design**: Mobile-friendly interface
- **Secure**: Password hashing, session management, and role-based access control

## Setup & Installation

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd csp
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   # On Windows
   .venv\Scripts\activate
   # On macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and set:
   - `FLASK_ENV=development`
   - `SECRET_KEY=your-secure-secret-key`
   - `MONGO_URI=your-mongodb-connection-string`
   - `ADMIN_EMAIL=admin@gmail.com`
   - `ADMIN_PASSWORD=1234`

5. **Run the application**
   ```bash
   python app.py
   ```
   
   The app will be available at `http://localhost:5000`

## Deployment on Render

### Prerequisites
- Render account (https://render.com)
- MongoDB Atlas account (https://www.mongodb.com/cloud/atlas)
- GitHub repository with this code

### Step-by-Step Deployment

1. **Push code to GitHub**
   ```bash
   git add .
   git commit -m "Ready for production"
   git push origin main
   ```

2. **Create MongoDB Atlas Cluster**
   - Go to MongoDB Atlas
   - Create a free cluster
   - Create a database user
   - Get connection string

3. **Deploy on Render**
   - Go to https://dashboard.render.com
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Configure the service with build and start commands

4. **Set Environment Variables** in Render:
   ```
   FLASK_ENV=production
   SECRET_KEY=<secure-key>
   MONGO_URI=<mongodb-connection-string>
   ADMIN_EMAIL=admin@gmail.com
   ADMIN_PASSWORD=<secure-password>
   ```

5. **Deploy** and access your app at the provided Render URL

## Project Structure

```
csp/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Procfile              # Render deployment
├── render.yaml           # Render native config
├── .env.example          # Environment template
├── README.md             # This file
├── static/
│   ├── css/
│   ├── js/
│   └── uploads/          # Paper uploads
└── templates/
    ├── base.html
    ├── home.html
    ├── papers.html
    ├── upload.html
    ├── login.html
    └── admin/            # Admin templates
```

## Admin Credentials

**Default admin account:**
- **Email**: admin@gmail.com
- **Password**: 1234

⚠️ **IMPORTANT**: Change these immediately after first login in production!

## Database

The application uses MongoDB with the following collections:
- `users` - User accounts
- `papers` - Uploaded papers
- `colleges` - College information
- `branches` - Engineering branches
- `subjects` - Subjects for each branch

Indexes are automatically created on first run.

## Security Features

✅ Password hashing
✅ CSRF protection
✅ File upload validation
✅ XSS protection
✅ Role-based access control
✅ HTTPS in production
✅ Input sanitization

## Troubleshooting

**MongoDB Connection Error**: Check MONGO_URI and IP whitelist
**Upload Fails**: Ensure PDF format and disk space
**Admin Access Denied**: Clear cookies and re-login

## Version
1.0.0 - Production Ready ✅

- 📱 Fully responsive mobile design

## Tech Stack
- **Frontend:** HTML5, CSS3, JavaScript (vanilla)
- **Backend:** Flask (Python)
- **Database:** MongoDB

## Quick Start

### 1. Install MongoDB
- Download from https://www.mongodb.com/try/download/community
- Start: `mongod --dbpath /data/db`
- Or use MongoDB Atlas (cloud) free tier

### 2. Install Python dependencies
```bash
cd ppn
pip install -r requirements.txt
```

### 3. Run the app
```bash
python app.py
```

Visit: http://localhost:5000

### 4. Admin login
- Email: `admin@gmail.com`
- Password: `1234`
- Admin panel: http://localhost:5000/admin

## MongoDB Atlas (Cloud)
Set the `MONGO_URI` environment variable:
```bash
export MONGO_URI="mongodb+srv://username:password@cluster.mongodb.net/"
python app.py
```

## Project Structure
```
ppn/
├── app.py                  # Main Flask application
├── requirements.txt
├── static/
│   ├── css/
│   │   ├── style.css       # Main stylesheet
│   │   └── admin.css       # Admin panel styles
│   ├── js/main.js
│   └── uploads/            # Uploaded PDFs
└── templates/
    ├── base.html           # Shared layout
    ├── home.html           # Landing page
    ├── papers.html         # Search & filter
    ├── upload.html         # Paper upload
    ├── view_paper.html     # Paper viewer
    ├── login.html          # Login/Register
    ├── about.html
    └── admin/
        ├── base.html       # Admin layout
        ├── dashboard.html
        ├── papers.html
        ├── colleges.html
        ├── branches.html
        └── users.html
```

## Seeded Data
On first run, the app seeds:
- 8 colleges (Tamil Nadu focused)
- 7 branches (CSE, ECE, EEE, MECH, CIVIL, IT, AIDS)
- 19 subjects across branches
- 6 sample papers
- 1 admin account

## Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| MONGO_URI | mongodb://localhost:27017/ | MongoDB connection string |
| SECRET_KEY | (hardcoded) | Flask session secret — change in production |
