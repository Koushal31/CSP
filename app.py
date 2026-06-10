from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, abort, flash
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import sys
import datetime
import functools
import uuid
import logging

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    logger.error('FATAL: SECRET_KEY environment variable not set')
    raise ValueError('SECRET_KEY environment variable is required')

# Upload folder configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), 'static', 'uploads'))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # HTTPS only in production

ALLOWED_EXTENSIONS = {'pdf'}

# MongoDB Connection with error handling
MONGO_URI = os.environ.get('MONGO_URI')
if not MONGO_URI:
    logger.error('FATAL: MONGO_URI environment variable not set')
    raise ValueError('MONGO_URI environment variable is required')

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    # Test connection
    client.admin.command('ping')
    db = client['previous_papers_navigator']
    logger.info('Connected to MongoDB successfully')
except (ServerSelectionTimeoutError, ConnectionFailure) as e:
    logger.error(f'Failed to connect to MongoDB: {e}')
    raise

# Collections
users_col = db['users']
papers_col = db['papers']
colleges_col = db['colleges']
branches_col = db['branches']
subjects_col = db['subjects']

# Create indexes for better performance
try:
    users_col.create_index('email', unique=True)
    papers_col.create_index('status')
    papers_col.create_index([('college', 1), ('branch', 1), ('semester', 1), ('subject', 1)])
    branches_col.create_index('college_code')
    subjects_col.create_index([('branch_code', 1), ('semester', 1)])
    logger.info('Database indexes created successfully')
except Exception as e:
    logger.warning(f'Index creation warning: {e}')

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

def get_object_id(value):
    try:
        return ObjectId(value)
    except Exception:
        return None

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            logger.warning(f'Unauthorized admin access attempt from {request.remote_addr}')
            abort(403)
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_template_globals():
    # Only query for pending count if user is admin
    pending_count = 0
    if session.get('role') == 'admin':
        try:
            pending_count = papers_col.count_documents({'status': 'pending'})
        except Exception as e:
            logger.error(f'Error counting pending papers: {e}')
    return {'admin_pending_count': pending_count}

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', code=404, message='Page not found'), 404

@app.errorhandler(403)
def forbidden(error):
    return render_template('error.html', code=403, message='Access denied'), 403

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal server error: {error}')
    return render_template('error.html', code=500, message='Server error'), 500

# ─── Startup Initialization ───────────────────────────────────────────────

def ensure_admin_user():
    try:
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@gmail.com')
        admin_password = os.environ.get('ADMIN_PASSWORD', '1234')
        
        existing_admin = users_col.find_one({"email": admin_email})
        if not existing_admin:
            users_col.insert_one({
                "name": "Admin",
                "email": admin_email,
                "password": generate_password_hash(admin_password),
                "role": "admin",
                "college": "",
                "created_at": utcnow()
            })
            logger.info(f'Admin user created: {admin_email}')
    except Exception as e:
        logger.error(f'Error ensuring admin user: {e}')

ensure_admin_user()

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    total_papers = papers_col.count_documents({"status": "approved"})
    total_colleges = colleges_col.count_documents({})
    total_users = users_col.count_documents({})
    colleges = list(colleges_col.find({}, {"_id": 0, "name": 1, "code": 1}).sort("name", 1))
    branches = list(branches_col.find({}, {"_id": 0, "name": 1, "code": 1, "college_code": 1}).sort([("college_code", 1), ("name", 1)]))
    semesters = list(range(1, 9))
    return render_template('home.html',
                           total_papers=total_papers,
                           total_colleges=total_colleges,
                           total_users=total_users,
                           colleges=colleges,
                           branches=branches,
                           semesters=semesters)

@app.route('/papers')
def papers():
    colleges = list(colleges_col.find({}, {"_id": 0, "name": 1, "code": 1}))
    branches = list(branches_col.find({}, {"_id": 0, "name": 1, "code": 1}))
    semesters = list(range(1, 9))

    # Filter params
    college = request.args.get('college', '')
    branch = request.args.get('branch', '')
    semester = request.args.get('semester', '')
    subject = request.args.get('subject', '')
    year = request.args.get('year', '')

    query = {"status": "approved"}
    if college:
        query["college"] = college
    if branch:
        query["branch"] = branch
    if semester:
        try:
            query["semester"] = int(semester)
        except ValueError:
            pass
    if subject:
        query["subject"] = {"$regex": subject, "$options": "i"}
    if year:
        try:
            query["year"] = int(year)
        except ValueError:
            pass

    results = list(papers_col.find(query).sort("year", -1))
    for p in results:
        p['_id'] = str(p['_id'])
    searched = any([college, branch, semester, subject, year])

    return render_template('papers.html',
                           colleges=colleges,
                           branches=branches,
                           semesters=semesters,
                           results=results,
                           searched=searched,
                           filters={"college": college, "branch": branch,
                                    "semester": semester, "subject": subject, "year": year})

@app.route('/api/branches')
def api_branches():
    try:
        college = request.args.get('college', '').strip()
        query = {}
        if college:
            query["college_code"] = college
        branches = list(branches_col.find(query, {"_id": 0, "name": 1, "code": 1, "college_code": 1}))
        return jsonify(branches)
    except Exception as e:
        logger.error(f'Error fetching branches: {e}')
        return jsonify([]), 500


@app.route('/api/subjects')
def api_subjects():
    try:
        branch = request.args.get('branch', '').strip()
        semester = request.args.get('semester', '').strip()
        query = {}
        if branch:
            query["branch_code"] = branch
        if semester:
            try:
                query["semester"] = int(semester)
            except ValueError:
                pass
        subjects = list(subjects_col.find(query, {"_id": 0, "name": 1}))
        return jsonify([s['name'] for s in subjects])
    except Exception as e:
        logger.error(f'Error fetching subjects: {e}')
        return jsonify([]), 500


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    colleges = list(colleges_col.find({}, {"_id": 0, "name": 1, "code": 1}).sort("name", 1))
    branches = list(branches_col.find({}, {"_id": 0, "name": 1, "code": 1, "college_code": 1}).sort([("college_code", 1), ("name", 1)]))
    semesters = list(range(1, 9))
    form_data = {}

    if request.method == 'POST':
        college_code = request.form.get('college')
        branch = request.form.get('branch')
        semester = request.form.get('semester')
        subject = request.form.get('subject')
        year = request.form.get('year')
        file = request.files.get('pdf')
        form_data = request.form

        college_doc = colleges_col.find_one({"code": college_code}) if college_code else None
        valid_branches = [b['code'] for b in branches if b.get('college_code') == college_code]

        if not all([college_code, branch, semester, subject, year, file]):
            return render_template('upload.html', colleges=colleges, branches=branches,
                                   semesters=semesters, form_data=form_data,
                                   error="All fields are required.")

        if not college_doc or branch not in valid_branches:
            return render_template('upload.html', colleges=colleges, branches=branches,
                                   semesters=semesters, form_data=form_data,
                                   error="Please select a valid college and branch for the selected college.")

        try:
            semester_num = int(semester)
            year_num = int(year)
        except ValueError:
            return render_template('upload.html', colleges=colleges, branches=branches,
                                   semesters=semesters, form_data=form_data,
                                   error="Semester and year must be valid numbers.")

        if semester_num < 1 or semester_num > 8:
            return render_template('upload.html', colleges=colleges, branches=branches,
                                   semesters=semesters, form_data=form_data,
                                   error="Semester must be between 1 and 8.")

        current_year = datetime.datetime.now().year
        if year_num < 2000 or year_num > current_year + 1:
            return render_template('upload.html', colleges=colleges, branches=branches,
                                   semesters=semesters, form_data=form_data,
                                   error="Please enter a valid year.")

        if file and allowed_file(file.filename):
            try:
                college_name = college_doc['name']
                unique_suffix = uuid.uuid4().hex[:8]
                filename = secure_filename(f"{college_name}_{branch}_sem{semester}_{subject}_{year}_{unique_suffix}.pdf")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                papers_col.insert_one({
                    "subject": subject,
                    "branch": branch,
                    "semester": semester_num,
                    "year": year_num,
                    "college": college_name,
                    "filename": filename,
                    "status": "pending",
                    "uploaded_by": session.get('email'),
                    "uploaded_at": utcnow(),
                    "downloads": 0
                })
                logger.info(f'Paper uploaded by {session.get("email")}: {filename}')
                flash("Paper uploaded successfully! It will be visible after admin approval.", "success")
                return render_template('upload.html', colleges=colleges, branches=branches,
                                       semesters=semesters, form_data={})
            except IOError as e:
                logger.error(f'File save error: {e}')
                return render_template('upload.html', colleges=colleges, branches=branches,
                                       semesters=semesters, form_data=form_data,
                                       error="Error saving file. Please try again.")
            except Exception as e:
                logger.error(f'Error uploading paper: {e}')
                return render_template('upload.html', colleges=colleges, branches=branches,
                                       semesters=semesters, form_data=form_data,
                                       error="An error occurred during upload. Please try again.")
        else:
            return render_template('upload.html', colleges=colleges, branches=branches,
                                   semesters=semesters, form_data=form_data,
                                   error="Only PDF files are allowed.")

    return render_template('upload.html', colleges=colleges, branches=branches, semesters=semesters, form_data=form_data)

@app.route('/paper/<paper_id>')
def view_paper(paper_id):
    object_id = get_object_id(paper_id)
    if object_id is None:
        return redirect(url_for('papers'))

    paper = papers_col.find_one({"_id": object_id, "status": "approved"})
    if not paper:
        return redirect(url_for('papers'))
    paper['_id'] = str(paper['_id'])
    return render_template('view_paper.html', paper=paper)

@app.route('/download/<paper_id>')
def download_paper(paper_id):
    try:
        object_id = get_object_id(paper_id)
        if object_id is None:
            logger.warning(f'Invalid paper_id format: {paper_id}')
            return jsonify({"error": "Not found"}), 404

        paper = papers_col.find_one({"_id": object_id, "status": "approved"})
        if not paper:
            logger.warning(f'Paper not found or not approved: {paper_id}')
            return jsonify({"error": "Not found"}), 404

        if paper.get('filename'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(paper['filename']))
            if os.path.exists(filepath):
                try:
                    papers_col.update_one({"_id": object_id}, {"$inc": {"downloads": 1}})
                except Exception as e:
                    logger.error(f'Error updating download count: {e}')
                return send_from_directory(app.config['UPLOAD_FOLDER'], secure_filename(paper['filename']), as_attachment=True)
            else:
                logger.error(f'File not found on disk: {filepath}')
                flash("The requested file is not available on the server.", "error")
                return redirect(url_for('view_paper', paper_id=paper_id))

        flash("This paper does not have an attached PDF.", "warning")
        return redirect(url_for('view_paper', paper_id=paper_id))
    except Exception as e:
        logger.error(f'Error in download_paper: {e}')
        flash("An error occurred while downloading the paper.", "error")
        return redirect(url_for('papers'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('home'))

    colleges = list(colleges_col.find({}, {"_id": 0, "name": 1}))
    login_email = ''
    active_tab = 'login'
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        login_email = email

        user = users_col.find_one({"email": email})
        if user and user.get('password') and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['email'] = user['email']
            session['name'] = user['name']
            session['role'] = user.get('role', 'student')
            if user.get('role') == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('home'))
        return render_template('login.html', error="Invalid email or password.", email=login_email,
                               colleges=colleges, active_tab=active_tab)

    return render_template('login.html', email=login_email, colleges=colleges, active_tab=active_tab)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))

    colleges = list(colleges_col.find({}, {"_id": 0, "name": 1}))
    form_data = {}
    active_tab = 'register'

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        college = request.form.get('college', '')
        form_data = request.form

        if not name or not email or not password:
            return render_template('login.html', reg_error="All fields are required.", colleges=colleges,
                                   active_tab=active_tab, form_data=form_data)

        if len(password) < 6:
            return render_template('login.html', reg_error="Password must be at least 6 characters.", colleges=colleges,
                                   active_tab=active_tab, form_data=form_data)

        if users_col.find_one({"email": email}):
            return render_template('login.html', reg_error="Email already registered.", colleges=colleges,
                                   active_tab=active_tab, form_data=form_data)

        users_col.insert_one({
            "name": name,
            "email": email,
            "password": generate_password_hash(password),
            "role": "student",
            "college": college,
            "created_at": utcnow()
        })
        return render_template('login.html', reg_success="Registered! Please log in.", colleges=colleges)

    return render_template('login.html', colleges=colleges, active_tab=active_tab, form_data=form_data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/about')
def about():
    return render_template('about.html')

# ─── Admin Routes ─────────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_dashboard():
    total_papers = papers_col.count_documents({"status": "approved"})
    pending_papers = papers_col.count_documents({"status": "pending"})
    total_users = users_col.count_documents({})
    total_branches = branches_col.count_documents({})
    total_colleges = colleges_col.count_documents({})
    total_subjects = subjects_col.count_documents({})

    recent_pending = list(papers_col.find({"status": "pending"}).sort("uploaded_at", -1).limit(10))
    for p in recent_pending:
        p['_id'] = str(p['_id'])

    return render_template('admin/dashboard.html',
                           total_papers=total_papers,
                           pending_papers=pending_papers,
                           total_users=total_users,
                           total_branches=total_branches,
                           total_colleges=total_colleges,
                           total_subjects=total_subjects,
                           recent_pending=recent_pending)

@app.route('/admin/papers')
@admin_required
def admin_papers():
    status_filter = request.args.get('status', 'all')
    query = {} if status_filter == 'all' else {"status": status_filter}
    all_papers = list(papers_col.find(query).sort("uploaded_at", -1))
    for p in all_papers:
        p['_id'] = str(p['_id'])
    return render_template('admin/papers.html', papers=all_papers, status_filter=status_filter)

@app.route('/admin/paper/<paper_id>/approve', methods=['POST'])
@admin_required
def approve_paper(paper_id):
    object_id = get_object_id(paper_id)
    if object_id is None:
        abort(404)

    papers_col.update_one({"_id": object_id}, {"$set": {"status": "approved"}})
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/paper/<paper_id>')
@admin_required
def admin_view_paper(paper_id):
    object_id = get_object_id(paper_id)
    if object_id is None:
        abort(404)

    paper = papers_col.find_one({"_id": object_id})
    if not paper:
        abort(404)

    paper['_id'] = str(paper['_id'])
    return render_template('admin/view_paper.html', paper=paper)

@app.route('/admin/paper/<paper_id>/download')
@admin_required
def admin_download_paper(paper_id):
    object_id = get_object_id(paper_id)
    if object_id is None:
        abort(404)

    paper = papers_col.find_one({"_id": object_id})
    if not paper or not paper.get('filename'):
        abort(404)

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], paper['filename'])
    if not os.path.exists(filepath):
        abort(404)

    return send_from_directory(app.config['UPLOAD_FOLDER'], paper['filename'], as_attachment=True)

@app.route('/admin/paper/<paper_id>/reject', methods=['POST'])
@admin_required
def reject_paper(paper_id):
    object_id = get_object_id(paper_id)
    if object_id is None:
        abort(404)

    papers_col.update_one({"_id": object_id}, {"$set": {"status": "rejected"}})
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/paper/<paper_id>/delete', methods=['POST'])
@admin_required
def delete_paper(paper_id):
    object_id = get_object_id(paper_id)
    if object_id is None:
        abort(404)

    paper = papers_col.find_one({"_id": object_id})
    if paper and paper.get('filename'):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], paper['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    papers_col.delete_one({"_id": object_id})
    return redirect(request.referrer or url_for('admin_papers'))

@app.route('/admin/colleges', methods=['GET', 'POST'])
@admin_required
def admin_colleges():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip().upper()
        city = request.form.get('city', '').strip()
        if not name or not code:
            flash("College name and code are required.", "error")
            return redirect(url_for('admin_colleges'))
        if colleges_col.find_one({"code": code}):
            flash(f"College code '{code}' already exists.", "error")
            return redirect(url_for('admin_colleges'))
        colleges_col.insert_one({"name": name, "code": code, "city": city})
        flash(f"College '{name}' added successfully.", "success")
        return redirect(url_for('admin_colleges'))

    all_colleges = list(colleges_col.find().sort("name", 1))
    for c in all_colleges:
        c['_id'] = str(c['_id'])
        c['paper_count'] = papers_col.count_documents({"college": c['name'], "status": "approved"})
    return render_template('admin/colleges.html', colleges=all_colleges)

@app.route('/admin/college/<college_id>/delete', methods=['POST'])
@admin_required
def delete_college(college_id):
    object_id = get_object_id(college_id)
    if object_id is None:
        abort(404)
    college = colleges_col.find_one({"_id": object_id})
    if not college:
        abort(404)
    dependent_papers = papers_col.count_documents({"college": college['name']})
    dependent_branches = branches_col.count_documents({"college_code": college['code']})
    if dependent_papers or dependent_branches:
        flash("Cannot delete this college because branches or papers are still associated with it.", "error")
        return redirect(url_for('admin_colleges'))
    colleges_col.delete_one({"_id": object_id})
    flash(f"College '{college['name']}' deleted successfully.", "success")
    return redirect(url_for('admin_colleges'))

@app.route('/admin/branches', methods=['GET', 'POST'])
@admin_required
def admin_branches():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip().upper()
        college_code = request.form.get('college_code', '').strip().upper()
        if not name or not code or not college_code:
            flash("Branch name, code, and college are required.", "error")
            return redirect(url_for('admin_branches'))
        if not colleges_col.find_one({"code": college_code}):
            flash(f"College code '{college_code}' does not exist.", "error")
            return redirect(url_for('admin_branches'))
        if branches_col.find_one({"code": code, "college_code": college_code}):
            flash(f"Branch code '{code}' already exists for this college.", "error")
            return redirect(url_for('admin_branches'))
        branches_col.insert_one({"name": name, "code": code, "college_code": college_code})
        flash(f"Branch '{name}' added successfully.", "success")
        return redirect(url_for('admin_branches'))

    all_branches = list(branches_col.find().sort([("college_code", 1), ("name", 1)]))
    college_map = {c['code']: c['name'] for c in colleges_col.find({}, {"code": 1, "name": 1})}
    for b in all_branches:
        b['_id'] = str(b['_id'])
        b['college_name'] = college_map.get(b.get('college_code'), 'Unknown')
    colleges = list(colleges_col.find({}, {"_id": 0, "name": 1, "code": 1}).sort("name", 1))
    return render_template('admin/branches.html', branches=all_branches, colleges=colleges)

@app.route('/admin/branches/<branch_id>/delete', methods=['POST'])
@admin_required
def delete_branch(branch_id):
    object_id = get_object_id(branch_id)
    if object_id is None:
        abort(404)
    branch = branches_col.find_one({"_id": object_id})
    if not branch:
        abort(404)
    dependent_papers = papers_col.count_documents({"branch": branch['code']})
    dependent_subjects = subjects_col.count_documents({"branch_code": branch['code']})
    if dependent_papers or dependent_subjects:
        flash("Cannot delete this branch because papers or subjects are still associated with it.", "error")
        return redirect(url_for('admin_branches'))
    branches_col.delete_one({"_id": object_id})
    flash(f"Branch '{branch['name']}' deleted successfully.", "success")
    return redirect(url_for('admin_branches'))

@app.route('/admin/subjects', methods=['GET', 'POST'])
@admin_required
def admin_subjects():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        college_code = request.form.get('college_code', '').strip().upper()
        branch_code = request.form.get('branch_code', '').strip().upper()
        semester = request.form.get('semester', '').strip()

        if not name or not college_code or not branch_code or not semester:
            flash("Subject name, college, branch, and semester are required.", "error")
            return redirect(url_for('admin_subjects'))

        try:
            semester_num = int(semester)
        except ValueError:
            flash("Semester must be a number.", "error")
            return redirect(url_for('admin_subjects'))

        if semester_num < 1 or semester_num > 10:
            flash("Semester must be between 1 and 10.", "error")
            return redirect(url_for('admin_subjects'))

        if not colleges_col.find_one({"code": college_code}):
            flash(f"College code '{college_code}' does not exist.", "error")
            return redirect(url_for('admin_subjects'))

        branch = branches_col.find_one({"code": branch_code, "college_code": college_code})
        if not branch:
            flash(f"Branch code '{branch_code}' does not exist for the selected college.", "error")
            return redirect(url_for('admin_subjects'))

        if subjects_col.find_one({"name": name, "college_code": college_code, "branch_code": branch_code, "semester": semester_num}):
            flash("This subject already exists for the selected college, branch, and semester.", "error")
            return redirect(url_for('admin_subjects'))

        subjects_col.insert_one({
            "name": name,
            "college_code": college_code,
            "branch_code": branch_code,
            "semester": semester_num
        })
        flash(f"Subject '{name}' added successfully.", "success")
        return redirect(url_for('admin_subjects'))

    colleges = list(colleges_col.find({}, {"_id": 0, "name": 1, "code": 1}).sort("name", 1))
    branches = list(branches_col.find({}, {"_id": 0, "name": 1, "code": 1, "college_code": 1}).sort([("college_code", 1), ("name", 1)]))
    subjects = list(subjects_col.find().sort([("college_code", 1), ("branch_code", 1), ("semester", 1), ("name", 1)]))

    college_map = {c['code']: c['name'] for c in colleges}
    branch_map = {(b['college_code'], b['code']): b for b in branches}
    for s in subjects:
        s['_id'] = str(s['_id'])
        college_key = s.get('college_code', '')
        branch_key = (college_key, s.get('branch_code', ''))
        branch = branch_map.get(branch_key)
        if not branch:
            # fallback if older records do not store college_code
            fallback = next((b for b in branches if b['code'] == s.get('branch_code')), None)
            if fallback:
                branch = fallback
                college_key = branch.get('college_code', '')
                s['college_code'] = college_key
        s['branch_name'] = branch['name'] if branch else 'Unknown'
        s['college_name'] = college_map.get(college_key, 'Unknown')

    return render_template('admin/subjects.html', subjects=subjects, branches=branches, colleges=colleges)

@app.route('/admin/subjects/<subject_id>/delete', methods=['POST'])
@admin_required
def delete_subject(subject_id):
    object_id = get_object_id(subject_id)
    if object_id is None:
        abort(404)
    subject = subjects_col.find_one({"_id": object_id})
    if not subject:
        abort(404)
    subjects_col.delete_one({"_id": object_id})
    flash(f"Subject '{subject['name']}' deleted successfully.", "success")
    return redirect(url_for('admin_subjects'))

@app.route('/admin/users')
@admin_required
def admin_users():
    all_users = list(users_col.find({}, {"password": 0}).sort("created_at", -1))
    for u in all_users:
        u['_id'] = str(u['_id'])
    return render_template('admin/users.html', users=all_users)

@app.route('/admin/user/<user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    object_id = get_object_id(user_id)
    if object_id is None:
        abort(404)
    users_col.delete_one({"_id": object_id})
    return redirect(url_for('admin_users'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
