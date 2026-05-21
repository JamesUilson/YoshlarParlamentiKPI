#app.py

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify, Response
import os
import psycopg2
import psycopg2.extras
import random
import string
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO, StringIO
import csv
from flask_cors import CORS
from functools import wraps
import hashlib
import binascii

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Jinja2 custom date filter
@app.template_filter('format_date')
def format_date_filter(val):
    if not val:
        return '—'
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d')
    # If it's a string
    return str(val)[:10]

# PostgreSQL ulanish URL
_db_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL', '')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['DATABASE_URL'] = _db_url
CORS(app)  # CORS ni yoqamiz

# Ruxsat berilgan fayl kengaytmalari
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'zip', 'rar'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# def get_regions():
#     return {
#         '01': 'Toshkent shahri',
#         '02': 'Toshkent viloyati',
#         '03': 'Andijon viloyati',
#         '04': 'Fargʻona viloyati',
#         '05': 'Namangan viloyati',
#         '06': 'Samarqand viloyati',
#         '07': 'Buxoro viloyati',
#         '08': 'Xorazm viloyati',
#         '09': 'Surxondaryo viloyati',
#         '10': 'Qashqadaryo viloyati',
#         '11': 'Jizzax viloyati',
#         '12': 'Sirdaryo viloyati',
#         '13': 'Navoiy viloyati',
#         '14': 'Qoraqalpogʻiston Respublikasi'
#     }

# Ma'lumotlar bazasini yaratish VA TEST MA'LUMOTLARNI QO'SHISH
# 2. DATABASE INIT funksiyasini to'g'rilash (jadval strukturasini to'g'rilash):
def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Foydalanuvchilar jadvali (TELEFON ustunini O'CHIRAMIZ yoki QO'SHAMIZ)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT UNIQUE,
                    password TEXT,
                    full_name TEXT,
                    district TEXT,
                    age INTEGER,
                    role TEXT DEFAULT 'user',
                    rating INTEGER DEFAULT 0,
                    joined_date DATE DEFAULT CURRENT_DATE,
                    last_login TIMESTAMP
                )''')
    # Baholash jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS task_ratings (
                    id SERIAL PRIMARY KEY,
                    task_id TEXT,
                    rated_by TEXT,  # kim baholadi
                    rated_to TEXT,  # kimga baho berildi
                    quality INTEGER DEFAULT 0,  # 0-10
                    timeliness INTEGER DEFAULT 0,  # 0-10
                    completeness INTEGER DEFAULT 0,  # 0-10
                    creativity INTEGER DEFAULT 0,  # 0-10
                    total_score INTEGER DEFAULT 0,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES user_tasks(task_id),
                    FOREIGN KEY (rated_by) REFERENCES users(user_id),
                    FOREIGN KEY (rated_to) REFERENCES users(user_id)
                )''')

    # Monitoring jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS admin_monitoring (
                    id SERIAL PRIMARY KEY,
                    admin_id TEXT,
                    admin_name TEXT,
                    action_type TEXT,  # task_created/task_assigned/task_completed/report_rated
                    target_id TEXT,  # task_id yoki user_id
                    target_name TEXT,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES users(user_id)
                )''')

    
    # Hisobotlar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    month_year TEXT,
                    event_count INTEGER DEFAULT 0,
                    material_count INTEGER DEFAULT 0,
                    message_count INTEGER DEFAULT 0,
                    safety_score INTEGER DEFAULT 5,
                    file_path TEXT,
                    description TEXT,
                    challenges TEXT,
                    suggestions TEXT,
                    status TEXT DEFAULT 'pending',
                    admin_comment TEXT,
                    submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )''')
    
    # Baholar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
                    id SERIAL PRIMARY KEY,
                    report_id INTEGER,
                    faollik INTEGER,
                    tashabbus INTEGER,
                    intizom INTEGER,
                    tasir INTEGER,
                    total INTEGER,
                    admin_comment TEXT,
                    rated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (report_id) REFERENCES reports(id)
                )''')
    
    # Topshiriqlar jadvali (yangi)
    c.execute('''CREATE TABLE IF NOT EXISTS user_tasks (
                    id SERIAL PRIMARY KEY,
                    task_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT,
                    assigned_to TEXT,  # "all" yoki user_id
                    assigned_by TEXT,  # kim topshirgan
                    deadline DATE,
                    points INTEGER DEFAULT 5,
                    task_type TEXT DEFAULT 'regular',
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'pending',  # pending/in_progress/completed/cancelled
                    progress INTEGER DEFAULT 0,  # 0-100%
                    completed_by TEXT,
                    completed_at DATETIME,
                    feedback TEXT,
                    rating_given INTEGER,  # 1-5 yulduz
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assigned_by) REFERENCES users(user_id)
                )''')

    # Reytinglar jadvali (yangi)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            id SERIAL PRIMARY KEY,
            task_id TEXT UNIQUE,
            title TEXT NOT NULL,
            description TEXT,
            assigned_to TEXT,
            assigned_by TEXT,
            deadline DATE,
            points INTEGER DEFAULT 5,
            task_type TEXT DEFAULT 'regular',
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            completed_by TEXT,
            completed_at TIMESTAMP,
            feedback TEXT,
            rating_given INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_by) REFERENCES users(user_id)
        )
    ''')
    
    # SISTEM LOGLARI JADVALINI QO'SHAMIZ
    c.execute('''CREATE TABLE IF NOT EXISTS system_logs (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    action TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # TEST MA'LUMOTLARNI QO'SHISH
    test_users = [
        ('FR-2024-001', generate_password_hash('test123'), 'Ali Valiyev', 'Yunusobod', 22, 'user'),
        ('FR-2024-002', generate_password_hash('test123'), 'Malika Karimova', 'Mirzo Ulugʻbek', 24, 'user'),
        ('admin001', generate_password_hash('admin123'), 'Admin User', 'Toshkent', 30, 'admin'),
        ('debug001', generate_password_hash('debug123'), 'Super Admin', 'Toshkent', 35, 'debugger')
    ]
    
    for user_id, password, full_name, district, age, role in test_users:
        try:
            c.execute('''INSERT OR IGNORE INTO users 
                        (user_id, password, full_name, district, age, role) 
                        VALUES (%s, %s, %s, %s, %s, %s)''', 
                      (user_id, password, full_name, district, age, role))
        except Exception as e:
            print(f"Foydalanuvchi qo'shishda xatolik {user_id}: {e}")
    
    # Test hisobotlar
    test_reports = [
        ('FR-2024-001', '2024-01', 5, 3, 2, 7, None, 'Yanvar oyi hisoboti', 'Muammolar yoʻq', 'Takliflar mavjud', 'pending', None),
        ('FR-2024-002', '2024-01', 3, 2, 1, 6, None, 'Birinchi hisobot', 'Bir oz qiyinchiliklar', '', 'pending', None),
    ]
    
    for user_id, month_year, event_count, material_count, message_count, safety_score, file_path, description, challenges, suggestions, status, admin_comment in test_reports:
        try:
            c.execute('''INSERT OR IGNORE INTO reports 
                        (user_id, month_year, event_count, material_count, 
                         message_count, safety_score, file_path, description,
                         challenges, suggestions, status, admin_comment) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                      (user_id, month_year, event_count, material_count, message_count, safety_score, file_path, description, challenges, suggestions, status, admin_comment))
        except Exception as e:
            print(f"Hisobot qo'shishda xatolik {user_id}: {e}")
    
    # Test topshiriqlar
    test_tasks = [
        ('Birinci topshiriq', 'Bu test topshirig\'i', 'Admin', '2024-02-01'),
        ('Ikkinchi topshiriq', 'Yana bir test topshirig\'i', 'Admin', '2024-02-10'),
    ]
    
    for title, description, created_by, created_date in test_tasks:
        try:
            c.execute('''INSERT OR IGNORE INTO tasks 
                        (title, description, created_by, created_date) 
                        VALUES (%s, %s, %s, %s)''',
                      (title, description, created_by, created_date))
        except Exception as e:
            print(f"Topshiriq qo'shishda xatolik: {e}")
    
    conn.commit()
    conn.close()
    print("✅ Database yaratildi va test ma'lumotlar qo'shildi!")

# app.py faylining boshida
def role_required(roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'success': False, 'error': 'Tizimga kiring'}), 401
            
            user_role = session.get('role', 'user')
            
            if user_role not in roles:
                return jsonify({
                    'success': False, 
                    'error': f'Ruxsat yo\'q. Sizning rolingiz: {user_role}'
                }), 403
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

# login_required dekoratoridan keyin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # Database connection olish
        conn = get_db_connection()
        user = conn.execute('SELECT role FROM users WHERE id = %s', (session['user_id'],)).fetchone()
        conn.close()
        
        # Admin huquqlarini tekshirish
        if user and user['role'] in ['admin', 'debugger']:
            return f(*args, **kwargs)
        else:
            flash('Bu sahifaga kirish uchun admin huquqlari kerak', 'error')
            return redirect(url_for('dashboard'))  # yoki login sahifasiga
    
    return decorated_function

@app.context_processor
def inject_common_variables():
    def generate_password(length=8):
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def get_regions():
        return {
            '01': 'Toshkent shahri',
            '02': 'Toshkent viloyati',
            '03': 'Andijon viloyati',
            '04': 'Fargʻona viloyati',
            '05': 'Namangan viloyati',
            '06': 'Samarqand viloyati',
            '07': 'Buxoro viloyati',
            '08': 'Xorazm viloyati',
            '09': 'Surxondaryo viloyati',
            '10': 'Qashqadaryo viloyati',
            '11': 'Jizzax viloyati',
            '12': 'Sirdaryo viloyati',
            '13': 'Navoiy viloyati',
            '14': 'Qoraqalpogʻiston Respublikasi'
        }
    
    return dict(
        generate_password=generate_password,
        regions=get_regions(),
        current_year=datetime.now().year
    )

def get_db():
    """PostgreSQL ulanish olish"""
    url = app.config.get('DATABASE_URL', '')
    if not url:
        raise RuntimeError('DATABASE_URL environment variable is not set')
    return psycopg2.connect(url)

# Asosiy marshrutlar
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']
        
        print(f"🔑 Login urinishi: ID={user_id}")  # Debug
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        conn.close()
        
        if user:
            print(f"✅ Foydalanuvchi topildi: {user[1]}")  # Debug
            
            # Parolni tekshirish
            if user[2] and check_password_hash(user[2], password):
                session['user_id'] = user[1]
                session['full_name'] = user[3]
                session['role'] = user[6]
                session['district'] = user[4]
                
                print(f"🚀 Kirish muvaffaqiyatli: {user[1]} - {user[6]}")  # Debug
                
                if user[6] == 'admin':
                    return redirect(url_for('admin_panel'))
                elif user[6] == 'debugger':
                    return redirect(url_for('debugger'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                print("❌ Noto'g'ri parol")
                flash('Notoʻgʻri parol!')
        else:
            print("❌ Foydalanuvchi topilmadi")
            flash('Foydalanuvchi topilmadi!')
    
    return render_template('login.html')

#################################################################
################ FOYDALANUVCHI DASHBOARDI #######################
#################################################################

# Dashboard funksiyasini o'zgartiramiz
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Agar admin bo'lsa, admin dashboardga yo'naltiramiz
    if session.get('role') in ['admin', 'debugger']:
        return redirect(url_for('admin_panel'))
    
    # Userlar uchun oddiy dashboard
    conn = get_db()
    c = conn.cursor()
    
    # Foydalanuvchining hisobotlari
    c.execute("SELECT * FROM reports WHERE user_id = %s ORDER BY submitted_date DESC", (session['user_id'],))
    reports = c.fetchall()
    
    # Topshiriqlar
    c.execute("SELECT * FROM user_tasks WHERE (assigned_to = %s OR assigned_to = 'all') AND status != 'completed' ORDER BY deadline ASC LIMIT 5", 
              (session['user_id'],))
    tasks = c.fetchall()
    
    # Reyting
    c.execute("SELECT rating FROM users WHERE user_id = %s", (session['user_id'],))
    rating_result = c.fetchone()
    rating = rating_result[0] if rating_result else 0
    
    conn.close()
    
    return render_template('dashboard.html', 
                         full_name=session['full_name'],
                         reports=reports,
                         tasks=tasks,
                         rating=rating,
                         district=session.get('district', ''))


# # Yangi admin dashboard endpointi
# @app.route('/admin_dashboard')
# def admin_dashboard():
#     if 'user_id' not in session or session.get('role') not in ['admin', 'debugger']:
#         return redirect(url_for('login'))
    
#     conn = get_db()
#     c = conn.cursor()
    
#     # Statistikalar
#     c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
#     total_users = c.fetchone()[0] or 0
    
#     c.execute("SELECT COUNT(*) FROM reports WHERE status = 'pending'")
#     pending_reports = c.fetchone()[0] or 0
    
#     c.execute("SELECT AVG(rating) FROM users WHERE role = 'user'")
#     avg_rating_result = c.fetchone()
#     avg_rating = avg_rating_result[0] if avg_rating_result else 0
    
#     c.execute("SELECT COUNT(*) FROM user_tasks WHERE status IN ('pending', 'in_progress')")
#     active_tasks = c.fetchone()[0] or 0
    
#     conn.close()
    
#     return render_template('admin_dashboard.html',
#                          total_users=total_users,
#                          pending_reports=pending_reports,
#                          avg_rating=avg_rating,
#                          active_tasks=active_tasks)

@app.route('/submit_report', methods=['GET', 'POST'])
def submit_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        month = request.form['month_year']
        # Yilni avtomatik qo'shish
        current_year = datetime.now().year
        month_year = f"{current_year}-{month}"
        
        event_count = request.form['event_count']
        material_count = request.form['material_count']
        message_count = request.form['message_count']
        safety_score = request.form['safety_score']
        description = request.form.get('description', '')
        challenges = request.form.get('challenges', '')
        suggestions = request.form.get('suggestions', '')
        
        # Fayl yuklash
        filename = None
        if 'report_file' in request.files:
            file = request.files['report_file']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    # Fayl nomini xavfsizlashtirish
                    original_filename = secure_filename(file.filename)
                    
                    # Yangi fayl nomi: userid_oy_vaqt.extension
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
                    filename = f"{session['user_id']}_{month_year}_{timestamp}.{file_ext}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Uploads papkasini yaratish
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(file_path)
                else:
                    flash('Fayl formati qoʻllab-quvvatlanmaydi!', 'danger')
                    return redirect(url_for('submit_report'))
        
        # Ma'lumotlar bazasiga saqlash
        conn = get_db()
        c = conn.cursor()
        
        try:
            c.execute('''INSERT INTO reports 
                        (user_id, month_year, event_count, material_count, 
                         message_count, safety_score, file_path, description,
                         challenges, suggestions) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                     (session['user_id'], month_year, event_count, material_count,
                      message_count, safety_score, filename, description,
                      challenges, suggestions))
            
            conn.commit()
            flash('Hisobot muvaffaqiyatli yuborildi!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Xatolik yuz berdi: {str(e)}', 'danger')
            
        finally:
            conn.close()
        
        return redirect(url_for('dashboard'))
    
    return render_template('report.html')

# Dashboard uchun API endpointlarini qo'shamiz

# Dashboard statistik ma'lumotlari
@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        user_id = session['user_id']
        
        # 1. Joriy reyting
        c.execute("SELECT rating FROM users WHERE user_id = %s", (user_id,))
        rating_result = c.fetchone()
        current_rating = rating_result[0] if rating_result else 0
        
        # 2. Topshirilgan hisobotlar soni
        c.execute("SELECT COUNT(*) FROM reports WHERE user_id = %s", (user_id,))
        total_reports = c.fetchone()[0]
        
        # 3. Baholangan hisobotlar soni
        c.execute("SELECT COUNT(*) FROM reports WHERE user_id = %s AND status = 'rated'", (user_id,))
        rated_reports = c.fetchone()[0]
        
        # 4. Faol topshiriqlar soni
        c.execute('''
            SELECT COUNT(*) FROM user_tasks 
            WHERE (assigned_to = %s OR assigned_to = 'all') 
            AND status IN ('pending', 'in_progress')
        ''', (user_id,))
        active_tasks = c.fetchone()[0]
        
        # 5. So'nggi 3 oy hisobotlari
        c.execute('''
            SELECT month_year, status, submitted_date 
            FROM reports 
            WHERE user_id = %s 
            ORDER BY submitted_date DESC 
            LIMIT 5
        ''', (user_id,))
        recent_reports = c.fetchall()
        
        # 6. Yangi topshiriqlar
        c.execute('''
            SELECT ut.*, u.full_name as admin_name
            FROM user_tasks ut
            LEFT JOIN users u ON ut.assigned_by = u.user_id
            WHERE (ut.assigned_to = %s OR ut.assigned_to = 'all')
            AND ut.status IN ('pending', 'in_progress')
            ORDER BY ut.created_at DESC 
            LIMIT 5
        ''', (user_id,))
        recent_tasks = c.fetchall()
        
        # Formatlash
        reports_list = []
        for report in recent_reports:
            reports_list.append({
                'month_year': report[0],
                'status': report[1],
                'submitted_date': report[2]
            })
        
        tasks_list = []
        for task in recent_tasks:
            tasks_list.append({
                'task_id': task[0],
                'title': task[2],
                'description': task[3],
                'deadline': task[6],
                'priority': task[9],
                'status': task[10]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'current_rating': current_rating,
                'total_reports': total_reports,
                'rated_reports': rated_reports,
                'active_tasks': active_tasks
            },
            'recent_reports': reports_list,
            'recent_tasks': tasks_list
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Foydalanuvchi profili ma'lumotlari
@app.route('/api/user/profile')
def api_user_profile():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        user_id = session['user_id']
        
        c.execute('''
            SELECT u.user_id, u.full_name, u.district, u.age, u.role, 
                   u.rating, u.joined_date, u.last_login, u.phone,
                   COUNT(DISTINCT r.id) as total_reports,
                   COUNT(DISTINCT CASE WHEN r.status = 'rated' THEN r.id END) as rated_reports,
                   COUNT(DISTINCT CASE WHEN ut.status = 'completed' THEN ut.id END) as completed_tasks,
                   COALESCE(u.yoshlar_guruhi, '') as yoshlar_guruhi,
                   COALESCE(u.qomita, '') as qomita
            FROM users u
            LEFT JOIN reports r ON u.user_id = r.user_id
            LEFT JOIN user_tasks ut ON (ut.assigned_to = u.user_id OR ut.assigned_to = 'all')
            WHERE u.user_id = %s
            GROUP BY u.user_id
        ''', (user_id,))
        
        user = c.fetchone()
        columns = [desc[0] for desc in c.description]
        
        user_dict = {}
        for i, col in enumerate(columns):
            user_dict[col] = user[i]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'profile': user_dict
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Dashboard uchun qo'shimcha API endpointlari

# Dashboard uchun real ma'lumotlar

@app.route('/api/dashboard/data')
def api_dashboard_data():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        user_id = session['user_id']
        
        # 1. Reyting grafik uchun ma'lumotlar (oxirgi 6 oy)
        c.execute('''
            SELECT 
                to_char(submitted_date, 'YYYY-MM') as month,
                COUNT(*) as report_count,
                AVG(rt.total) as avg_rating
            FROM reports r
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE r.user_id = %s AND r.submitted_date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY to_char(submitted_date, 'YYYY-MM')
            ORDER BY month
        ''', (user_id,))
        
        rating_history = []
        for row in c.fetchall():
            rating_history.append({
                'month': row[0],
                'report_count': row[1],
                'avg_rating': float(row[2]) if row[2] else 0
            })
        
        # 2. Topshiriqlar statistikasi
        c.execute('''
            SELECT 
                status,
                COUNT(*) as count
            FROM user_tasks
            WHERE assigned_to = %s OR assigned_to = 'all'
            GROUP BY status
        ''', (user_id,))
        
        task_stats = []
        for row in c.fetchall():
            task_stats.append({
                'status': row[0],
                'count': row[1]
            })
        
        # 3. Oylik hisobotlar
        c.execute('''
            SELECT 
                month_year,
                event_count,
                material_count,
                message_count,
                safety_score,
                status
            FROM reports
            WHERE user_id = %s
            ORDER BY submitted_date DESC
            LIMIT 6
        ''', (user_id,))
        
        monthly_reports = []
        for row in c.fetchall():
            monthly_reports.append({
                'month_year': row[0],
                'events': row[1],
                'materials': row[2],
                'messages': row[3],
                'safety_score': row[4],
                'status': row[5]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'rating_history': rating_history,
            'task_stats': task_stats,
            'monthly_reports': monthly_reports
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/notifications')
@admin_required
def notifications():
    """Bildirishnomalar sahifasi"""
    # Bildirishnomalarni olish
    notifications = []
    return render_template('notifications.html', notifications=notifications)

@app.route('/api/admin/announcements')
@admin_required
def get_announcements():
    """E'lonlarni olish"""
    try:
        # Ma'lumotlar bazasidan e'lonlarni olish
        announcements = []
        return jsonify(success=True, announcements=announcements)
    except Exception as e:
        return jsonify(success=False, error=str(e))

@app.route('/api/admin/export/<data_type>')
@admin_required
def export_data(data_type):
    """Ma'lumotlarni export qilish"""
    try:
        if data_type == 'reports':
            # Hisobotlarni export qilish
            pass
        elif data_type == 'users':
            # Foydalanuvchilarni export qilish
            pass
        elif data_type == 'ratings':
            # Reytinglarni export qilish
            pass
        return send_file(exported_file, as_attachment=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


# Notificationlar
@app.route('/api/dashboard/notifications')
def api_dashboard_notifications():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        user_id = session['user_id']
        notifications = []
        
        # 1. Yangi topshiriqlar
        c.execute('''
            SELECT COUNT(*) 
            FROM user_tasks 
            WHERE (assigned_to = %s OR assigned_to = 'all') 
            AND status = 'pending'
            AND created_at >= CURRENT_TIMESTAMP
        ''', (user_id,))
        new_tasks = c.fetchone()[0]
        if new_tasks > 0:
            notifications.append({
                'type': 'new_task',
                'message': f'Sizga {new_tasks} ta yangi topshiriq berildi',
                'link': '/user_tasks'
            })
        
        # 2. Baholangan hisobotlar
        c.execute('''
            SELECT COUNT(*) 
            FROM reports 
            WHERE user_id = %s 
            AND status = 'rated'
            AND submitted_date >= CURRENT_TIMESTAMP
        ''', (user_id,))
        rated_reports = c.fetchone()[0]
        if rated_reports > 0:
            notifications.append({
                'type': 'rated_report',
                'message': f'{rated_reports} ta hisobotingiz baholandi',
                'link': '/reports_history'
            })
        
        # 3. Muddati yaqinlashgan topshiriqlar
        c.execute('''
            SELECT COUNT(*) 
            FROM user_tasks 
            WHERE (assigned_to = %s OR assigned_to = 'all')
            AND status IN ('pending', 'in_progress')
            AND deadline BETWEEN CURRENT_DATE AND CURRENT_DATE
        ''', (user_id,))
        upcoming_deadlines = c.fetchone()[0]
        if upcoming_deadlines > 0:
            notifications.append({
                'type': 'deadline',
                'message': f'{upcoming_deadlines} ta topshirig\'ingizning muddati yaqinlashmoqda',
                'link': '/user_tasks'
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'notifications': notifications,
            'count': len(notifications)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Profil sozlamalari sahifasi
# Profile settings ni yangilaymiz
@app.route('/profile_settings')
def profile_settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Agar admin bo'lsa, admin profiliga yo'naltiramiz
    if session.get('role') in ['admin', 'debugger']:
        return redirect(url_for('admin_profile'))
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
    user = c.fetchone()
    
    regions = get_regions()
    conn.close()
    
    return render_template('profile_settings.html', 
                         user=user,
                         regions=regions)

# Yangi admin profil sahifasi
@app.route('/admin_profile')
def admin_profile():
    if 'user_id' not in session or session.get('role') not in ['admin', 'debugger']:
        return redirect(url_for('login'))
    
    conn = get_db()
    c = conn.cursor()
    
    # Foydalanuvchi ma'lumotlari (tuple sifatida)
    c.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
    user = c.fetchone()
    
    if not user:
        flash('Foydalanuvchi topilmadi!', 'danger')
        return redirect(url_for('admin_panel'))
    
    # Hisobotlar soni
    c.execute("SELECT COUNT(*) FROM reports WHERE user_id = %s", (session['user_id'],))
    reports_count = c.fetchone()[0] or 0
    
    conn.close()
    
    return render_template('admin_profile.html', 
                         user=user,
                         reports_count=reports_count)
                         
# Profilni yangilash API
@app.route('/api/user/update_profile', methods=['POST'])
def api_update_profile():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        data = request.json
        user_id = session['user_id']
        
        # Majburiy maydonlarni tekshirish
        required_fields = ['full_name']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} maydoni talab qilinadi'})
        
        conn = get_db()
        c = conn.cursor()
        
        # Parolni tekshirish (agar o'zgartirilishi kerak bo'lsa)
        if 'current_password' in data and 'new_password' in data:
            # Joriy parolni tekshirish
            c.execute("SELECT password FROM users WHERE user_id = %s", (user_id,))
            result = c.fetchone()
            
            if not result or not check_password_hash(result[0], data['current_password']):
                return jsonify({'success': False, 'error': 'Joriy parol noto\'g\'ri'})
            
            # Yangi parolni hash qilish
            hashed_password = generate_password_hash(data['new_password'])
            c.execute("UPDATE users SET password = %s WHERE user_id = %s", 
                     (hashed_password, user_id))
        
        # Profil ma'lumotlarini yangilash
        yoshlar_guruhi = data.get('yoshlar_guruhi', '')
        qomita = data.get('qomita', '')
        c.execute('''UPDATE users 
                    SET full_name = %s, age = %s, yoshlar_guruhi = %s, qomita = %s
                    WHERE user_id = %s''',
                  (data['full_name'], data['age'], yoshlar_guruhi, qomita, user_id))
        
        # Session ma'lumotlarini yangilash
        session['full_name'] = data['full_name']

        
        conn.commit()
        conn.close()
        
        log_action(user_id, 'update_profile', 'Profil ma\'lumotlari yangilandi')
        
        return jsonify({
            'success': True,
            'message': 'Profil muvaffaqiyatli yangilandi'
        })
        
    except Exception as e:
        print(f"Profil yangilashda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Parolni tiklash
@app.route('/api/user/reset_password', methods=['POST'])
def api_user_reset_password():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        data = request.json
        user_id = session['user_id']
        
        # Majburiy maydonlarni tekshirish
        if 'current_password' not in data or 'new_password' not in data:
            return jsonify({'success': False, 'error': 'Barcha maydonlarni to\'ldiring'})
        
        conn = get_db()
        c = conn.cursor()
        
        # Joriy parolni tekshirish
        c.execute("SELECT password FROM users WHERE user_id = %s", (user_id,))
        result = c.fetchone()
        
        if not result or not check_password_hash(result[0], data['current_password']):
            return jsonify({'success': False, 'error': 'Joriy parol noto\'g\'ri'})
        
        # Yangi parolni hash qilish
        hashed_password = generate_password_hash(data['new_password'])
        c.execute("UPDATE users SET password = %s WHERE user_id = %s", 
                 (hashed_password, user_id))
        
        conn.commit()
        conn.close()
        
        log_action(user_id, 'reset_password', 'Parol yangilandi')
        
        return jsonify({
            'success': True,
            'message': 'Parol muvaffaqiyatli yangilandi'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# Admin profil sozlamalari sahifasi
@app.route('/admin_profile_settings')
def admin_profile_settings():
    if 'user_id' not in session or session.get('role') not in ['admin', 'debugger']:
        return redirect(url_for('login'))
    
    return render_template('admin_profile_settings.html', regions=get_regions())

# Hisobni o'chirish endpointi (admin uchun)
@app.route('/api/admin/delete_account', methods=['POST'])
def api_delete_admin_account():
    if 'user_id' not in session or session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        user_id = session['user_id']
        
        # O'zini o'chira olmasin
        if user_id in ['debug001', 'admin001']:  # Asosiy adminlar
            return jsonify({'success': False, 'error': 'Asosiy admin akkauntini o\'chirish mumkin emas'})
        
        conn = get_db()
        c = conn.cursor()
        
        # Foydalanuvchini o'chirish
        c.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        
        # Hisobotlarni o'chirish (ixtiyoriy)
        c.execute("DELETE FROM reports WHERE user_id = %s", (user_id,))
        
        conn.commit()
        conn.close()
        
        # Sessionni tozalash
        session.clear()
        
        log_action(user_id, 'delete_account', 'Admin hisobini o\'chirdi')
        
        return jsonify({
            'success': True,
            'message': 'Hisob muvaffaqiyatli o\'chirildi'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Hisobotlar tarixi sahifasi
@app.route('/reports_history')
def reports_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('reports_history.html')

# Hisobotlar tarixi API
@app.route('/api/user/reports_history')
def api_reports_history():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        user_id = session['user_id']
        
        # Barcha hisobotlarni olish
        c.execute('''
            SELECT 
                r.id,
                r.month_year,
                r.event_count,
                r.material_count,
                r.message_count,
                r.safety_score,
                r.description,
                r.status,
                r.submitted_date,
                r.admin_comment,
                rt.faollik,
                rt.tashabbus,
                rt.intizom,
                rt.tasir,
                rt.total,
                rt.admin_comment as rating_comment
            FROM reports r
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE r.user_id = %s
            ORDER BY r.submitted_date DESC
        ''', (user_id,))
        
        reports = c.fetchall()
        columns = [desc[0] for desc in c.description]
        
        # Formatlash
        reports_list = []
        for report in reports:
            report_dict = {}
            for i, col in enumerate(columns):
                report_dict[col] = report[i]
            reports_list.append(report_dict)
        
        # Hisobotlar statistikasi
        c.execute('''
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'rated' THEN 1 END) as rated,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected,
                AVG(rt.total) as avg_score
            FROM reports r
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE r.user_id = %s
        ''', (user_id,))
        
        stats = c.fetchone()
        stats_dict = {
            'total': stats[0] or 0,
            'rated': stats[1] or 0,
            'pending': stats[2] or 0,
            'rejected': stats[3] or 0,
            'avg_score': round(float(stats[4] or 0), 1)
        }
        
        conn.close()
        
        return jsonify({
            'success': True,
            'reports': reports_list,
            'stats': stats_dict
        })
        
    except Exception as e:
        print(f"Hisobotlar tarixini olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Hisobotni yuklab olish
@app.route('/api/user/download_report/<int:report_id>')
def api_download_report(report_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Hisobot mavjudligini tekshirish
        c.execute('SELECT user_id, file_path FROM reports WHERE id = %s', (report_id,))
        report = c.fetchone()
        
        if not report:
            return jsonify({'success': False, 'error': 'Hisobot topilmadi'})
        
        # Faqat o'z hisobotlarini yuklab olish
        if report[0] != session['user_id']:
            return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
        
        if not report[1]:
            return jsonify({'success': False, 'error': 'Fayl mavjud emas'})
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], report[1])
        
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'success': False, 'error': 'Fayl topilmadi'})
            
    except Exception as e:
        print(f"Fayl yuklab olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Topshiriqlar sahifasi
@app.route('/user_tasks')
def user_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('user_tasks.html')

# Foydalanuvchi topshiriqlari API
@app.route('/api/user/tasks')
def api_user_tasks():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        user_id = session['user_id']
        
        # Filtrlash parametrlari
        status_filter = request.args.get('status', 'all')
        priority_filter = request.args.get('priority', 'all')
        
        # Asosiy WHERE sharti
        where_conditions = ['(ut.assigned_to = %s OR ut.assigned_to = "all")']
        params = [user_id]
        
        # Status filtri
        if status_filter != 'all':
            where_conditions.append('ut.status = %s')
            params.append(status_filter)
        
        # Priority filtri
        if priority_filter != 'all':
            where_conditions.append('ut.priority = %s')
            params.append(priority_filter)
        
        where_clause = ' AND '.join(where_conditions)
        
        # Foydalanuvchining topshiriqlari
        c.execute(f'''
            SELECT 
                ut.*,
                u.full_name as admin_name,
                CASE 
                    WHEN ut.assigned_to = 'all' THEN 'Barcha'
                    ELSE u2.full_name 
                END as assignee_name
            FROM user_tasks ut
            LEFT JOIN users u ON ut.assigned_by = u.user_id
            LEFT JOIN users u2 ON ut.assigned_to = u2.user_id
            WHERE {where_clause}
            ORDER BY 
                CASE ut.priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END,
                ut.deadline ASC
        ''', params)
        
        tasks = c.fetchall()
        columns = [desc[0] for desc in c.description]
        
        # Formatlash
        tasks_list = []
        for task in tasks:
            task_dict = {}
            for i, col in enumerate(columns):
                task_dict[col] = task[i]
            
            # Qo'shimcha maydonlar
            task_dict['is_overdue'] = is_task_overdue(task_dict['deadline'])
            task_dict['days_left'] = get_days_left(task_dict['deadline'])
            
            tasks_list.append(task_dict)
        
        # Statistikalar
        c.execute(f'''
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN deadline < CURRENT_DATE AND status != 'completed' THEN 1 END) as overdue
            FROM user_tasks ut
            WHERE {where_clause}
        ''', params)
        
        stats = c.fetchone()
        stats_dict = {
            'total': stats[0] or 0,
            'completed': stats[1] or 0,
            'in_progress': stats[2] or 0,
            'pending': stats[3] or 0,
            'overdue': stats[4] or 0
        }
        
        conn.close()
        
        return jsonify({
            'success': True,
            'tasks': tasks_list,
            'stats': stats_dict
        })
        
    except Exception as e:
        print(f"Topshiriqlarni olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

def is_task_overdue(deadline):
    """Topshiriq muddati o'tganmi%s"""
    if not deadline:
        return False
    from datetime import datetime
    try:
        deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
        return deadline_date < datetime.now()
    except:
        return False

def get_days_left(deadline):
    """Qancha kun qolgan%s"""
    if not deadline:
        return None
    from datetime import datetime
    try:
        deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
        today = datetime.now()
        days_left = (deadline_date - today).days
        return max(0, days_left)
    except:
        return None

@app.route('/api/user/update_rating', methods=['POST'])
def api_user_update_rating():
    """Progressiv reyting tizimi"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        data = request.get_json()
        user_id = session['user_id']
        points = data.get('points', 0)  # Yangi ball (+ yoki -)
        source_type = data.get('type', 'task')  # 'report' yoki 'task'
        
        conn = get_db()
        c = conn.cursor()
        
        # 1. Foydalanuvchi ma'lumotlarini olish
        c.execute('''
            SELECT rating, total_points, rated_count 
            FROM users 
            WHERE user_id = %s
        ''', (user_id,))
        
        user = c.fetchone()
        if not user:
            return jsonify({'success': False, 'error': 'Foydalanuvchi topilmadi'})
        
        current_rating = user[0] or 0
        total_points = user[1] or 0
        rated_count = user[2] or 0
        
        # 2. Progressiv reyting formulasini hisoblash
        def calculate_new_rating(old_rating, new_points, source_type):
            MAX_RATING = 20
            MIN_RATING = 0
            
            # Agar negativ ball bo'lsa (qayta hisoblash uchun)
            if new_points < 0:
                new_rating = old_rating + new_points
                if new_rating < MIN_RATING:
                    new_rating = MIN_RATING
                return new_rating
            
            # Progressiv omil: 10 balldan keyin qiyinlashadi
            progressive_factor = 1.0
            if old_rating >= 10 and old_rating < 15:
                progressive_factor = 0.7  # 30% qiyin
            elif old_rating >= 15:
                progressive_factor = 0.5  # 50% qiyin
            
            # Yangi ballni progressiv o'zgartirish
            adjusted_points = new_points * progressive_factor
            
            # Topshiriq yoki hisobot turiga qarab
            if source_type == 'report':
                # Hisobotlar uchun: ball * murakkablik omili
                adjusted_points = adjusted_points * 1.2
            elif source_type == 'task':
                # Topshiriqlar uchun: oddiy ball
                adjusted_points = adjusted_points * 1.0
            
            # Yangi reyting
            new_rating = old_rating + adjusted_points
            
            # 20 balldan oshmasligi
            if new_rating > MAX_RATING:
                new_rating = MAX_RATING
            
            return round(new_rating, 2)
        
        # 3. Reytingni hisoblash
        new_rating = calculate_new_rating(current_rating, points, source_type)
        
        # 4. O'rtacha ball tizimi uchun yangilash
        if source_type == 'report':
            rated_count += 1
            total_points += points
        
        # 5. Ma'lumotlarni yangilash
        c.execute('''
            UPDATE users 
            SET rating = %s, 
                total_points = %s,
                rated_count = %s,
                last_rating_update = CURRENT_TIMESTAMP
            WHERE user_id = %s
        ''', (new_rating, total_points, rated_count, user_id))
        
        conn.commit()
        
        # 6. Reyting tarixini saqlash
        c.execute('''
            INSERT INTO rating_history 
            (user_id, old_rating, new_rating, points, source_type, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ''', (user_id, current_rating, new_rating, points, source_type))
        
        conn.commit()
        conn.close()
        
        # 7. Kamayish omilini hisoblash (keyingi past ball uchun)
        def get_decrease_factor(rating):
            """Reytingga qarab kamayish omili"""
            if rating < 10:
                return 0.3  # 10 dan pastda - 30% kamayadi
            elif rating < 15:
                return 0.5  # 10-15 oralig'ida - 50% kamayadi
            else:
                return 0.7  # 15 dan yuqorida - 70% kamayadi
        
        return jsonify({
            'success': True,
            'new_rating': new_rating,
            'old_rating': current_rating,
            'change': round(new_rating - current_rating, 2),
            'decrease_factor': get_decrease_factor(new_rating),
            'message': f'Reyting yangilandi: {current_rating} → {new_rating}'
        })
        
    except Exception as e:
        print(f"Reyting yangilashda xatolik: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

def update_tables_with_rating():
    """Reyting tizimi uchun jadvallarni yangilash"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # 1. users jadvaliga yangi ustunlar
        c.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in c.fetchall()]
        
        # total_points - barcha ballar yig'indisi
        if 'total_points' not in user_columns:
            print("➕ users jadvaliga total_points ustuni qo'shilmoqda...")
            c.execute('ALTER TABLE users ADD COLUMN total_points INTEGER DEFAULT 0')
        
        # rated_count - baholangan hisobotlar/topshiriqlar soni
        if 'rated_count' not in user_columns:
            print("➕ users jadvaliga rated_count ustuni qo'shilmoqda...")
            c.execute('ALTER TABLE users ADD COLUMN rated_count INTEGER DEFAULT 0')
        
        # last_rating_update - oxirgi reyting yangilanishi
        if 'last_rating_update' not in user_columns:
            print("➕ users jadvaliga last_rating_update ustuni qo'shilmoqda...")
            c.execute('ALTER TABLE users ADD COLUMN last_rating_update TIMESTAMP')
        
        # 2. rating_history jadvalini yaratish
        c.execute('''
            CREATE TABLE IF NOT EXISTS rating_history (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                old_rating REAL DEFAULT 0,
                new_rating REAL DEFAULT 0,
                points REAL DEFAULT 0,
                source_type TEXT, -- 'report', 'task', 'correction'
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        print("✅ rating_history jadvali yaratildi/tekshirildi")
        
        # 3. Index qo'shish
        c.execute('CREATE INDEX IF NOT EXISTS idx_rating_history_user ON rating_history(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_rating_history_date ON rating_history(created_at)')
        
        conn.commit()
        conn.close()
        print("✅ Reyting tizimi jadvallari yangilandi")
        
    except Exception as e:
        print(f"❌ Reyting jadvallarini yangilashda xatolik: {e}")

class RatingSystem:
    """Progressiv reyting tizimi"""
    
    MAX_RATING = 20
    MIN_RATING = 0
    
    @staticmethod
    def calculate_progressive_factor(current_rating):
        """Progressiv omilni hisoblash"""
        if current_rating < 5:
            return 1.5  # Oson (50% oson)
        elif current_rating < 10:
            return 1.0  # Normal
        elif current_rating < 15:
            return 0.7  # Qiyin (30% qiyin)
        else:
            return 0.5  # Juda qiyin (50% qiyin)
    
    @staticmethod
    def calculate_decrease_factor(current_rating):
        """Kamayish omilini hisoblash"""
        if current_rating < 5:
            return 0.2  # 20% kamayadi
        elif current_rating < 10:
            return 0.3  # 30% kamayadi
        elif current_rating < 15:
            return 0.5  # 50% kamayadi
        else:
            return 0.7  # 70% kamayadi
    
    @staticmethod
    def calculate_new_rating(old_rating, earned_points, source_type='task'):
        """Yangi reytingni hisoblash"""
        # Agar past ball olingan bo'lsa (kamayish)
        if earned_points <= 0:
            decrease_factor = RatingSystem.calculate_decrease_factor(old_rating)
            new_rating = old_rating + (earned_points * decrease_factor)
        
        # Agar yaxshi ball olingan bo'lsa (oshish)
        else:
            progressive_factor = RatingSystem.calculate_progressive_factor(old_rating)
            source_multiplier = 1.2 if source_type == 'report' else 1.0
            adjusted_points = earned_points * progressive_factor * source_multiplier
            new_rating = old_rating + adjusted_points
        
        # Chegaralarni tekshirish
        new_rating = max(RatingSystem.MIN_RATING, min(RatingSystem.MAX_RATING, new_rating))
        
        return round(new_rating, 2)
    
    @staticmethod
    def calculate_average_rating(user_id):
        """O'rtacha reytingni hisoblash (statistika uchun)"""
        try:
            conn = get_db()
            c = conn.cursor()
            
            c.execute('''
                SELECT 
                    AVG(new_rating) as avg_rating,
                    COUNT(*) as total_ratings,
                    SUM(CASE WHEN points > 0 THEN 1 ELSE 0 END) as positive_ratings,
                    SUM(CASE WHEN points < 0 THEN 1 ELSE 0 END) as negative_ratings
                FROM rating_history 
                WHERE user_id = %s
            ''', (user_id,))
            
            result = c.fetchone()
            conn.close()
            
            return {
                'avg_rating': round(result[0] or 0, 2),
                'total_ratings': result[1] or 0,
                'positive_ratings': result[2] or 0,
                'negative_ratings': result[3] or 0
            }
            
        except Exception as e:
            print(f"O'rtacha reyting hisoblashda xatolik: {e}")
            return None

# Topshiriqni bajarilgan deb belgilash
@app.route('/api/user/complete_task/<task_id>', methods=['POST'])
def api_user_complete_task(task_id):
    """Topshiriqni tugatish va reyting berish"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        data = request.get_json()
        user_id = session['user_id']
        admin_rating = data.get('rating', 0)  # Admin bergan ball (1-10)
        
        conn = get_db()
        c = conn.cursor()
        
        # 1. Topshiriq ma'lumotlarini olish
        c.execute('''
            SELECT points, assigned_to, status 
            FROM user_tasks 
            WHERE task_id = %s
        ''', (task_id,))
        
        task = c.fetchone()
        if not task:
            return jsonify({'success': False, 'error': 'Topshiriq topilmadi'})
        
        task_points = task[0] or 5
        assigned_to = task[1]
        current_status = task[2]
        
        # 2. Foydalanuvchi ruxsatini tekshirish
        if assigned_to != user_id and assigned_to != 'all':
            return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
        
        # 3. Topshiriq holatini yangilash
        c.execute('''
            UPDATE user_tasks 
            SET status = 'completed',
                completed_by = %s,
                completed_at = CURRENT_TIMESTAMP,
                rating_given = %s
            WHERE task_id = %s
        ''', (user_id, admin_rating, task_id))
        
        # 4. Reytingni hisoblash (admin bahosi asosida)
        # Agar admin 10 ball bergan bo'lsa, to'liq ball olinadi
        # Agar past ball bergan bo'lsa, kam ball olinadi
        rating_points = (admin_rating / 10) * task_points
        
        # 5. Reytingni yangilash
        rating_response = api_user_update_rating()
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'task_completed': True,
            'task_points': task_points,
            'rating_received': rating_points,
            'admin_rating': admin_rating,
            'message': f'Topshiriq tugatildi va {rating_points} ball qo\'shildi'
        })
        
    except Exception as e:
        print(f"Topshiriqni tugatishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Reyting statistikasi sahifasi
@app.route('/rating_statistics')
def rating_statistics():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('rating_statistics.html')

# Foydalanuvchi reyting statistikasi
# Reyting statistikasi API ni to'g'rilaymiz
@app.route('/api/user/rating_statistics')
def api_user_rating_statistics():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        # Avval jadvallarni yangilash
        update_tables()
        
        conn = get_db()
        c = conn.cursor()
        
        user_id = session['user_id']
        
        # 1. Reyting tarixi
        c.execute('''
            SELECT 
                to_char(r.submitted_date, 'YYYY-MM') as month,
                rt.total as rating,
                COUNT(r.id) as report_count
            FROM reports r
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE r.user_id = %s AND r.status = 'rated' AND rt.total IS NOT NULL
            GROUP BY to_char(r.submitted_date, 'YYYY-MM')
            ORDER BY month DESC
            LIMIT 12
        ''', (user_id,))
        
        rating_history = []
        for row in c.fetchall():
            rating_history.append({
                'month': row[0],
                'rating': row[1],
                'report_count': row[2]
            })
        
        # 2. Topshiriq statistikasi - completed_by ustuni borligini tekshirish
        try:
            # completed_by ustuni borligini tekshirish
            c.execute("PRAGMA table_info(user_tasks)")
            columns = [col[1] for col in c.fetchall()]
            
            if 'completed_by' in columns:
                # completed_by ustuni bor versiya
                c.execute('''
                    SELECT 
                        to_char(completed_at, 'YYYY-MM') as month,
                        SUM(points) as points_earned,
                        COUNT(*) as tasks_completed
                    FROM user_tasks
                    WHERE completed_by = %s AND status = 'completed'
                    GROUP BY to_char(completed_at, 'YYYY-MM')
                    ORDER BY month DESC
                    LIMIT 12
                ''', (user_id,))
            else:
                # completed_by ustuni yo'q versiya
                c.execute('''
                    SELECT 
                        to_char(created_at, 'YYYY-MM') as month,
                        SUM(points) as points_earned,
                        COUNT(*) as tasks_completed
                    FROM user_tasks
                    WHERE status = 'completed'
                        AND (assigned_to = %s OR assigned_to = 'all')
                    GROUP BY to_char(created_at, 'YYYY-MM')
                    ORDER BY month DESC
                    LIMIT 12
                ''', (user_id,))
            
            task_stats_rows = c.fetchall()
            task_stats = []
            for row in task_stats_rows:
                task_stats.append({
                    'month': row[0] if row[0] else 'Noma\'lum',
                    'points_earned': row[1] or 0,
                    'tasks_completed': row[2] or 0
                })
                
        except Exception as e:
            print(f"Topshiriq statistikasini olishda xatolik: {e}")
            task_stats = []
        
        # 3. Hudud statistikasi
        c.execute("SELECT district, rating FROM users WHERE user_id = %s", (user_id,))
        user_info = c.fetchone()
        
        district_stats = {
            'district': user_info[0] if user_info else '',
            'total_users': 0,
            'district_rank': 1,
            'district_avg': 0,
            'user_rating': user_info[1] if user_info else 0
        }
        
        if user_info and user_info[0]:
            # Hudud statistikasini olish
            c.execute('''
                SELECT 
                    COUNT(*) as total_users,
                    AVG(rating) as district_avg
                FROM users
                WHERE role = 'user' AND district = %s AND rating IS NOT NULL
            ''', (user_info[0],))
            
            stats = c.fetchone()
            if stats:
                district_stats['total_users'] = stats[0] or 0
                district_stats['district_avg'] = round(float(stats[1] or 0), 1)
            
            # Hududda o'rni
            c.execute('''
                SELECT COUNT(*) as better_users
                FROM users
                WHERE role = 'user' 
                    AND district = %s 
                    AND rating > %s
                    AND rating IS NOT NULL
            ''', (user_info[0], user_info[1] or 0))
            
            rank_result = c.fetchone()
            if rank_result:
                district_stats['district_rank'] = (rank_result[0] or 0) + 1
        
        # 4. Foydalanuvchi statistikasi
        c.execute('''
            SELECT 
                rating,
                (SELECT COUNT(*) FROM reports WHERE user_id = %s) as report_count,
                (SELECT COUNT(*) FROM user_tasks 
                 WHERE status = 'completed' 
                 AND (assigned_to = %s OR assigned_to = 'all')) as task_count
            FROM users 
            WHERE user_id = %s
        ''', (user_id, user_id, user_id))
        
        user_stats_result = c.fetchone()
        
        # O'rtacha hisobot bahosi
        c.execute('''
            SELECT AVG(rt.total)
            FROM reports r
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE r.user_id = %s AND r.status = 'rated' AND rt.total IS NOT NULL
        ''', (user_id,))
        
        avg_score_result = c.fetchone()
        avg_score = round(float(avg_score_result[0] or 0), 1) if avg_score_result and avg_score_result[0] is not None else 0
        
        user_rating_stats = {
            'current_rating': user_stats_result[0] if user_stats_result else 0,
            'report_count': user_stats_result[1] or 0 if user_stats_result else 0,
            'task_count': user_stats_result[2] or 0 if user_stats_result else 0,
            'avg_report_score': avg_score
        }
        
        conn.close()
        
        return jsonify({
            'success': True,
            'rating_history': rating_history,
            'task_stats': task_stats,
            'district_stats': district_stats,
            'user_stats': user_rating_stats
        })
        
    except Exception as e:
        print(f"Reyting statistikasini olishda xatolik: {e}")
        import traceback
        traceback.print_exc()
        
        # Agar xatolik bo'lsa, kamida bo'sh ma'lumot qaytaramiz
        return jsonify({
            'success': True,
            'rating_history': [],
            'task_stats': [],
            'district_stats': {
                'district': '',
                'total_users': 0,
                'district_rank': 1,
                'district_avg': 0,
                'user_rating': 0
            },
            'user_stats': {
                'current_rating': 0,
                'report_count': 0,
                'task_count': 0,
                'avg_report_score': 0
            }
        })

# Yordam sahifasi
@app.route('/help')
def help_page():
    return render_template('help.html')

# FAQ API
@app.route('/api/help/faq')
def api_faq():
    faq_data = [
        {
            'question': 'Hisobot qanday topshiriladi%s',
            'answer': 'Dashboardda "Hisobot topshirish" tugmasini bosing yoki yon paneldan "Hisobot topshirish" bo\'limiga o\'ting. Oyni, tadbirlar soni, materiallar soni va boshqa ma\'lumotlarni to\'ldiring, fayl yuklashingiz mumkin va "Yuborish" tugmasini bosing.'
        },
        {
            'question': 'Hisobotim necha kunda baholanadi%s',
            'answer': 'Hisobotlaringiz odatda 3-7 ish kunida adminlar tomonidan baholanadi. Baholangan hisobotlarni "Hisobotlar tarixi" bo\'limida ko\'rishingiz mumkin.'
        },
        {
            'question': 'Reyting qanday hisoblanadi%s',
            'answer': 'Reyting 20 ball tizimi asosida hisoblanadi. Hisobotlar 4 jihatdan baholanadi: Faollik, Tashabbuskorlik, Intizom va Ta\'sir. Har bir kategoriya 0-5 ballgacha baholanadi.'
        },
        {
            'question': 'Topshiriq qanday bajariladi%s',
            'answer': '"Topshiriqlar" bo\'limidan topshiriqlaringizni ko\'rishingiz mumkin. Topshiriqni bajarganingizdan so\'ng, "Bajarildi" tugmasini bosib, topshiriqni bajarilgan deb belgilashingiz mumkin.'
        },
        {
            'question': 'Parolni qanday o\'zgartirish mumkin%s',
            'answer': '"Profil sozlamalari" bo\'limida "Xavfsizlik" qismida parolni o\'zgartirishingiz mumkin. Joriy parolni va yangi parolni kiritishingiz kerak.'
        },
        {
            'question': 'Hisobotni yuklab olish mumkinmi%s',
            'answer': 'Ha, "Hisobotlar tarixi" bo\'limida har bir hisobot uchun "Yuklash" tugmasi mavjud. Bu siz yuklagan faylni yuklab olish uchun ishlatiladi.'
        },
        {
            'question': 'Qanday qilib reytingimni oshirishim mumkin%s',
            'answer': '1. Vaqtida hisobot topshirish\n2. Sifatli va to\'liq ma\'lumotlar berish\n3. Topshiriqlarni o\'z vaqtida bajarish\n4. Aktiv ishtirok etish'
        }
    ]
    
    return jsonify({'success': True, 'faq': faq_data})

# Contact form yuborish
@app.route('/api/help/contact', methods=['POST'])
def api_contact():
    try:
        data = request.json
        
        # Majburiy maydonlarni tekshirish
        required_fields = ['name', 'email', 'subject', 'message']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'{field} maydoni to\'ldirilishi shart'})
        
        # Bu yerda email yuborish logikasi bo'lishi kerak
        # Hozircha log yozamiz
        log_action(data.get('email', 'anonymous'), 'contact_form', 
                  f"Yordam so'rovi: {data['subject']}")
        
        return jsonify({
            'success': True,
            'message': 'Xabaringiz yuborildi. Tez orada javob beramiz.'
        })
        
    except Exception as e:
        print(f"Contact form xatosi: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Hisobotni olish endpointi
@app.route('/api/user/get_report/<int:report_id>')
def api_user_get_report(report_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        user_id = session['user_id']
        
        c.execute('''
            SELECT 
                r.*,
                u.full_name,
                u.district,
                u.age,
                rt.faollik,
                rt.tashabbus,
                rt.intizom,
                rt.tasir,
                rt.total,
                rt.admin_comment as rating_comment
            FROM reports r
            LEFT JOIN users u ON r.user_id = u.user_id
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE r.id = %s AND r.user_id = %s
        ''', (report_id, user_id))
        
        report = c.fetchone()
        
        if not report:
            return jsonify({'success': False, 'error': 'Hisobot topilmadi yoki ruxsat yo\'q'})
        
        # Kolonka nomlari
        columns = [desc[0] for desc in c.description]
        
        # Formatlash
        report_dict = {}
        for i, col in enumerate(columns):
            report_dict[col] = report[i]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'report': report_dict
        })
        
    except Exception as e:
        print(f"Hisobotni olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Topshiriqni olish endpointi
@app.route('/api/user/get_task/<task_id>')
def api_user_get_task(task_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        user_id = session['user_id']
        
        c.execute('''
            SELECT 
                ut.*,
                u.full_name as admin_name
            FROM user_tasks ut
            LEFT JOIN users u ON ut.assigned_by = u.user_id
            WHERE ut.task_id = %s AND (ut.assigned_to = %s OR ut.assigned_to = 'all')
        ''', (task_id, user_id))
        
        task = c.fetchone()
        
        if not task:
            return jsonify({'success': False, 'error': 'Topshiriq topilmadi yoki ruxsat yo\'q'})
        
        # Kolonka nomlari
        columns = [desc[0] for desc in c.description]
        
        # Formatlash
        task_dict = {}
        for i, col in enumerate(columns):
            task_dict[col] = task[i]
        
        # Qo'shimcha maydonlar
        task_dict['is_overdue'] = is_task_overdue(task_dict.get('deadline'))
        task_dict['days_left'] = get_days_left(task_dict.get('deadline'))
        
        conn.close()
        
        return jsonify({
            'success': True,
            'task': task_dict
        })
        
    except Exception as e:
        print(f"Topshiriqni olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# # Jadvalni yangilash funksiyasi
# def update_tables():
#     """Mavjud jadval strukturasini yangilash"""
#     try:
#         conn = get_db()
#         c = conn.cursor()
        
#         # user_tasks jadvalining ustunlarini tekshirish
#         c.execute("PRAGMA table_info(user_tasks)")
#         columns = [col[1] for col in c.fetchall()]
        
#         # Agar completed_at ustuni yo'q bo'lsa, qo'shamiz
#         if 'completed_at' not in columns:
#             print("✅ user_tasks jadvaliga completed_at ustuni qo'shilmoqda...")
#             c.execute("ALTER TABLE user_tasks ADD COLUMN completed_at TIMESTAMP")
        
#         # Agar rating_given ustuni yo'q bo'lsa, qo'shamiz
#         if 'rating_given' not in columns:
#             print("✅ user_tasks jadvaliga rating_given ustuni qo'shilmoqda...")
#             c.execute("ALTER TABLE user_tasks ADD COLUMN rating_given INTEGER")
        
#         # Agar feedback ustuni yo'q bo'lsa, qo'shamiz
#         if 'feedback' not in columns:
#             print("✅ user_tasks jadvaliga feedback ustuni qo'shilmoqda...")
#             c.execute("ALTER TABLE user_tasks ADD COLUMN feedback TEXT")
        
#         # Agar progress ustuni yo'q bo'lsa, qo'shamiz
#         if 'progress' not in columns:
#             print("✅ user_tasks jadvaliga progress ustuni qo'shilmoqda...")
#             c.execute("ALTER TABLE user_tasks ADD COLUMN progress INTEGER DEFAULT 0")
        
#         conn.commit()
#         conn.close()
#         print("✅ Jadval strukturalari yangilandi!")
        
#     except Exception as e:
#         print(f"❌ Jadval yangilashda xatolik: {e}")


# Test qilish uchun endpoint
@app.route('/api/test/tables')
def api_test_tables():
    """Jadval strukturasini tekshirish"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        results = {}
        
        # 1. user_tasks jadvali
        c.execute("PRAGMA table_info(user_tasks)")
        user_tasks_columns = c.fetchall()
        results['user_tasks'] = [col[1] for col in user_tasks_columns]
        
        # 2. users jadvali
        c.execute("PRAGMA table_info(users)")
        users_columns = c.fetchall()
        results['users'] = [col[1] for col in users_columns]
        
        # 3. reports jadvali
        c.execute("PRAGMA table_info(reports)")
        reports_columns = c.fetchall()
        results['reports'] = [col[1] for col in reports_columns]
        
        # 4. Jadvaldagi ma'lumotlar soni
        c.execute("SELECT COUNT(*) FROM user_tasks")
        results['user_tasks_count'] = c.fetchone()[0]
        
        c.execute("SELECT * FROM user_tasks LIMIT 1")
        sample_task = c.fetchone()
        results['sample_task_columns'] = len(sample_task) if sample_task else 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Jadvalni tuzatish endpointi
@app.route('/api/admin/fix_tables', methods=['POST'])
def api_fix_tables():
    if session.get('role') != 'debugger':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        update_tables()
        
        # Test uchun bir nechta topshiriq qo'shamiz
        conn = get_db()
        c = conn.cursor()
        
        # Test topshiriqlari
        test_tasks = [
            {
                'task_id': f'TASK-{datetime.now().strftime("%Y%m%d")}-{random.randint(1000, 9999)}',
                'title': 'Hudud yoshlari sonini aniqlash',
                'description': 'Hududingizdagi 18-35 yosh oralig\'idagi yoshlar sonini hisoblang va hisobot tayyorlang.',
                'assigned_to': session['user_id'],
                'assigned_by': 'debug001',
                'deadline': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
                'points': 10,
                'task_type': 'monthly',
                'priority': 'high'
            },
            {
                'task_id': f'TASK-{datetime.now().strftime("%Y%m%d")}-{random.randint(1000, 9999)}',
                'title': 'Ijtimoiy media hisobi',
                'description': 'Parlament ijtimoiy media hisobi uchun haftalik kontent tayyorlash.',
                'assigned_to': 'all',
                'assigned_by': 'debug001',
                'deadline': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
                'points': 5,
                'task_type': 'regular',
                'priority': 'medium'
            }
        ]
        
        for task in test_tasks:
            try:
                c.execute('''
                    INSERT OR REPLACE INTO user_tasks 
                    (task_id, title, description, assigned_to, assigned_by, deadline, 
                     points, task_type, priority, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
                ''', (
                    task['task_id'], task['title'], task['description'],
                    task['assigned_to'], task['assigned_by'], task['deadline'],
                    task['points'], task['task_type'], task['priority'],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
            except Exception as e:
                print(f"Topshiriq qo'shishda xatolik: {e}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Jadvallar tuzatildi va test topshiriqlari qo\'shildi'
        })
        
    except Exception as e:
        print(f"Jadvallarni tuzatishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Jadval strukturasini to'liq yangilash
def update_user_tasks_table():
    """user_tasks jadvalini to'liq yangilash"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Avval jadval mavjud ustunlarini tekshirish
        c.execute("PRAGMA table_info(user_tasks)")
        existing_columns = [col[1] for col in c.fetchall()]
        
        print(f"🔍 user_tasks jadvalining mavjud ustunlari: {existing_columns}")
        
        # Kerakli ustunlar ro'yxati
        required_columns = [
            ('id', 'SERIAL PRIMARY KEY'),
            ('task_id', 'TEXT UNIQUE'),
            ('title', 'TEXT NOT NULL'),
            ('description', 'TEXT'),
            ('assigned_to', 'TEXT'),
            ('assigned_by', 'TEXT'),
            ('deadline', 'DATE'),
            ('points', 'INTEGER DEFAULT 5'),
            ('task_type', 'TEXT DEFAULT "regular"'),
            ('priority', 'TEXT DEFAULT "medium"'),
            ('status', 'TEXT DEFAULT "pending"'),
            ('progress', 'INTEGER DEFAULT 0'),
            ('completed_by', 'TEXT'),
            ('completed_at', 'TIMESTAMP'),
            ('feedback', 'TEXT'),
            ('rating_given', 'INTEGER'),
            ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ]
        
        # Agar jadval bo'sh bo'lsa yoki asosiy ustunlar yo'q bo'lsa, to'liq qayta yaratish
        if len(existing_columns) < 5:
            print("🔄 user_tasks jadvali to'liq qayta yaratilmoqda...")
            
            # Avval eski jadvalni o'chirish
            try:
                c.execute('DROP TABLE IF EXISTS user_tasks')
                print("✅ Eski user_tasks jadvali o'chirildi")
            except:
                pass
            
            # Yangi jadval yaratish
            create_sql = '''
                CREATE TABLE user_tasks (
                    id SERIAL PRIMARY KEY,
                    task_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT,
                    assigned_to TEXT,
                    assigned_by TEXT,
                    deadline DATE,
                    points INTEGER DEFAULT 5,
                    task_type TEXT DEFAULT 'regular',
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    completed_by TEXT,
                    completed_at TIMESTAMP,
                    feedback TEXT,
                    rating_given INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assigned_by) REFERENCES users(user_id)
                )
            '''
            c.execute(create_sql)
            print("✅ Yangi user_tasks jadvali yaratildi")
        else:
            # Faqat yo'q ustunlarni qo'shish
            for column_name, column_type in required_columns:
                if column_name not in existing_columns:
                    print(f"➕ {column_name} ustuni qo'shilmoqda...")
                    
                    if column_name == 'id':
                        continue  # id ustuni allaqachon mavjud
                    
                    # ALTER TABLE qo'shish
                    alter_sql = f'ALTER TABLE user_tasks ADD COLUMN {column_name} {column_type.split()[0]}'
                    c.execute(alter_sql)
                    
                    # Agar default qiymat bo'lsa
                    if 'DEFAULT' in column_type:
                        try:
                            # Avval barcha qatorlarga default qiymat berish
                            update_sql = f'UPDATE user_tasks SET {column_name} = %s WHERE {column_name} IS NULL'
                            default_value = column_type.split()[-1].strip('"\'')
                            c.execute(update_sql, (default_value,))
                        except:
                            pass
        
        conn.commit()
        
        # Test uchun bir nechta ustunlarni tekshirish
        c.execute("PRAGMA table_info(user_tasks)")
        final_columns = [col[1] for col in c.fetchall()]
        print(f"✅ Yakuniy ustunlar: {final_columns}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ user_tasks jadvalini yangilashda xatolik: {e}")
        import traceback
        traceback.print_exc()
        return False

# Barcha jadvallarni yangilash funksiyasini yangilaymiz
def update_tables():
    """Barcha muhim jadvallarni yangilash"""
    print("🔧 Jadvallar yangilanmoqda...")
    
    # 1. user_tasks jadvali
    user_tasks_success = update_user_tasks_table()
    
    # 2. users jadvali
    try:
        conn = get_db()
        c = conn.cursor()
        
        # users jadvali ustunlarini tekshirish
        c.execute("PRAGMA table_info(users)")
        users_columns = [col[1] for col in c.fetchall()]
        
        # phone ustuni
        if 'phone' not in users_columns:
            print("➕ users jadvaliga phone ustuni qo'shilmoqda...")
            c.execute('ALTER TABLE users ADD COLUMN phone TEXT')
        
        # rating ustuni (agar yo'q bo'lsa)
        if 'rating' not in users_columns:
            print("➕ users jadvaliga rating ustuni qo'shilmoqda...")
            c.execute('ALTER TABLE users ADD COLUMN rating INTEGER DEFAULT 0')
        
        # last_login ustuni
        if 'last_login' not in users_columns:
            print("➕ users jadvaliga last_login ustuni qo'shilmoqda...")
            c.execute('ALTER TABLE users ADD COLUMN last_login TIMESTAMP')
        
        conn.commit()
        conn.close()
        print("✅ users jadvali yangilandi")
    except Exception as e:
        print(f"❌ users jadvalini yangilashda xatolik: {e}")
    
    print("✅ Barcha jadvallar yangilandi!")
    return user_tasks_success



###########. 404 sahifasi  ############

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404



#########################################################
################ ADMIN PANELI ###########################
#########################################################
@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    role = session.get('role')
    
    # Faqat admin va debuggerlar kirishi mumkin
    if role not in ['admin', 'debugger']:
        return redirect('/dashboard')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # -------------------------------
    # FOYDALANUVCHILAR SONI
    # -------------------------------
    cursor.execute("SELECT COUNT(*) FROM users WHERE role NOT IN ('admin', 'debugger')")
    user_count = cursor.fetchone()[0] or 0
    
    # -------------------------------
    # AKTIV FOYDALANUVCHILAR
    # -------------------------------
    cursor.execute("SELECT COUNT(*) FROM users WHERE julianday('now') - julianday(last_login) < 7")
    active_users = cursor.fetchone()[0] or 0
    
    # -------------------------------
    # HISOBOTLAR SONI
    # -------------------------------
    cursor.execute("SELECT COUNT(*) FROM reports")
    report_count = cursor.fetchone()[0] or 0
    
    # -------------------------------
    # KUTILAYOTGAN HISOBOTLAR
    # -------------------------------
    cursor.execute("SELECT COUNT(*) FROM reports WHERE status = 'pending'")
    pending_reports = cursor.fetchone()[0] or 0
    
    # -------------------------------
    # TOPSHIRIQLAR SONI - FILTERLANGAN
    # -------------------------------
    try:
        cursor.execute("SELECT COUNT(*) FROM user_tasks")
        task_count = cursor.fetchone()[0] or 0
    except:
        task_count = 0
    
    # -------------------------------
    # SO'NGGI LOGLAR
    # -------------------------------
    try:
        cursor.execute('''
            SELECT datetime(timestamp, 'localtime'), user_id, action, details
            FROM system_logs
            ORDER BY timestamp DESC
            LIMIT 10
        ''')
        recent_logs = cursor.fetchall()
    except:
        recent_logs = []
    
    # -------------------------------
    # BARCHA FOYDALANUVCHILAR
    # -------------------------------
    cursor.execute('''
        SELECT * FROM users 
        WHERE role NOT IN ('admin', 'debugger')
        ORDER BY id DESC
    ''')
    all_users = cursor.fetchall()
    
    # -------------------------------
    # HISOBOTLAR RO'YXATI - FILTERLANGAN
    # -------------------------------
    try:
        cursor.execute('''
            SELECT r.*, u.full_name, u.district
            FROM reports r
            JOIN users u ON r.user_id = u.user_id
            ORDER BY r.submitted_date DESC
            LIMIT 20
        ''')
        reports = cursor.fetchall()
    except:
        reports = []
    
    conn.close()
    
    # Hududlar ro'yxati
    regions = get_regions()
    
    # Parol generatsiya funksiyasi
    def generate_password(length=8):
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    return render_template('admin.html',
                         user_count=user_count,
                         active_users=active_users,
                         report_count=report_count,
                         pending_reports=pending_reports,
                         task_count=task_count,
                         recent_logs=recent_logs,
                         all_users=all_users,
                         reports=reports,  # ENDI reports ANIQLANGAN
                         regions=regions,
                         generate_password=generate_password)
                         
# ============ ADMIN TEKSHIRISH ============
def check_admin_access():
    """Admin kirish huquqini tekshirish"""
    return session.get('role') in ['admin', 'debugger']

@app.route('/api/admin/get_users', methods=['GET'])
def api_get_users():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        c.execute('''
            SELECT * FROM users 
            WHERE role NOT IN ('admin', 'debugger')
            ORDER BY id DESC
        ''')
        
        users = c.fetchall()
        conn.close()
        
        return jsonify({'success': True, 'users': users})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# @app.route('/api/admin/rating_dashboard', methods=['GET'])
# def api_rating_dashboard():
#     """Reyting dashboard (viloyat bo'yicha filterlangan)"""
#     try:
#         admin_district = get_admin_district()
#         user_role = session.get('role')
        
#         conn = get_db()
#         cursor = conn.cursor()
        
#         # FILTERNİ QO'LLASH
#         district_filter = ""
#         params = []
        
#         if user_role != 'debugger' and admin_district:
#             district_filter = "AND u.district = %s"
#             params.append(admin_district)
        
#         # 1. Umumiy statistika
#         cursor.execute(f'''
#             SELECT 
#                 COUNT(DISTINCT u.id) as total_users,
#                 AVG(ur.rating) as avg_rating,
#                 MAX(ur.rating) as max_rating,
#                 SUM(CASE WHEN julianday('now') - julianday(u.last_login) < 7 THEN 1 ELSE 0 END) as active_users
#             FROM users u
#             LEFT JOIN user_ratings ur ON u.id = ur.user_id
#             WHERE u.role = 'user' {district_filter}
#         ''', params)
        
#         stats_row = cursor.fetchone()
        
#         # 2. Hududlar bo'yicha (agar debugger bo'lsa, hamma hududlar, aks holda faqat o'zi)
#         if user_role == 'debugger':
#             cursor.execute('''
#                 SELECT 
#                     u.district,
#                     COUNT(DISTINCT u.id) as user_count,
#                     AVG(ur.rating) as avg_rating
#                 FROM users u
#                 LEFT JOIN user_ratings ur ON u.id = ur.user_id
#                 WHERE u.role = 'user'
#                 GROUP BY u.district
#                 ORDER BY avg_rating DESC
#             ''')
#         else:
#             # Admin faqat o'z hududini ko'radi
#             cursor.execute('''
#                 SELECT 
#                     u.district,
#                     COUNT(DISTINCT u.id) as user_count,
#                     AVG(ur.rating) as avg_rating
#                 FROM users u
#                 LEFT JOIN user_ratings ur ON u.id = ur.user_id
#                 WHERE u.role = 'user' AND u.district = %s
#                 GROUP BY u.district
#             ''', (admin_district,))
        
#         districts = cursor.fetchall()
        
#         # 3. Top foydalanuvchilar (faqat admin viloyatidan)
#         cursor.execute(f'''
#             SELECT 
#                 u.id,
#                 u.full_name,
#                 u.district,
#                 COALESCE(ur.rating, 0) as rating,
#                 (SELECT COUNT(*) FROM reports WHERE user_id = u.id) as report_count,
#                 u.created_at
#             FROM users u
#             LEFT JOIN user_ratings ur ON u.id = ur.user_id
#             WHERE u.role = 'user' {district_filter}
#             ORDER BY rating DESC
#             LIMIT 10
#         ''', params)
        
#         top_users = cursor.fetchall()
        
#         conn.close()
        
#         # Region nomlarini olish
#         regions = get_regions()
        
#         # Formatlash
#         formatted_districts = []
#         for d in districts:
#             district_code = d[0]
#             formatted_districts.append({
#                 'district_code': district_code,
#                 'district_name': regions.get(district_code, f"Hudud {district_code}"),
#                 'user_count': d[1],
#                 'avg_rating': round(d[2] or 0, 1)
#             })
        
#         formatted_top_users = []
#         for u in top_users:
#             formatted_top_users.append({
#                 'user_id': u[0],
#                 'full_name': u[1],
#                 'district': regions.get(u[2], u[2]),
#                 'district_code': u[2],
#                 'rating': u[3] or 0,
#                 'rating_percentage': round((u[3] or 0) * 5, 1),
#                 'report_count': u[4] or 0,
#                 'joined_date': u[5][:10] if u[5] else ''
#             })
        
#         return jsonify({
#             'success': True,
#             'stats': {
#                 'total_users': stats_row[0] or 0,
#                 'avg_rating': round(stats_row[1] or 0, 1),
#                 'max_rating': stats_row[2] or 0,
#                 'active_users': stats_row[3] or 0
#             },
#             'districts': formatted_districts,
#             'top_users': formatted_top_users,
#             'admin_district': admin_district,
#             'is_super_admin': user_role == 'debugger'
#         })
        
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500
    
@app.route('/api/admin/ratings_table', methods=['GET'])
def api_ratings_table():
    """Reytinglar jadvali (filterlangan)"""
    try:
        user_role = session.get('role')
        
        # Filter parametrlari
        rating_filter = request.args.get('rating', 'all')
        sort_by = request.args.get('sort', 'rating_desc')
        search_term = request.args.get('search', '')
        
        conn = get_db()
        cursor = conn.cursor()
        
        where_clauses = ["u.role = 'user'"]
        params = []
        
        # Reyting filter
        if rating_filter == 'high':
            where_clauses.append("COALESCE(ur.current_rating, 0) >= 15")
        elif rating_filter == 'medium':
            where_clauses.append("COALESCE(ur.current_rating, 0) BETWEEN 10 AND 14")
        elif rating_filter == 'low':
            where_clauses.append("COALESCE(ur.current_rating, 0) < 10")
        
        # Qidirish
        if search_term:
            where_clauses.append("(u.full_name LIKE %s OR u.user_id LIKE %s)")
            params.append(f'%{search_term}%')
            params.append(f'%{search_term}%')
        
        where_sql = " AND ".join(where_clauses)
        
        # Tartiblash
        order_map = {
            'rating_desc': 'rating DESC',
            'rating_asc': 'rating ASC',
            'name_asc': 'u.full_name ASC',
            'name_desc': 'u.full_name DESC',
            'reports_desc': 'report_count DESC'
        }
        order_by = order_map.get(sort_by, 'rating DESC')
        
        # Ma'lumotlarni olish
        cursor.execute(f'''
            SELECT 
                u.user_id,
                u.full_name,
                u.district,
                COALESCE(u.rating, 0) as rating,
                (SELECT COUNT(*) FROM reports WHERE user_id = u.user_id) as total_reports,
                (SELECT COUNT(*) FROM reports WHERE user_id = u.user_id AND status = 'rated') as rated_reports,
                u.last_login
            FROM users u
            WHERE {where_sql}
            ORDER BY {order_by}
        ''', params)
        
        users = cursor.fetchall()
        conn.close()
        
        # Formatlash
        regions = get_regions()
        formatted_users = []
        
        for u in users:
            rating = u[3] or 0
            rating_percentage = round(rating * 5, 1)
            
            # Status aniqlash
            if rating >= 16:
                status = 'excellent'
            elif rating >= 13:
                status = 'good'
            elif rating >= 10:
                status = 'average'
            elif rating >= 7:
                status = 'needs_improvement'
            else:
                status = 'poor'
            
            # Faollik darajasi
            last_login = u[6]
            activity = 'inactive'
            if last_login:
                try:
                    # YYYY-MM-DD formatda bo'lsa
                    if isinstance(last_login, str) and len(last_login) >= 10:
                        days_since = (datetime.now() - datetime.strptime(last_login[:10], '%Y-%m-%d')).days
                        if days_since < 3:
                            activity = 'very_active'
                        elif days_since < 7:
                            activity = 'active'
                        elif days_since < 14:
                            activity = 'less_active'
                except:
                    pass
            
            formatted_users.append({
                'user_id': u[0],
                'full_name': u[1],
                'district': regions.get(u[2], f"Hudud {u[2]}"),
                'district_code': u[2],
                'rating': rating,
                'rating_percentage': rating_percentage,
                'total_reports': u[4] or 0,
                'rated_reports': u[5] or 0,
                'status': status,
                'activity_level': activity
            })
        
        return jsonify({
            'success': True,
            'users': formatted_users,
            'total_count': len(formatted_users),
        })
        
    except Exception as e:
        print(f"❌ RATINGS TABLE XATOSI: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/export_users', methods=['GET'])
def export_users_excel():
    """Foydalanuvchilarni Excel export qilish"""
    try:
        user_role = session.get('role')
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, full_name, district, age, phone, role, 
                   COALESCE((SELECT rating FROM user_ratings WHERE user_id = users.id), 0) as rating,
                   joined_date
            FROM users
            WHERE role NOT IN ('admin', 'debugger')
            ORDER BY full_name
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        # Excel fayl yaratish
        import pandas as pd
        from io import BytesIO
        
        regions = get_regions()
        data = []
        
        for user in users:
            data.append({
                'ID': user[0],
                'To\'liq ism': user[1],
                'Hudud': regions.get(user[2], user[2]),
                'Yosh': user[3],
                'Telefon': user[4] or '-',
                'Rol': user[5],
                'Reyting': user[6],
                'Ro\'yxatdan o\'tgan': user[7][:10] if user[7] else '-'
            })
        
        df = pd.DataFrame(data)
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Foydalanuvchilar', index=False)
        
        output.seek(0)
        
        filename = f"foydalanuvchilar_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/import_excel', methods=['POST'])
def import_excel():
    """Excel import qilish - faqat adminning viloyatiga tegishli"""
    try:
        user_role = session.get('role')
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Fayl yuklanmadi'})
        
        file = request.files['file']
        
        # Excel faylni o'qish
        import pandas as pd
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        conn = get_db()
        cursor = conn.cursor()
        
        added = 0
        updated = 0
        skipped = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                user_id = str(row.get('ID', '')).zfill(4)
                full_name = row.get('FullName', row.get('To\'liq ism', ''))
                district = str(row.get('District', row.get('Hudud', ''))).strip()
                age = int(row.get('Age', row.get('Yosh', 18)))
                phone = str(row.get('Phone', row.get('Telefon', '')))
                role = str(row.get('Role', row.get('Rol', 'user')))
                initial_rating = int(row.get('InitialRating', row.get('Boshlang\'ich reyting', 10)))
                
                # Mavjudligini tekshirish
                cursor.execute('SELECT id FROM users WHERE id = %s', (user_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # Yangilash
                    cursor.execute('''
                        UPDATE users 
                        SET full_name = %s, district = %s, age = %s, phone = %s, role = %s
                        WHERE id = %s
                    ''', (full_name, district, age, phone, role, user_id))
                    updated += 1
                else:
                    # Yangi qo'shish
                    password = generate_random_password()
                    hashed_password = generate_password_hash(password)
                    
                    cursor.execute('''
                        INSERT INTO users (id, full_name, district, age, phone, role, password, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ''', (user_id, full_name, district, age, phone, role, hashed_password))
                    
                    # Reyting qo'shish
                    cursor.execute('''
                        INSERT INTO user_ratings (user_id, rating, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ''', (user_id, initial_rating))
                    
                    added += 1
                
            except Exception as e:
                errors.append(f"Qator {index+2}: {str(e)}")
                skipped += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f"Import yakunlandi! Qo'shildi: {added}, Yangilandi: {updated}, O'tkazib yuborildi: {skipped}",
            'added': added,
            'updated': updated,
            'skipped': skipped,
            'errors': errors[:5]  # Faqat birinchi 5 ta xato
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/admin/get_tasks', methods=['GET'])
def api_get_tasks():
    """Topshiriqlarni olish"""
    try:
        user_role = session.get('role')
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.*, 
                   u.full_name as assignee_name,
                   a.full_name as admin_name
            FROM user_tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            LEFT JOIN users a ON t.assigned_by = a.id
            ORDER BY t.created_at DESC
        ''')
        
        tasks = cursor.fetchall()
        conn.close()
        
        # Formatlash
        formatted_tasks = []
        for t in tasks:
            formatted_tasks.append({
                'id': t[0],
                'task_id': t[1],
                'title': t[2],
                'description': t[3],
                'assigned_to': t[4],
                'assignee_name': t[17] if len(t) > 17 else t[4],
                'assigned_by': t[5],
                'admin_name': t[18] if len(t) > 18 else 'Admin',
                'deadline': t[6],
                'points': t[7],
                'task_type': t[8],
                'priority': t[9],
                'status': t[10],
                'progress': t[11],
                'created_at': t[12]
            })
        
        return jsonify({
            'success': True,
            'tasks': formatted_tasks,
            'count': len(formatted_tasks),
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



# @app.route('/api/admin/add_user', methods=['POST'])
# def api_add_user():
#     """Yangi foydalanuvchi qo'shish"""
#     try:
#         data = request.json
#         user_id = data.get('id')
#         full_name = data.get('full_name')
#         district = data.get('district')
#         age = data.get('age')
#         phone = data.get('phone', '')
#         role = data.get('role', 'user')
#         initial_rating = data.get('initial_rating', 10)
#         password = data.get('password')
        
#         # MUHIM: Admin o'z viloyatidan boshqasiga foydalanuvchi qo'sha olmaydi!
#         admin_district = get_admin_district()
#         user_role = session.get('role')
        
#         if user_role != 'debugger' and str(district) != str(admin_district):
#             return jsonify({
#                 'success': False,
#                 'error': f"Siz faqat {admin_district}-hududiga foydalanuvchi qo'sha olasiz!"
#             })
        
#         # Qolgan kod...
        
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/login', methods=['POST'])
# def login():
#     """Login qilish"""
#     user_id = request.form.get('user_id')
#     password = request.form.get('password')
    
#     conn = get_db()
#     cursor = conn.cursor()
    
#     cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
#     user = cursor.fetchone()
#     conn.close()
    
#     if user and check_password_hash(user[7], password):
#         session['user_id'] = user[0]
#         session['full_name'] = user[2]
#         session['district'] = user[3]  # MUHIM: Viloyatni saqlash!
#         session['role'] = user[6]
        
#         # Login vaqtini yangilash
#         update_last_login(user[0])
        
#         if user[6] == 'debugger':
#             return redirect('/debugger')
#         elif user[6] == 'admin':
#             return redirect('/admin')
#         else:
#             return redirect('/dashboard')
    
#     return render_template('login.html', error="ID yoki parol xato!")
    
@app.route('/api/admin/dashboard_stats')
@role_required(['admin', 'debugger'])
def dashboard_stats():
    """Dashboard statistikasini olish"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # 1. Foydalanuvchilar statistikasi
        cursor.execute('SELECT COUNT(*) FROM users')
        stats['total_users'] = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) 
            FROM reports 
            WHERE submitted_date >= DATE('now', '-7 days')
        ''')
        stats['active_users'] = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            SELECT COUNT(*) 
            FROM users 
            WHERE created_at >= DATE('now', '-30 days')
        ''')
        stats['new_users'] = cursor.fetchone()[0] or 0
        
        # 2. Hisobotlar statistikasi
        cursor.execute('SELECT COUNT(*) FROM reports')
        stats['total_reports'] = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM reports WHERE status = 'pending'")
        stats['pending_reports'] = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM reports WHERE status = 'approved'")
        stats['approved_reports'] = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            SELECT COUNT(*) 
            FROM reports 
            WHERE to_char(submitted_date, 'YYYY-MM') = to_char(CURRENT_DATE, 'YYYY-MM')
        ''')
        stats['monthly_reports'] = cursor.fetchone()[0] or 0
        
        # 3. Topshiriqlar statistikasi
        try:
            cursor.execute('SELECT COUNT(*) FROM user_tasks')
            stats['total_tasks'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM user_tasks WHERE status = 'in_progress'")
            stats['inprogress_tasks'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM user_tasks WHERE status = 'completed'")
            stats['completed_tasks'] = cursor.fetchone()[0] or 0
        except:
            stats['total_tasks'] = 0
            stats['inprogress_tasks'] = 0
            stats['completed_tasks'] = 0
        
        # 4. Reyting statistikasi
        cursor.execute('SELECT AVG(rating), MAX(rating) FROM users WHERE rating > 0')
        rating_data = cursor.fetchone()
        stats['avg_rating'] = float(rating_data[0] or 0)
        stats['max_rating'] = float(rating_data[1] or 0)
        
        # 5. Hududlar statistikasi
        cursor.execute('SELECT COUNT(DISTINCT district) FROM users')
        stats['active_districts'] = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            SELECT district, COUNT(*) as count 
            FROM users 
            GROUP BY district 
            ORDER BY count DESC 
            LIMIT 1
        ''')
        top_district = cursor.fetchone()
        if top_district:
            stats['top_district'] = get_region_name(top_district[0]) if top_district[0] else '—'
        else:
            stats['top_district'] = '—'
        
        # 6. Database hajmi
        try:
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            stats['database_size'] = round((page_size * page_count) / (1024 * 1024), 2)  # MB
        except:
            stats['database_size'] = 0
        
        # 7. Top foydalanuvchilar
        cursor.execute('''
            SELECT user_id, full_name, district, rating
            FROM users 
            WHERE rating > 0 
            ORDER BY rating DESC 
            LIMIT 5
        ''')
        top_users = cursor.fetchall()
        stats['top_users'] = []
        for user in top_users:
            stats['top_users'].append({
                'user_id': user[0],
                'full_name': user[1],
                'district': get_region_name(user[2]) if user[2] else user[2],
                'rating': user[3] or 0
            })
        
        conn.close()
        
        # Chart ma'lumotlari
        stats['charts'] = {
            'reports_labels': ['Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan', 'Yak'],
            'reports_data': [12, 19, 3, 5, 2, 3, 15],
            'tasks_data': [25, 15, 40, 20]
        }
        
        return jsonify({
            'success': True,
            **stats
        })
        
    except Exception as e:
        print(f"Dashboard stats xatolik: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
        
# Hisobot fayllarini olish
@app.route('/api/admin/get_report_files/<int:report_id>')
def api_get_report_files(report_id):
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT file_path FROM reports WHERE id = %s", (report_id,))
        result = c.fetchone()
        conn.close()
        
        files = []
        if result and result[0]:
            files.append(result[0])
        
        return jsonify({
            'success': True,
            'files': files
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/committee_stats')
@role_required(['admin', 'debugger'])
def api_committee_stats():
    """Qo'mita va yoshlar guruhi statistikasi"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Qo'mita bo'yicha statistika
        c.execute('''
            SELECT COALESCE(NULLIF(qomita,''), 'Belgilanmagan') as qomita, COUNT(*) as count
            FROM users WHERE role = 'user'
            GROUP BY qomita ORDER BY count DESC
        ''')
        qomita_rows = c.fetchall()
        
        # Yoshlar guruhi bo'yicha statistika
        c.execute('''
            SELECT COALESCE(NULLIF(yoshlar_guruhi,''), 'Belgilanmagan') as yoshlar_guruhi, COUNT(*) as count
            FROM users WHERE role = 'user'
            GROUP BY yoshlar_guruhi ORDER BY count DESC
        ''')
        yoshlar_guruhi_rows = c.fetchall()
        
        # Qo'mita bo'yicha o'rtacha reyting
        c.execute('''
            SELECT COALESCE(NULLIF(qomita,''), 'Belgilanmagan') as qomita, 
                   COUNT(*) as count, ROUND(AVG(rating),1) as avg_rating
            FROM users WHERE role = 'user'
            GROUP BY qomita ORDER BY count DESC
        ''')
        qomita_rating_rows = c.fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'qomita_stats': [{'name': r[0], 'count': r[1]} for r in qomita_rows],
            'yoshlar_guruhi_stats': [{'name': r[0], 'count': r[1]} for r in yoshlar_guruhi_rows],
            'qomita_rating_stats': [{'name': r[0], 'count': r[1], 'avg_rating': r[2]} for r in qomita_rating_rows]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

####### v2 ##########
# ======================= ADMIN PANEL UCHUN YANGI API ENDPOINTLARI =======================

@app.route('/api/admin/rating_stats_v2')
def api_rating_stats_v2():
    """Reyting statistikasi API (yangi versiya)"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # 1. Umumiy statistikalar
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
        total_users = c.fetchone()[0] or 0
        
        c.execute("SELECT AVG(rating) FROM users WHERE role = 'user'")
        avg_rating_result = c.fetchone()[0]
        avg_rating = round(float(avg_rating_result or 0), 1)
        
        c.execute("SELECT MAX(rating) FROM users WHERE role = 'user'")
        max_rating = c.fetchone()[0] or 0
        
        # 2. Top 10 foydalanuvchi
        c.execute('''
            SELECT u.user_id, u.full_name, u.district, u.rating, u.joined_date,
                   COUNT(r.id) as report_count
            FROM users u
            LEFT JOIN reports r ON u.user_id = r.user_id
            WHERE u.role = 'user'
            GROUP BY u.user_id
            ORDER BY u.rating DESC
            LIMIT 10
        ''')
        
        top_users = []
        rows = c.fetchall()
        for row in rows:
            top_users.append({
                'user_id': row[0],
                'full_name': row[1],
                'district': row[2],
                'rating': row[3] or 0,
                'joined_date': row[4],
                'report_count': row[5] or 0
            })
        
        # 3. Oylik reyting o'zgarishi
        c.execute('''
            SELECT 
                to_char(submitted_date, 'YYYY-MM') as month,
                AVG(rt.total) as avg_rating,
                COUNT(*) as report_count
            FROM reports r
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE r.status = 'rated' AND rt.total IS NOT NULL
            GROUP BY to_char(submitted_date, 'YYYY-MM')
            ORDER BY month DESC
            LIMIT 6
        ''')
        
        monthly_stats = []
        rows = c.fetchall()
        for row in rows:
            if row[0]:
                monthly_stats.append({
                    'month': row[0],
                    'avg_rating': round(float(row[1] or 0), 1),
                    'report_count': row[2] or 0
                })
        
        # 4. Hududlar bo'yicha statistikalar
        c.execute('''
            SELECT 
                u.district,
                AVG(u.rating) as avg_rating,
                COUNT(*) as user_count
            FROM users u
            WHERE u.role = 'user' AND u.district IS NOT NULL AND u.district != ''
            GROUP BY u.district
            ORDER BY avg_rating DESC
        ''')
        
        district_stats = []
        rows = c.fetchall()
        for row in rows:
            district = str(row[0]).zfill(2) if row[0] else '00'
            district_stats.append({
                'district': get_regions().get(district, f"Hudud {district}"),
                'avg_rating': round(float(row[1] or 0), 1),
                'user_count': row[2] or 0
            })
        
        # 5. Faol foydalanuvchilar (oxirgi 30 kunda login qilgan)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'user' AND last_login > %s", (thirty_days_ago,))
        active_users = c.fetchone()[0] or 0
        
        # 6. Baholangan hisobotlar soni
        c.execute("SELECT COUNT(*) FROM reports WHERE status = 'rated'")
        rated_reports = c.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'avg_rating_all': avg_rating,
                'avg_rating': avg_rating,
                'max_rating': max_rating,
                'active_users': active_users,
                'rated_reports': rated_reports
            },
            'top_users': top_users,
            'monthly_data': monthly_stats,
            'district_data': district_stats
        })
        
    except Exception as e:
        print(f"Reyting statistikasini olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/tasks_list_v2')
def api_tasks_list_v2():
    """Topshiriqlar ro'yxati API (yangi versiya)"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Avval user_tasks jadvalini tekshirish
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_tasks'")
        if not c.fetchone():
            return jsonify({
                'success': False,
                'error': 'user_tasks jadvali topilmadi',
                'stats': {
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'pending_tasks': 0,
                    'overdue_tasks': 0
                },
                'tasks': []
            })
        
        # 1. Statistikalar
        c.execute("SELECT COUNT(*) FROM user_tasks")
        total_tasks = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM user_tasks WHERE status = 'completed'")
        completed_tasks = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM user_tasks WHERE status IN ('pending', 'in_progress')")
        pending_tasks = c.fetchone()[0] or 0
        
        # Muddati o'tgan topshiriqlar
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute('''
            SELECT COUNT(*) FROM user_tasks 
            WHERE deadline < %s AND status NOT IN ('completed', 'cancelled')
        ''', (today,))
        overdue_tasks = c.fetchone()[0] or 0
        
        # 2. Topshiriqlar ro'yxati
        c.execute('''
            SELECT 
                ut.task_id,
                ut.title,
                ut.description,
                ut.assigned_to,
                CASE 
                    WHEN ut.assigned_to = 'all' THEN 'Barcha'
                    ELSE u.full_name 
                END as assignee_name,
                ut.deadline,
                ut.points,
                ut.status,
                ut.priority,
                ut.created_at,
                admin_u.full_name as admin_name
            FROM user_tasks ut
            LEFT JOIN users u ON ut.assigned_to = u.user_id
            LEFT JOIN users admin_u ON ut.assigned_by = admin_u.user_id
            ORDER BY 
                CASE ut.priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END,
                ut.deadline ASC
        ''')
        
        tasks = []
        rows = c.fetchall()
        for row in rows:
            deadline = row[5]
            deadline_formatted = None
            if deadline:
                try:
                    deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
                    deadline_formatted = deadline_date.strftime('%d.%m.%Y')
                except:
                    deadline_formatted = deadline
            
            tasks.append({
                'task_id': row[0],
                'title': row[1],
                'description': row[2],
                'assigned_to': row[3],
                'assignee_name': row[4],
                'deadline': row[5],
                'deadline_formatted': deadline_formatted,
                'points': row[6] or 0,
                'status': row[7] or 'pending',
                'priority': row[8] or 'medium',
                'created_at': row[9],
                'admin_name': row[10]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'pending_tasks': pending_tasks,
                'overdue_tasks': overdue_tasks
            },
            'tasks': tasks
        })
        
    except Exception as e:
        print(f"Topshiriqlarni olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/create_task_v2', methods=['POST'])
def api_admin_create_task_v2():
    """Yangi topshiriq yaratish API (yangi versiya)"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        data = request.json
        
        # Majburiy maydonlarni tekshirish
        required_fields = ['title', 'assignee', 'deadline']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                return jsonify({'success': False, 'error': f'{field} maydoni to\'ldirilishi shart'})
        
        # Topshiriq ID generatsiya qilish
        task_id = f"TASK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
        
        conn = get_db()
        c = conn.cursor()
        
        # user_tasks jadvalini tekshirish
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_tasks'")
        if not c.fetchone():
            # Agar jadval yo'q bo'lsa, yaratish
            c.execute('''
                CREATE TABLE IF NOT EXISTS user_tasks (
                    id SERIAL PRIMARY KEY,
                    task_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT,
                    assigned_to TEXT,
                    assigned_by TEXT,
                    deadline DATE,
                    points INTEGER DEFAULT 5,
                    task_type TEXT DEFAULT 'regular',
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assigned_by) REFERENCES users(user_id)
                )
            ''')
        
        # Topshiriqni bazaga qo'shish
        c.execute('''
            INSERT INTO user_tasks 
            (task_id, title, description, assigned_to, assigned_by, 
             deadline, points, priority, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', CURRENT_TIMESTAMP)
        ''', (
            task_id,
            data['title'].strip(),
            data.get('description', '').strip(),
            data['assignee'],
            session['user_id'],
            data['deadline'],
            data.get('points', 5),
            data.get('priority', 'medium')
        ))
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'create_task', 
                  f"Yangi topshiriq yaratildi: {task_id} - {data['title']}")
        
        return jsonify({
            'success': True,
            'message': 'Topshiriq muvaffaqiyatli yaratildi!',
            'task_id': task_id
        })
        
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Bu topshiriq ID allaqachon mavjud'})
    except Exception as e:
        print(f"Topshiriq yaratishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ======================= FAYL YUKLAB OLISH =======================

@app.route('/api/admin/download_file/<filename>')
def api_admin_download_file(filename):
    """Faylni yuklab olish API"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        safe_filename = secure_filename(filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            # Pattern orqali qidirish
            import glob
            files = glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], f'*{filename}*'))
            if files:
                return send_file(files[0], as_attachment=True)
            
            return jsonify({'success': False, 'error': 'Fayl topilmadi'}), 404
            
    except Exception as e:
        print(f"Fayl yuklab olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# E'lon yaratish endpointi
@app.route('/api/admin/create_announcement', methods=['POST'])
@admin_required
def api_create_announcement():
    try:
        # Debug uchun log
        print(f"Creating announcement: {request.form}")
        
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        audience = request.form.get('audience', 'all')
        priority = request.form.get('priority', 'normal')
        
        if not title:
            return jsonify({'success': False, 'error': 'Sarlavha kiritilmagan'}), 400
        
        if not content:
            return jsonify({'success': False, 'error': 'Matn kiritilmagan'}), 400
        
        # Rasmni saqlash
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                if allowed_file(filename):
                    image_filename = f"announcement_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(file_path)
        
        # Log yozish
        log_action(session['user_id'], 'create_announcement', 
                  f"Yangi e'lon: {title[:50]}...")
        
        return jsonify({
            'success': True,
            'message': 'E\'lon muvaffaqiyatli yaratildi',
            'announcement_id': 1  # Bu yerda database id qaytariladi
        })
        
    except Exception as e:
        print(f"Error in create_announcement: {e}")
        return jsonify({
            'success': False, 
            'error': f'Server xatosi: {str(e)}'
        }), 500

# Hisobotni baholash (POST endpointi)
@app.route('/rate_report/<int:report_id>', methods=['POST'])
def api_rate_report_post(report_id):
    """Hisobotni baholash (JSON qabul qiladi)"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        data = request.json
        
        # Baholash ma'lumotlari
        faollik = data.get('faollik', 0)
        tashabbus = data.get('tashabbus', 0)
        intizom = data.get('intizom', 0)
        tasir = data.get('tasir', 0)
        comment = data.get('comment', '')
        
        total = faollik + tashabbus + intizom + tasir
        
        conn = get_db()
        c = conn.cursor()
        
        # Baholashni saqlash
        c.execute('''INSERT INTO ratings 
                    (report_id, faollik, tashabbus, intizom, tasir, total, admin_comment) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                 (report_id, faollik, tashabbus, intizom, tasir, total, comment))
        
        # Hisobot holatini yangilash
        c.execute("UPDATE reports SET status = 'rated', admin_comment = %s WHERE id = %s", 
                 (comment, report_id))
        
        # Foydalanuvchi reytingini yangilash
        c.execute('''SELECT user_id FROM reports WHERE id = %s''', (report_id,))
        user_id_result = c.fetchone()
        if user_id_result:
            user_id = user_id_result[0]
            c.execute('''UPDATE users SET rating = rating + %s WHERE user_id = %s''', 
                     (total, user_id))
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'rate_report', 
                  f"Hisobot baholandi: {report_id} - ball: {total}")
        
        return jsonify({
            'success': True,
            'message': 'Hisobot muvaffaqiyatli baholandi!'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Reytinglar uchun API
# REYTING STATISTIKASI API - YANGI VERSIYA
@app.route('/api/admin/rating_dashboard')
@role_required(['debugger', 'admin'])
def api_rating_dashboard():
    # Debug uchun session ma'lumotlarini chop etish
    print(f"DEBUG: Session - user_id: {session.get('user_id')}, role: {session.get('role')}")
    
    # Avval session mavjudligini tekshirish
    if 'user_id' not in session:
        print("DEBUG: Session yo'q - foydalanuvchi tizimga kirmagan")
        return jsonify({'success': False, 'error': 'Kirish talab qilinadi'})
    
    # Keyin rolini tekshirish
    user_role = session.get('role')
    print(f"DEBUG: Foydalanuvchi roli: {user_role}")
    
    if user_role not in ['debugger', 'admin']:
        print(f"DEBUG: Ruxsat yo'q - rol: {user_role}, kerakli: debugger yoki admin")
        return jsonify({'success': False, 'error': f'Ruxsat yo\'q. Sizning rolingiz: {user_role}'})
    
    # Agar debugger bo'lsa, davom etish
    try:
        conn = get_db()
        c = conn.cursor()
        
        # 1. UMUMIY STATISTIKA
        stats = {}
        
        # Foydalanuvchilar soni
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
        stats['total_users'] = c.fetchone()[0] or 0
        
        # O'rtacha reyting
        c.execute("SELECT AVG(rating) FROM users WHERE role = 'user'")
        avg_result = c.fetchone()[0]
        stats['avg_rating'] = round(float(avg_result or 0), 1) if avg_result else 0.0
        
        # Eng yuqori reyting
        c.execute("SELECT MAX(rating) FROM users WHERE role = 'user'")
        stats['max_rating'] = c.fetchone()[0] or 0
        
        # Eng past reyting
        c.execute("SELECT MIN(rating) FROM users WHERE role = 'user'")
        stats['min_rating'] = c.fetchone()[0] or 0
        
        # Aktiv foydalanuvchilar (oxirgi 30 kunda login qilgan)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'user' AND last_login > %s", (thirty_days_ago,))
        active_result = c.fetchone()
        stats['active_users'] = active_result[0] if active_result else 0
        
        print(f"DEBUG: Stats - total_users: {stats['total_users']}, avg_rating: {stats['avg_rating']}")
        
        # 2. HUDUDLAR BO'YICHA STATISTIKA
        c.execute('''
            SELECT 
                u.district,
                COUNT(*) as user_count,
                AVG(u.rating) as avg_rating,
                MAX(u.rating) as max_rating,
                MIN(u.rating) as min_rating
            FROM users u
            WHERE u.role = 'user' AND u.district IS NOT NULL AND u.district != ''
            GROUP BY u.district
            ORDER BY avg_rating DESC
        ''')
        
        district_stats = []
        district_rows = c.fetchall()
        print(f"DEBUG: District rows count: {len(district_rows)}")
        
        for row in district_rows:
            district = str(row[0]).zfill(2) if row[0] else '00'
            district_stats.append({
                'district_code': district,
                'district_name': get_regions().get(district, f"Hudud {district}"),
                'user_count': row[1] or 0,
                'avg_rating': round(float(row[2] or 0), 1) if row[2] else 0.0,
                'max_rating': row[3] or 0,
                'min_rating': row[4] or 0,
                'rating_percentage': round((float(row[2] or 0) / 20) * 100, 1) if row[2] else 0.0
            })
        
        # 3. TOP 10 FOYDALANUVCHI
        c.execute('''
            SELECT 
                u.user_id,
                u.full_name,
                u.district,
                u.rating,
                u.joined_date,
                COUNT(r.id) as report_count,
                COALESCE(SUM(rt.total), 0) as total_score
            FROM users u
            LEFT JOIN reports r ON u.user_id = r.user_id
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE u.role = 'user'
            GROUP BY u.user_id, u.full_name, u.district, u.rating, u.joined_date
            ORDER BY u.rating DESC
            LIMIT 10
        ''')
        
        top_users = []
        top_user_rows = c.fetchall()
        print(f"DEBUG: Top users count: {len(top_user_rows)}")
        
        for row in top_user_rows:
            district = str(row[2]).zfill(2) if row[2] else '00'
            top_users.append({
                'user_id': row[0] or '',
                'full_name': row[1] or 'Noma\'lum',
                'district': get_regions().get(district, district),
                'rating': row[3] or 0,
                'joined_date': row[4] or '',
                'report_count': row[5] or 0,
                'total_score': row[6] or 0
            })
        
        # 4. OYLIK REYTING O'ZGARISHI
        c.execute('''
            SELECT 
                to_char(r.submitted_date, 'YYYY-MM') as month,
                COUNT(DISTINCT r.user_id) as user_count,
                AVG(rt.total) as avg_rating,
                COUNT(*) as report_count
            FROM reports r
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE r.status = 'rated' 
                AND r.submitted_date >= CURRENT_DATE - INTERVAL '6 months'
                AND rt.total IS NOT NULL
            GROUP BY to_char(r.submitted_date, 'YYYY-MM')
            ORDER BY month ASC
        ''')
        
        monthly_stats = []
        monthly_rows = c.fetchall()
        print(f"DEBUG: Monthly rows count: {len(monthly_rows)}")
        
        if len(monthly_rows) < 3:
            # Test ma'lumotlar - faqat demo uchun
            import random
            for i in range(5, -1, -1):
                month_date = datetime.now() - timedelta(days=30*i)
                month_str = month_date.strftime('%Y-%m')
                monthly_stats.append({
                    'month': month_str,
                    'month_name': month_date.strftime('%b %Y'),
                    'user_count': random.randint(3, 10),
                    'avg_rating': round(random.uniform(8, 16), 1),
                    'report_count': random.randint(2, 8)
                })
        else:
            for row in monthly_rows:
                if row[0]:  # month bo'sh bo'lmasa
                    month_date = datetime.strptime(row[0] + '-01', '%Y-%m-%d')
                    monthly_stats.append({
                        'month': row[0],
                        'month_name': month_date.strftime('%b %Y'),
                        'user_count': row[1] or 0,
                        'avg_rating': round(float(row[2] or 0), 1) if row[2] else 0.0,
                        'report_count': row[3] or 0
                    })
        
        # 5. REYTING TAQSIMOTI
        rating_distribution = []
        for i in range(0, 21, 2):  # 0-20, har 2 ballda
            c.execute('''
                SELECT COUNT(*) FROM users 
                WHERE role = 'user' AND rating >= %s AND rating < %s
            ''', (i, i+2))
            count_result = c.fetchone()
            count = count_result[0] if count_result else 0
            total = stats['total_users']
            percentage = round((count / total) * 100, 1) if total > 0 else 0
            
            rating_distribution.append({
                'range': f"{i}-{i+1}",
                'label': f"{i}-{i+1} ball",
                'count': count,
                'percentage': percentage
            })
        
        conn.close()
        
        response_data = {
            'success': True,
            'stats': stats,
            'districts': district_stats,
            'top_users': top_users,
            'monthly_trend': monthly_stats,
            'monthly_data': monthly_stats,  # Ikkala nomda ham qaytaramiz
            'rating_distribution': rating_distribution,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"DEBUG: Response data prepared, districts: {len(district_stats)}, monthly: {len(monthly_stats)}")
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Reyting dashboard xatosi: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


# Session holatini tekshirish endpointi
@app.route('/api/check_session')
def api_check_session():
    return jsonify({
        'logged_in': 'user_id' in session,
        'user_id': session.get('user_id'),
        'role': session.get('role'),
        'full_name': session.get('full_name')
    })

# Hisobot faylini yuklab olish (admin uchun)
@app.route('/admin/download/<filename>')
def admin_download_file(filename):
    if 'user_id' not in session or session.get('role') not in ['admin', 'debugger']:
        flash('Ruxsat yo\'q!')
        return redirect(url_for('login'))
    
    # Fayl nomini to'g'rilash
    safe_filename = secure_filename(filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        # Agar to'g'ridan-to'g'ri topilmasa, pattern orqali qidirish
        try:
            import glob
            files = glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], f'*{filename}*'))
            if files:
                return send_file(files[0], as_attachment=True)
        except:
            pass
        
        flash('Fayl topilmadi!', 'danger')
        return redirect(url_for('admin_panel'))
        

@app.route('/api/admin/check_tables')
def api_check_tables():
    if session.get('role') != 'debugger':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # user_tasks jadvali strukturasini tekshirish
        c.execute("PRAGMA table_info(user_tasks)")
        user_tasks_columns = []
        for col in c.fetchall():
            user_tasks_columns.append({
                'name': col[1],
                'type': col[2],
                'notnull': col[3],
                'default': col[4]
            })
        
        # user_tasks jadvalidagi ma'lumotlar
        c.execute("SELECT COUNT(*) FROM user_tasks")
        user_tasks_count = c.fetchone()[0]
        
        c.execute("SELECT * FROM user_tasks LIMIT 1")
        sample_row = c.fetchone()
        sample_data = None
        if sample_row:
            sample_data = {}
            c.execute("PRAGMA table_info(user_tasks)")
            columns_info = c.fetchall()
            for i, col_info in enumerate(columns_info):
                if i < len(sample_row):
                    sample_data[col_info[1]] = sample_row[i]
        
        # users jadvali
        c.execute("PRAGMA table_info(users)")
        users_columns = [col[1] for col in c.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user_tasks': {
                'columns': user_tasks_columns,
                'count': user_tasks_count,
                'sample': sample_data
            },
            'users_columns': users_columns
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/recreate_user_tasks', methods=['POST'])
def api_recreate_user_tasks():
    if session.get('role') != 'debugger':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # 1. Avval jadvaldagi barcha ma'lumotlarni saqlab olamiz (agar kerak bo'lsa)
        try:
            c.execute("SELECT * FROM user_tasks")
            old_data = c.fetchall()
            c.execute("PRAGMA table_info(user_tasks)")
            old_columns = [col[1] for col in c.fetchall()]
            print(f"📦 Eski ma'lumotlar saqlandi: {len(old_data)} qator")
        except:
            old_data = []
            old_columns = []
        
        # 2. Eski jadvalni o'chirish
        c.execute('DROP TABLE IF EXISTS user_tasks')
        
        # 3. Yangi jadval yaratish
        create_sql = '''
            CREATE TABLE user_tasks (
                id SERIAL PRIMARY KEY,
                task_id TEXT UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                assigned_to TEXT,
                assigned_by TEXT,
                deadline DATE,
                points INTEGER DEFAULT 5,
                task_type TEXT DEFAULT 'regular',
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                completed_by TEXT,
                completed_at TIMESTAMP,
                feedback TEXT,
                rating_given INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assigned_by) REFERENCES users(user_id)
            )
        '''
        c.execute(create_sql)
        
        # 4. Test ma'lumotlar qo'shish
        test_tasks = [
            ('TASK-20250125-0001', 'Yoshlar sonini aniqlash', 
             'Hududingizdagi yoshlar sonini hisoblang', 'all', 'debug001',
             '2024-12-31', 10, 'monthly', 'high'),
            ('TASK-20250125-0002', 'Hisobot tayyorlash',
             'Oylik hisobotni vaqtida topshirish', 'all', 'debug001',
             '2024-12-20', 5, 'regular', 'medium'),
            ('TASK-20250125-0003', 'Uchrashuv tashkil qilish',
             'Kamida 20 yosh bilan uchrashuv o\'tkazish', 'FR-2024-001', 'debug001',
             '2024-12-15', 8, 'urgent', 'high')
        ]
        
        for task in test_tasks:
            c.execute('''
                INSERT INTO user_tasks 
                (task_id, title, description, assigned_to, assigned_by, 
                 deadline, points, task_type, priority, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', CURRENT_TIMESTAMP)
            ''', task)
        
        conn.commit()
        conn.close()
        
        print("✅ user_tasks jadvali to'liq qayta yaratildi")
        
        return jsonify({
            'success': True,
            'message': 'user_tasks jadvali qayta yaratildi. 3 ta test topshiriq qo\'shildi.'
        })
        
    except Exception as e:
        print(f"❌ user_tasks jadvalini qayta yaratishda xatolik: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# Console uchun API endpointlari

@app.route('/api/console/execute', methods=['POST'])
def api_console_execute():
    if session.get('role') != 'debugger':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        data = request.json
        command = data.get('command', '').strip()
        
        # Command dispatcher
        if command.startswith('sql '):
            sql_query = command[4:]
            return execute_sql_command(sql_query)
        elif command == 'check tables':
            return check_tables_command()
        elif command == 'fix tables':
            return fix_tables_command()
        elif command == 'optimize':
            return optimize_db_command()
        elif command == 'vacuum':
            return vacuum_db_command()
        elif command == 'backup':
            return backup_db_command()
        elif command == 'system status':
            return system_status_command()
        elif command == 'list users':
            return list_users_command()
        elif command == 'clear cache':
            return clear_cache_command()
        elif command == 'help':
            return help_command()
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown command: {command}. Type "help" for available commands.'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def execute_sql_command(sql_query):
    """SQL so'rov bajarish"""
    try:
        if not sql_query.upper().startswith('SELECT'):
            return jsonify({
                'success': False,
                'error': 'Only SELECT queries are allowed for security'
            })
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute(sql_query)
        results = c.fetchall()
        
        # Format results
        formatted_results = []
        for row in results:
            formatted_results.append(dict(row))
        
        conn.close()
        
        return jsonify({
            'success': True,
            'type': 'sql',
            'results': formatted_results,
            'count': len(formatted_results)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def check_tables_command():
    """Jadvallarni tekshirish"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Barcha jadvallarni olish
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in c.fetchall()]
        
        # Har bir jadval strukturasini olish
        table_info = {}
        for table in tables:
            c.execute(f"PRAGMA table_info({table})")
            columns = c.fetchall()
            table_info[table] = {
                'columns': len(columns),
                'column_names': [col[1] for col in columns]
            }
        
        conn.close()
        
        return jsonify({
            'success': True,
            'type': 'tables',
            'tables': tables,
            'table_info': table_info,
            'total_tables': len(tables)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/console/system_info')
def api_console_system_info():
    """Sistem ma'lumotlari"""
    if session.get('role') != 'debugger':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        import platform
        import psutil
        
        system_info = {
            'python_version': platform.python_version(),
            'platform': platform.platform(),
            'processor': platform.processor(),
            'flask_version': '2.0.1',  # flask.__version__ ni import qilishingiz kerak
            'database_path': app.config['DATABASE'],
            'uptime': get_system_uptime(),
            'memory_usage': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'cpu_usage': psutil.cpu_percent(interval=1)
        }
        
        return jsonify({
            'success': True,
            'type': 'system_info',
            'system': system_info
        })
        
    except ImportError:
        return jsonify({
            'success': True,
            'type': 'system_info',
            'system': {
                'python_version': platform.python_version(),
                'platform': platform.platform(),
                'database_path': app.config['DATABASE']
            },
            'warning': 'psutil not installed'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def get_system_uptime():
    """Sistem uptime ni olish"""
    try:
        import psutil
        import datetime
        boot_time = psutil.boot_time()
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(boot_time)
        
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return f"{days}d {hours}h {minutes}m {seconds}s"
    except:
        return "Unknown"

############console#########  

# REYTINGLAR JADVALI
# @app.route('/api/admin/ratings_table')
# def api_ratings_table():
#     if session.get('role') not in ['debugger', 'admin']:
#         return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
#     try:
#         conn = get_db()
#         c = conn.cursor()
        
#         admin_district = session.get('district')
#         role = session.get('role')
        
#         # Filter parametrlari
#         district_filter = request.args.get('district', 'all')
#         rating_filter = request.args.get('rating', 'all')
#         sort_by = request.args.get('sort', 'rating_desc')
#         search_term = request.args.get('search', '')
        
#         # -------------------------------
#         # ASOSIY FILTER - ADMIN HUDUDI
#         # -------------------------------
#         query = "SELECT u.user_id, u.full_name, u.district, u.rating, u.joined_date, u.last_login FROM users u WHERE u.role = 'user'"
#         params = []
        
#         if role != 'debugger':
#             query += " AND u.district = %s"
#             params.append(admin_district)
#         elif district_filter != 'all':
#             query += " AND u.district = %s"
#             params.append(district_filter)
        
#         # Reyting filteri
#         if rating_filter == 'high':
#             query += " AND u.rating >= 15"
#         elif rating_filter == 'medium':
#             query += " AND u.rating BETWEEN 10 AND 14"
#         elif rating_filter == 'low':
#             query += " AND u.rating < 10"
        
#         # Qidirish
#         if search_term:
#             query += " AND (u.full_name LIKE %s OR u.user_id LIKE %s)"
#             params.append(f'%{search_term}%')
#             params.append(f'%{search_term}%')
        
#         # Tartiblash
#         if sort_by == 'rating_desc':
#             query += " ORDER BY u.rating DESC"
#         elif sort_by == 'rating_asc':
#             query += " ORDER BY u.rating ASC"
#         elif sort_by == 'name_asc':
#             query += " ORDER BY u.full_name ASC"
#         elif sort_by == 'name_desc':
#             query += " ORDER BY u.full_name DESC"
        
#         c.execute(query, params)
#         users = c.fetchall()
        
#         # Hisobotlar sonini qo'shimcha olish
#         formatted_users = []
#         for user in users:
#             user_id = user[0]
            
#             c.execute("SELECT COUNT(*) FROM reports WHERE user_id = %s", (user_id,))
#             total_reports = c.fetchone()[0] or 0
            
#             c.execute("SELECT COUNT(*) FROM reports WHERE user_id = %s AND status = 'rated'", (user_id,))
#             rated_reports = c.fetchone()[0] or 0
            
#             rating = user[3] or 0
#             rating_percentage = round((rating / 20) * 100, 1)
            
#             formatted_users.append({
#                 'user_id': user[0],
#                 'full_name': user[1],
#                 'district': user[2],
#                 'district_code': user[2],
#                 'rating': rating,
#                 'rating_percentage': rating_percentage,
#                 'total_reports': total_reports,
#                 'rated_reports': rated_reports,
#                 'joined_date': user[4]
#             })
        
#         conn.close()
        
#         return jsonify({
#             'success': True,
#             'users': formatted_users,
#             'total_count': len(formatted_users)
#         })
        
#     except Exception as e:
#         return jsonify({'success': False, 'error': str(e)})

def get_activity_level(last_login):
    if not last_login:
        return 'inactive'
    
    login_date = datetime.strptime(last_login, '%Y-%m-%d %H:%M:%S')
    days_diff = (datetime.now() - login_date).days
    
    if days_diff <= 7:
        return 'very_active'
    elif days_diff <= 30:
        return 'active'
    elif days_diff <= 90:
        return 'less_active'
    else:
        return 'inactive'

def get_rating_status(rating):
    if rating >= 16:
        return 'excellent'
    elif rating >= 13:
        return 'good'
    elif rating >= 10:
        return 'average'
    elif rating >= 7:
        return 'needs_improvement'
    else:
        return 'poor'
# Reytinglar ma'lumotlarini olish API
@app.route('/api/admin/get_ratings')
def api_get_ratings():
    if session.get('role') != 'debugger':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # user_ratings jadvalini tekshirish va yaratish
        c.execute('''CREATE TABLE IF NOT EXISTS user_ratings (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT,
                        full_name TEXT,
                        district TEXT,
                        current_rating INTEGER DEFAULT 0,
                        last_week_rating INTEGER DEFAULT 0,
                        monthly_change INTEGER DEFAULT 0,
                        total_points INTEGER DEFAULT 0,
                        tasks_completed INTEGER DEFAULT 0,
                        reports_submitted INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        # Foydalanuvchilar reytinglarini olish
        c.execute('''
            SELECT 
                u.user_id,
                u.full_name,
                u.district,
                u.rating as current_rating,
                COALESCE(ur.last_week_rating, u.rating - 5) as last_week_rating,
                COALESCE(ur.monthly_change, 0) as monthly_change,
                COALESCE(ur.total_points, 0) as total_points,
                COALESCE(ur.tasks_completed, 0) as tasks_completed,
                COALESCE(ur.reports_submitted, 0) as reports_submitted
            FROM users u
            LEFT JOIN user_ratings ur ON u.user_id = ur.user_id
            WHERE u.role = 'user'
            ORDER BY u.rating DESC
        ''')
        
        ratings = c.fetchall()
        columns = [desc[0] for desc in c.description]
        
        # Formatlash
        ratings_list = []
        for rating in ratings:
            rating_dict = {}
            for i, col in enumerate(columns):
                rating_dict[col] = rating[i]
            
            # O'zgarishni hisoblash
            if rating_dict['last_week_rating']:
                change = rating_dict['current_rating'] - rating_dict['last_week_rating']
            else:
                change = 0
            rating_dict['change'] = change
            
            ratings_list.append(rating_dict)
        
        # Statistik ma'lumotlar
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT AVG(rating) FROM users WHERE role = 'user'")
        avg_rating = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM reports WHERE status = 'rated'")
        rated_reports = c.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'ratings': ratings_list,
            'stats': {
                'total_users': total_users,
                'avg_rating': round(float(avg_rating), 1),
                'rated_reports': rated_reports
            }
        })
        
    except Exception as e:
        print(f"Reytinglarni olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Reyting ma'lumotlarini yangilash API
@app.route('/api/admin/update_ratings', methods=['POST'])
def api_update_ratings():
    if session.get('role') != 'debugger':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # user_ratings jadvalini tekshirish va yaratish
        c.execute('''CREATE TABLE IF NOT EXISTS user_ratings (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT UNIQUE,
                        full_name TEXT,
                        district TEXT,
                        current_rating INTEGER DEFAULT 0,
                        last_week_rating INTEGER DEFAULT 0,
                        monthly_change INTEGER DEFAULT 0,
                        total_points INTEGER DEFAULT 0,
                        tasks_completed INTEGER DEFAULT 0,
                        reports_submitted INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        # Joriy haftalik reytinglarni saqlash
        c.execute('''
            INSERT OR REPLACE INTO user_ratings 
            (user_id, full_name, district, current_rating, last_week_rating, 
             monthly_change, updated_at)
            SELECT 
                u.user_id,
                u.full_name,
                u.district,
                u.rating,
                COALESCE(ur.current_rating, u.rating),
                (u.rating - COALESCE(ur.current_rating, u.rating)) as monthly_change,
                CURRENT_TIMESTAMP
            FROM users u
            LEFT JOIN user_ratings ur ON u.user_id = ur.user_id
            WHERE u.role = 'user'
        ''')
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'update_ratings', 'Reyting ma\'lumotlari yangilandi')
        
        return jsonify({
            'success': True,
            'message': 'Reyting ma\'lumotlari muvaffaqiyatli yangilandi'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Reytinglar uchun API - TUZATILGAN
@app.route('/api/admin/generate_test_ratings', methods=['POST'])
def generate_test_ratings():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()  # conn qo'shildi
        cursor = conn.cursor()  # cursor qo'shildi
        
        # ratings jadvalini tekshirish (ratings_new deb nomlaymiz)
        cursor.execute('''CREATE TABLE IF NOT EXISTS ratings_new (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT,
                            full_name TEXT,
                            district TEXT,
                            current_rating INTEGER,
                            last_week_rating INTEGER,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )''')
        
        cursor.execute("""
            INSERT INTO ratings_new (user_id, full_name, district, current_rating, last_week_rating, created_at)
            SELECT 
                user_id,
                full_name,
                district,
                ROUND(RANDOM() * 20) as current_rating,
                ROUND(RANDOM() * 20) as last_week_rating,
                CURRENT_TIMESTAMP
            FROM users
            WHERE role = 'user'
            LIMIT 10
        """)
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Test reyting ma\'lumotlari muvaffaqiyatli yaratildi',
            'count': cursor.rowcount
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Topshiriqlar uchun API - TUZATILGAN


#####qoshilgan kodlar:

# Chart.js uchun ma'lumotlar:
@app.route('/api/admin/chart_data')
def api_chart_data():
    if session.get('role') != 'debugger':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # 1. Hududlar bo'yicha foydalanuvchilar soni
        c.execute('''
            SELECT 
                district,
                COUNT(*) as user_count,
                AVG(rating) as avg_rating
            FROM users
            WHERE role = 'user' AND district IS NOT NULL
            GROUP BY district
            ORDER BY user_count DESC
        ''')
        districts_data = c.fetchall()
        
        # 2. Oylik hisobotlar soni
        c.execute('''
            SELECT 
                to_char(submitted_date, 'YYYY-MM') as month,
                COUNT(*) as report_count
            FROM reports
            WHERE submitted_date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY to_char(submitted_date, 'YYYY-MM')
            ORDER BY month
        ''')
        monthly_data = c.fetchall()
        
        # 3. Reyting taqsimoti
        c.execute('''
            SELECT 
                CASE 
                    WHEN rating >= 16 THEN 'A\'lo (16-20)'
                    WHEN rating >= 13 THEN 'Yaxshi (13-15)'
                    WHEN rating >= 10 THEN 'O\'rta (10-12)'
                    WHEN rating >= 7 THEN 'Qoniqarli (7-9)'
                    ELSE 'Qoniqarsiz (0-6)'
                END as rating_range,
                COUNT(*) as user_count
            FROM users
            WHERE role = 'user'
            GROUP BY rating_range
            ORDER BY 
                CASE rating_range
                    WHEN 'A\'lo (16-20)' THEN 1
                    WHEN 'Yaxshi (13-15)' THEN 2
                    WHEN 'O\'rta (10-12)' THEN 3
                    WHEN 'Qoniqarli (7-9)' THEN 4
                    ELSE 5
                END
        ''')
        rating_distribution = c.fetchall()
        
        conn.close()
        
        # Formatlash
        return jsonify({
            'success': True,
            'districts': {
                'labels': [get_regions().get(str(d[0]).zfill(2), d[0]) for d in districts_data],
                'user_counts': [d[1] for d in districts_data],
                'avg_ratings': [float(d[2] or 0) for d in districts_data]
            },
            'monthly': {
                'labels': [d[0] for d in monthly_data],
                'counts': [d[1] for d in monthly_data]
            },
            'distribution': {
                'labels': [d[0] for d in rating_distribution],
                'counts': [d[1] for d in rating_distribution]
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Diagrammalar sahifasi
@app.route('/rating_dashboard')
def rating_dashboard():
    if 'user_id' not in session or session.get('role') != 'debugger':
        return redirect(url_for('dashboard'))
    return render_template('rating_dashboard.html')

# YANGI: Topshiriq yaratish API
@app.route('/api/admin/create_task', methods=['POST'])
def api_create_task():
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        # FormData yoki JSON tekshirish
        if request.content_type.startswith('multipart/form-data'):
            data = request.form
            file = request.files.get('file')
        else:
            data = request.json
            file = None
        
        # Majburiy maydonlarni tekshirish
        required_fields = ['title', 'assigned_to', 'deadline']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'{field} maydoni to\'ldirilishi shart'})
        
        # Faylni yuklash
        file_path = None
        if file and file.filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            filename = f"task_{timestamp}.{file_ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(file_path)
            file_path = filename
        
        # Topshiriq ID generatsiya qilish
        task_id = f"TASK-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        
        conn = get_db()
        c = conn.cursor()
        
        # user_tasks jadvalini tekshirish va yaratish
        c.execute('''CREATE TABLE IF NOT EXISTS user_tasks (
                        id SERIAL PRIMARY KEY,
                        task_id TEXT UNIQUE,
                        title TEXT NOT NULL,
                        description TEXT,
                        assigned_to TEXT,
                        assigned_by TEXT,
                        deadline DATE,
                        points INTEGER DEFAULT 5,
                        task_type TEXT DEFAULT 'regular',
                        priority TEXT DEFAULT 'medium',
                        status TEXT DEFAULT 'pending',
                        progress INTEGER DEFAULT 0,
                        file_path TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (assigned_by) REFERENCES users(user_id)
                    )''')
        
        # Topshiriqni bazaga qo'shish
        c.execute('''INSERT INTO user_tasks 
                    (task_id, title, description, assigned_to, assigned_by, 
                     deadline, points, task_type, priority, file_path) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                 (task_id, data['title'], data.get('description', ''),
                  data['assigned_to'], session['user_id'],
                  data['deadline'], int(data.get('points', 5)),
                  data.get('task_type', 'regular'), 
                  data.get('priority', 'medium'),
                  file_path))
        
        conn.commit()
        conn.close()
        
        # Log yozish
        log_action(session['user_id'], 'create_task', 
                  f"Yangi topshiriq: {task_id} - {data['title']}")
        
        return jsonify({
            'success': True, 
            'message': 'Topshiriq muvaffaqiyatli yaratildi!',
            'task_id': task_id
        })
    
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Bu topshiriq ID allaqachon mavjud'})
    except Exception as e:
        print(f"Topshiriq yaratishda xatolik: {str(e)}")
        return jsonify({'success': False, 'error': f'Server xatosi: {str(e)}'})


@app.route('/api/admin/download/<filename>')
def api_admin_download(filename):
    """Faylni yuklab olish API"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        safe_filename = secure_filename(filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            # Pattern orqali qidirish
            import glob
            files = glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], f'*{filename}*'))
            if files:
                return send_file(files[0], as_attachment=True)
            
            return jsonify({'success': False, 'error': 'Fayl topilmadi'}), 404
            
    except Exception as e:
        print(f"Fayl yuklab olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ======================= E'LONLAR API =======================

@app.route('/api/admin/get_announcements')
def api_get_announcements():
    """E'lonlarni olish API"""
    try:
        # Avval session ni tekshirish
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Login qilmagansiz'}), 401
        
        if session.get('role') not in ['admin', 'debugger']:
            return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
        
        # Test ma'lumotlar
        announcements = [
            {
                'id': 1,
                'title': 'Yangi hisobot formati',
                'content': '2024-yil fevral oyidan boshlab hisobotlarni yangi formatda topshirishingizni iltimos qilamiz.',
                'author': 'Admin',
                'created_at': '2024-01-25 14:30:00',
                'priority': 'important',
                'audience': 'Barcha foydalanuvchilar',
                'views': 45,
                'image': None
            },
            {
                'id': 2,
                'title': 'Reyting tizimi yangilandi',
                'content': 'Reyting tizimi yangilandi. Endi har bir hisobot 20 ball tizimi asosida baholanadi.',
                'author': 'Super Admin',
                'created_at': '2024-01-24 10:15:00',
                'priority': 'urgent',
                'audience': 'Barcha foydalanuvchilar',
                'views': 78,
                'image': None
            },
            {
                'id': 3,
                'title': 'Topshiriqlar bo\'limi',
                'content': 'Yangi topshiriqlar bo\'limi qo\'shildi. Adminlar foydalanuvchilarga vazifalar berishi mumkin.',
                'author': 'Admin',
                'created_at': '2024-01-23 09:00:00',
                'priority': 'normal',
                'audience': 'Barcha foydalanuvchilar',
                'views': 32,
                'image': None
            }
        ]
        
        return jsonify({
            'success': True,
            'announcements': announcements
        })
        
    except Exception as e:
        print(f"Error in get_announcements: {e}")
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500

@app.route('/api/admin/complete_task/<task_id>', methods=['POST'])
def complete_task(task_id):
    """Topshiriqni bajarilgan deb belgilash"""
    try:
        cursor.execute("""
            UPDATE tasks 
            SET status = 'completed', 
                completed_at = CURRENT_TIMESTAMP
            WHERE task_id = %s
        """, (task_id,))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Topshiriq bajarilgan deb belgilandi'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/delete_task/<task_id>', methods=['DELETE'])
@role_required(['debugger', 'admin'])
def delete_task(task_id):
    """Topshiriqni o'chirish"""
    try:
        cursor.execute("DELETE FROM user_tasks WHERE task_id = %s", (task_id,))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Topshiriq muvaffaqiyatli o\'chirildi'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def generate_id():
    """ID generatsiya qilish"""
    import random
    import string
    return ''.join(random.choices(string.digits, k=6))

def get_region_name(code):
    """Hudud kodidan nomini olish"""
    regions = {
        '01': 'Toshkent shahri',
        '02': 'Toshkent viloyati',
        '03': 'Andijon viloyati',
        '04': 'Fargʻona viloyati',
        '05': 'Namangan viloyati',
        '06': 'Samarqand viloyati',
        '07': 'Buxoro viloyati',
        '08': 'Xorazm viloyati',
        '09': 'Surxondaryo viloyati',
        '10': 'Qashqadaryo viloyati',
        '11': 'Jizzax viloyati',
        '12': 'Sirdaryo viloyati',
        '13': 'Navoiy viloyati',
        '14': 'Qoraqalpogʻiston Respublikasi'
    }
    return regions.get(code)

@app.route('/api/admin/table_structure', methods=['POST'])
def table_structure():
    """Jadval tuzilishini ko'rsatish"""
    try:
        data = request.get_json()
        table_name = data.get('table', '').strip()
        
        if not table_name:
            return jsonify({
                'success': False,
                'error': 'Table name is required'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Jadval maydonlarini olish
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # Jadval statistikasini olish
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            # Index ma'lumotlarini olish
            cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = cursor.fetchall()
            
            conn.close()
            
            # Natijani formatlash
            structure = {
                'table_name': table_name,
                'row_count': row_count,
                'columns': [],
                'indexes': []
            }
            
            for col in columns:
                structure['columns'].append({
                    'cid': col[0],
                    'name': col[1],
                    'type': col[2],
                    'notnull': bool(col[3]),
                    'default_value': col[4],
                    'pk': bool(col[5])
                })
            
            for idx in indexes:
                structure['indexes'].append({
                    'seq': idx[0],
                    'name': idx[1],
                    'unique': bool(idx[2]),
                    'origin': idx[3],
                    'partial': bool(idx[4])
                })
            
            return jsonify({
                'success': True,
                'structure': structure,
                'message': f'Table structure retrieved for {table_name}'
            })
            
        except Exception as e:
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Table not found or error: {str(e)}'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/admin/truncate_table', methods=['POST'])
def truncate_table():
    """Jadvalni tozalash (TRUNCATE)"""
    try:
        data = request.get_json()
        table_name = data.get('table', '').strip()
        
        if not table_name:
            return jsonify({
                'success': False,
                'error': 'Table name is required'
            }), 400
        
        # Muhim jadvallarni himoya qilish
        protected_tables = ['users', 'admins', 'system_settings']
        if table_name in protected_tables:
            return jsonify({
                'success': False,
                'error': f'Table {table_name} is protected and cannot be truncated'
            }), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Avval jadvaldagi ma'lumotlar sonini olish
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        
        # Jadvalni tozalash
        cursor.execute(f"DELETE FROM {table_name}")
        
        # Sequence ni qayta o'rnatish (AUTOINCREMENT uchun)
        try:
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")
        except:
            pass
        
        conn.commit()
        conn.close()
        
        # Log yozish
        log_action('debugger', 'truncate_table', f'Truncated table {table_name} ({row_count} rows removed)')
        
        return jsonify({
            'success': True,
            'message': f'Table {table_name} truncated successfully. Removed {row_count} rows.',
            'rows_removed': row_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/admin/drop_table', methods=['POST'])
def drop_table():
    """Jadvalni o'chirish"""
    try:
        data = request.get_json()
        table_name = data.get('table', '').strip()
        
        if not table_name:
            return jsonify({
                'success': False,
                'error': 'Table name is required'
            }), 400
        
        # Muhim jadvallarni himoya qilish
        critical_tables = ['users', 'admins', 'system_settings', 'logs']
        if table_name in critical_tables:
            return jsonify({
                'success': False,
                'error': f'Table {table_name} is critical and cannot be dropped'
            }), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Jadval mavjudligini tekshirish
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=%s", (table_name,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Table {table_name} does not exist'
            }), 404
        
        # Jadvalni o'chirish
        cursor.execute(f"DROP TABLE {table_name}")
        
        conn.commit()
        conn.close()
        
        # Log yozish
        log_action('debugger', 'drop_table', f'Dropped table {table_name}')
        
        return jsonify({
            'success': True,
            'message': f'Table {table_name} dropped successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        

 
# debugger.html da ishlatilgan executeQuery() uchun:
@app.route('/api/admin/execute_query', methods=['POST'])
def api_execute_query():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'error': 'SQL so\'rov kiriting!'})
        
        # Faqat SELECT so'rovlariga ruxsat (xavfsizlik uchun)
        if not query.upper().startswith('SELECT'):
            return jsonify({'success': False, 'error': 'Faqat SELECT so\'rovlariga ruxsat'})
        
        conn = get_db()
        conn.row_factory = sqlite3.Row  # Dictionary formatda qaytarish
        c = conn.cursor()
        
        try:
            c.execute(query)
            results = c.fetchall()
            
            # Kolonka nomlari
            columns = [desc[0] for desc in c.description] if c.description else []
            
            # Ma'lumotlarni formatlash
            formatted_results = []
            for row in results:
                formatted_results.append(dict(row))
            
            conn.close()
            
            log_action(session['user_id'], 'execute_query', 
                      f"SQL so'rov bajarildi: {query[:50]}...")
            
            return jsonify({
                'success': True,
                'columns': columns,
                'results': formatted_results,
                'count': len(formatted_results)
            })
            
        except sqlite3.Error as e:
            return jsonify({'success': False, 'error': f'SQL xatosi: {str(e)}'})
        
    except Exception as e:
        print(f"SQL so'rov bajarishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})
        
#############################################################################################
##############   Test loglar yaratish endpointi   #########   koment olib qoyiladi keyin   ##
#############################################################################################
@app.route('/api/admin/generate_test_logs', methods=['POST'])
def api_generate_test_logs():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        test_actions = [
            ('login', 'Tizimga kirish'),
            ('create_task', 'Yangi topshiriq yaratildi'),
            ('submit_report', 'Hisobot yuborildi'),
            ('rate_report', 'Hisobot baholandi'),
            ('update_profile', 'Profil yangilandi'),
            ('export_data', 'Ma\'lumotlar eksport qilindi'),
            ('import_data', 'Ma\'lumotlar import qilindi'),
            ('delete_user', 'Foydalanuvchi o\'chirildi'),
            ('reset_password', 'Parol tiklandi')
        ]
        
        test_users = ['debug001', 'admin001', 'FR-2024-001', 'FR-2024-002']
        
        conn = get_db()
        c = conn.cursor()
        
        for _ in range(20):  # 20 ta test log
            user = random.choice(test_users)
            action, action_text = random.choice(test_actions)
            details = f"Test log - {action_text}"
            
            days_offset = f"{random.randint(0, 30)} days"
            c.execute('''
                INSERT INTO system_logs (user_id, action, details, timestamp)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP - CAST(%s AS INTERVAL))
            ''', (user, action, details, days_offset))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '20 ta test log yaratildi'
        })
        
    except Exception as e:
        print(f"Test log yaratishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})


# 2. FOYDALANUVCHINI O'CHIRISH API
@app.route('/api/admin/user/<user_id>/delete', methods=['DELETE'])
def api_admin_delete_user(user_id):
    """Foydalanuvchini o'chirish"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Foydalanuvchi mavjudligini tekshirish
        c.execute("SELECT full_name FROM users WHERE user_id=%s", (user_id,))
        user = c.fetchone()
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'Foydalanuvchi topilmadi'}), 404
        
        # Foydalanuvchini o'chirish
        c.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
        
        # Bog'liq ma'lumotlarni ham o'chirish (agar kerak bo'lsa)
        c.execute("DELETE FROM reports WHERE user_id=%s", (user_id,))
        c.execute("DELETE FROM user_tasks WHERE assigned_to=%s", (user_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{user[0]} o\'chirildi'
        })
        
    except Exception as e:
        print(f"Foydalanuvchi o'chirishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# 3. PAROLNI TIKLASH API
@app.route('/api/admin/user/<user_id>/reset-password', methods=['POST'])
def api_admin_reset_password(user_id):
    """Foydalanuvchi parolini tiklash"""
    try:
        data = request.get_json()
        new_password = data.get('new_password')
        
        if not new_password:
            return jsonify({'success': False, 'error': 'Yangi parol kiritilmadi'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'error': 'Parol kamida 6 ta belgidan iborat bo\'lishi kerak'}), 400
        
        conn = get_db()
        c = conn.cursor()
        
        # Foydalanuvchi mavjudligini tekshirish
        c.execute("SELECT full_name FROM users WHERE user_id=%s", (user_id,))
        user = c.fetchone()
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'Foydalanuvchi topilmadi'}), 404
        
        # Parolni yangilash
        hashed_password = generate_password_hash(new_password)
        c.execute("UPDATE users SET password=%s WHERE user_id=%s", 
                 (hashed_password, user_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{user[0]} paroli yangilandi'
        })
        
    except Exception as e:
        print(f"Parol yangilashda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# debugger.html da file upload uchun:
@app.route('/api/admin/process_excel', methods=['POST'])
def api_process_excel():
    if session.get('role') != 'debugger':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Fayl topilmadi'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Fayl tanlanmagan'})
    
    try:
        # Fayl turini aniqlash
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        else:
            return jsonify({'success': False, 'error': 'Faqat CSV yoki Excel fayllar'})
        
        # Majburiy ustunlarni tekshirish
        required_columns = ['ID', 'FullName', 'District', 'Age', 'Role', 'InitialRating']
        for col in required_columns:
            if col not in df.columns:
                return jsonify({'success': False, 'error': f'{col} ustuni topilmadi'})
        
        conn = get_db()
        c = conn.cursor()
        
        success_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                user_id = str(row['ID']).zfill(4)
                full_name = str(row['FullName']).strip()
                district = str(row['District']).zfill(2)
                age = int(row['Age'])
                phone = str(row.get('Phone', '')).strip()
                role = str(row['Role']).lower()
                initial_rating = int(row['InitialRating'])
                
                # Parol generatsiya qilish
                password = generate_random_password()
                hashed_password = generate_password_hash(password)
                
                # Telefon formatini tekshirish
                if phone and not phone.startswith('+998'):
                    phone = '+998' + phone[-9:]
                
                # Foydalanuvchini qo'shish/yangilash
                c.execute('SELECT user_id FROM users WHERE user_id = %s', (user_id,))
                existing = c.fetchone()
                
                if existing:
                    # Yangilash
                    c.execute('''
                        UPDATE users 
                        SET full_name = %s, district = %s, age = %s, phone = %s, 
                            role = %s, rating = %s, password = %s
                        WHERE user_id = %s
                    ''', (full_name, district, age, phone, role, 
                          initial_rating, hashed_password, user_id))
                else:
                    # Yangi qo'shish
                    c.execute('''
                        INSERT INTO users 
                        (user_id, password, full_name, district, age, 
                         phone, role, rating, joined_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (user_id, hashed_password, full_name, district, age,
                          phone, role, initial_rating, datetime.now().date()))
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Qator {index + 2}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'import_excel', 
                  f"Excel import: {success_count} muvaffaqiyatli, {error_count} xato")
        
        return jsonify({
            'success': True,
            'message': f'{success_count} foydalanuvchi qo\'shildi/yangilandi',
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors[:10]  # Faqat birinchi 10 ta xatoni qaytaramiz
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Hisobotlarni export qilish:
@app.route('/api/admin/export_reports')
def api_export_reports():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                r.id as ReportID,
                r.user_id as UserID,
                u.full_name as FullName,
                u.district as District,
                r.month_year as MonthYear,
                r.event_count as Events,
                r.material_count as Materials,
                r.message_count as Messages,
                r.safety_score as SafetyScore,
                r.status as Status,
                r.submitted_date as SubmittedDate,
                rt.total as RatingScore,
                rt.admin_comment as AdminComment
            FROM reports r
            LEFT JOIN users u ON r.user_id = u.user_id
            LEFT JOIN ratings rt ON r.id = rt.report_id
            ORDER BY r.submitted_date DESC
        ''')
        
        reports = c.fetchall()
        columns = [desc[0] for desc in c.description]
        conn.close()
        
        # CSV yaratish
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(columns)
        writer.writerows(reports)
        
        output = BytesIO()
        output.write(si.getvalue().encode('utf-8'))
        output.seek(0)
        
        log_action(session['user_id'], 'export_reports', 'Hisobotlar eksport qilindi')
        
        return send_file(output, 
                        download_name='reports_export.csv',
                        as_attachment=True,
                        mimetype='text/csv')
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Reytinglarni export qilish:
@app.route('/api/admin/export_ratings')
def api_export_ratings():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                u.user_id as UserID,
                u.full_name as FullName,
                u.district as District,
                u.age as Age,
                u.role as Role,
                u.rating as CurrentRating,
                u.joined_date as JoinedDate,
                COUNT(r.id) as TotalReports,
                COUNT(CASE WHEN r.status = 'rated' THEN 1 END) as RatedReports,
                AVG(rt.total) as AverageRating
            FROM users u
            LEFT JOIN reports r ON u.user_id = r.user_id
            LEFT JOIN ratings rt ON r.id = rt.report_id
            GROUP BY u.user_id
            ORDER BY u.rating DESC
        ''')
        
        ratings = c.fetchall()
        columns = [desc[0] for desc in c.description]
        conn.close()
        
        # CSV yaratish
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(columns)
        writer.writerows(ratings)
        
        output = BytesIO()
        output.write(si.getvalue().encode('utf-8'))
        output.seek(0)
        
        log_action(session['user_id'], 'export_ratings', 'Reytinglar eksport qilindi')
        
        return send_file(output, 
                        download_name='ratings_export.csv',
                        as_attachment=True,
                        mimetype='text/csv')
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Test topshiriqlar yaratish - TUZATILGAN
@app.route('/api/admin/generate_test_tasks', methods=['POST'])
def generate_test_tasks():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    test_tasks = [
        ("Hududingizdagi yoshlar sonini aniqlang", "Hududingizdagi 18-35 yosh oralig'idagi yoshlar sonini hisoblang", "all", "2024-12-25", 5, "monthly"),
        ("Yoshlar muammolari haqida hisobot", "Hududingizdagi yoshlarning asosiy muammolari haqida 1 sahifalik hisobot tayyorlang", "all", "2024-12-20", 8, "regular"),
        ("Uchrashuv tashkil qilish", "Kamida 20 nafar yosh bilan uchrashuv o'tkazish", "all", "2024-12-18", 10, "urgent"),
        ("Ijtimoiy media hisobi", "Parlament ijtimoiy media hisobi uchun kontent tayyorlash", "all", "2024-12-22", 4, "regular"),
        ("O'quv dasturi taklifi", "Yoshlar uchun o'quv dasturi loyihasini ishlab chiqish", "all", "2024-12-30", 12, "monthly")
    ]
    
    try:
        conn = get_db()  # conn qo'shildi
        cursor = conn.cursor()  # cursor qo'shildi
        
        # tasks_new jadvalini yaratish
        cursor.execute('''CREATE TABLE IF NOT EXISTS tasks_new (
                            id SERIAL PRIMARY KEY,
                            title TEXT,
                            description TEXT,
                            assigned_to TEXT,
                            deadline DATE,
                            points INTEGER,
                            task_type TEXT,
                            status TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )''')
        
        for task in test_tasks:
            cursor.execute("""
                INSERT INTO tasks_new (title, description, assigned_to, deadline, points, task_type, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', CURRENT_TIMESTAMP)
            """, task)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Test topshiriqlar muvaffaqiyatli yaratildi',
            'count': len(test_tasks)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

## TOPSHIRIQNI O'CHIRISH - TO'LIQ TUZATILGAN VERSIYA
@app.route('/api/admin/delete_task/<task_id>', methods=['DELETE', 'POST', 'OPTIONS'])
def api_delete_task(task_id):
    """Topshiriqni o'chirish (DELETE va POST ikkalasini qabul qiladi)"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    # CORS uchun OPTIONS metodini qaytarish
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Avval topshiriq mavjudligini tekshirish
        c.execute("SELECT * FROM user_tasks WHERE task_id = %s", (task_id,))
        task = c.fetchone()
        
        if not task:
            return jsonify({'success': False, 'error': 'Topshiriq topilmadi'})
        
        # Admin/Debugger huquqlarini tekshirish
        if session.get('role') == 'debugger':
            # Debugger barcha topshiriqlarni o'chira oladi
            c.execute("DELETE FROM user_tasks WHERE task_id = %s", (task_id,))
        else:
            # Admin faqat o'zi yaratgan topshiriqlarni o'chira oladi
            c.execute("SELECT assigned_by FROM user_tasks WHERE task_id = %s", (task_id,))
            task_creator = c.fetchone()
            
            if not task_creator or task_creator[0] != session['user_id']:
                return jsonify({
                    'success': False, 
                    'error': 'Siz faqat o\'zingiz yaratgan topshiriqlarni o\'chira olasiz'
                })
            
            c.execute("DELETE FROM user_tasks WHERE task_id = %s AND assigned_by = %s", 
                     (task_id, session['user_id']))
        
        deleted_rows = conn.total_changes
        
        conn.commit()
        conn.close()
        
        if deleted_rows > 0:
            log_action(session['user_id'], 'delete_task', f"Topshiriq o'chirildi: {task_id}")
            return jsonify({
                'success': True,
                'message': 'Topshiriq muvaffaqiyatli o\'chirildi'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Topshiriqni o\'chirib bo\'lmadi'
            })
        
    except Exception as e:
        print(f"Topshiriq o'chirishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# TOPSHIRIQNI YANGILASH - TO'LIQ TUZATILGAN VERSIYA
@app.route('/api/admin/update_task/<task_id>', methods=['POST', 'PUT', 'OPTIONS'])
def api_update_task(task_id):
    """Topshiriqni yangilash (POST va PUT ikkalasini qabul qiladi)"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    # CORS uchun OPTIONS metodini qaytarish
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    try:
        # FormData yoki JSON tekshirish
        if request.content_type.startswith('multipart/form-data'):
            data = request.form
            file = request.files.get('file')
        else:
            data = request.json
            file = None
        
        # Ma'lumotlarni tekshirish
        if not data:
            return jsonify({'success': False, 'error': 'Ma\'lumotlar yo\'q'})
        
        conn = get_db()
        c = conn.cursor()
        
        # Avval topshiriq mavjudligini tekshirish
        c.execute("SELECT * FROM user_tasks WHERE task_id = %s", (task_id,))
        task = c.fetchone()
        
        if not task:
            return jsonify({'success': False, 'error': 'Topshiriq topilmadi'})
        
        # Faylni yuklash
        file_path = None
        if file and file.filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            filename = f"task_{timestamp}.{file_ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(file_path)
            file_path = filename
        
        # Yangilanadigan maydonlarni aniqlash
        update_fields = []
        update_values = []
        
        if 'title' in data:
            update_fields.append("title = %s")
            update_values.append(data['title'])
        
        if 'description' in data:
            update_fields.append("description = %s")
            update_values.append(data['description'])
        
        if 'assigned_to' in data:
            update_fields.append("assigned_to = %s")
            update_values.append(data['assigned_to'])
        
        if 'deadline' in data:
            update_fields.append("deadline = %s")
            update_values.append(data['deadline'])
        
        if 'points' in data:
            update_fields.append("points = %s")
            update_values.append(int(data['points']))
        
        if 'task_type' in data:
            update_fields.append("task_type = %s")
            update_values.append(data['task_type'])
        
        if 'priority' in data:
            update_fields.append("priority = %s")
            update_values.append(data['priority'])
        
        if 'status' in data:
            update_fields.append("status = %s")
            update_values.append(data['status'])
        
        if 'progress' in data:
            update_fields.append("progress = %s")
            update_values.append(data['progress'])
        
        if 'feedback' in data:
            update_fields.append("feedback = %s")
            update_values.append(data['feedback'])
        
        if 'rating_given' in data:
            update_fields.append("rating_given = %s")
            update_values.append(data['rating_given'])
        
        if file_path:
            update_fields.append("file_path = %s")
            update_values.append(file_path)
        
        if not update_fields:
            return jsonify({'success': False, 'error': 'Yangilanish uchun ma\'lumotlar yo\'q'})
        
        # Admin/Debugger huquqlarini tekshirish
        if session.get('role') == 'debugger':
            # Debugger barcha topshiriqlarni yangilay oladi
            query = f"UPDATE user_tasks SET {', '.join(update_fields)} WHERE task_id = %s"
            update_values.append(task_id)
            c.execute(query, update_values)
        else:
            # Admin faqat o'zi yaratgan topshiriqlarni yangilay oladi
            c.execute("SELECT assigned_by FROM user_tasks WHERE task_id = %s", (task_id,))
            task_creator = c.fetchone()
            
            if not task_creator or task_creator[0] != session['user_id']:
                return jsonify({
                    'success': False, 
                    'error': 'Siz faqat o\'zingiz yaratgan topshiriqlarni yangilay olasiz'
                })
            
            query = f"UPDATE user_tasks SET {', '.join(update_fields)} WHERE task_id = %s AND assigned_by = %s"
            update_values.extend([task_id, session['user_id']])
            c.execute(query, update_values)
        
        updated_rows = conn.total_changes
        
        conn.commit()
        conn.close()
        
        if updated_rows > 0:
            log_action(session['user_id'], 'update_task', 
                      f"Topshiriq yangilandi: {task_id}")
            return jsonify({
                'success': True,
                'message': 'Topshiriq muvaffaqiyatli yangilandi'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Topshiriqni yangilab bo\'lmadi'
            })
        
    except Exception as e:
        print(f"Topshiriq yangilashda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Hisobotlarni baholash (admin uchun)
@app.route('/api/admin/rate_report/<int:report_id>', methods=['POST'])
def api_rate_report(report_id):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        data = request.json
        
        # Baholash ma'lumotlari
        faollik = data.get('faollik', 0)
        tashabbus = data.get('tashabbus', 0)
        intizom = data.get('intizom', 0)
        tasir = data.get('tasir', 0)
        comment = data.get('comment', '')
        
        total = faollik + tashabbus + intizom + tasir
        
        conn = get_db()
        c = conn.cursor()
        
        # Baholashni saqlash
        c.execute('''INSERT INTO ratings 
                    (report_id, faollik, tashabbus, intizom, tasir, total, admin_comment) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                 (report_id, faollik, tashabbus, intizom, tasir, total, comment))
        
        # Hisobot holatini yangilash
        c.execute("UPDATE reports SET status = 'rated', admin_comment = %s WHERE id = %s", 
                 (comment, report_id))
        
        # Foydalanuvchi reytingini yangilash
        c.execute('''SELECT user_id FROM reports WHERE id = %s''', (report_id,))
        user_id = c.fetchone()[0]
        
        c.execute('''UPDATE users SET rating = rating + %s WHERE user_id = %s''', 
                 (total, user_id))
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'rate_report', 
                  f"Hisobot baholandi: {report_id} - ball: {total}")
        
        return jsonify({
            'success': True,
            'message': 'Hisobot muvaffaqiyatli baholandi'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Reyting statistikasi uchun API
@app.route('/api/admin/rating_stats')
def api_rating_stats():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # -------------------------------
        # UMUMIY STATISTIKA
        # -------------------------------
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
        total_users = c.fetchone()[0] or 0
        
        c.execute("SELECT AVG(rating) FROM users WHERE role = 'user'")
        avg_result = c.fetchone()[0]
        avg_rating = round(float(avg_result or 0), 1)
        
        c.execute("SELECT MAX(rating) FROM users WHERE role = 'user'")
        max_rating = c.fetchone()[0] or 0
        
        # -------------------------------
        # TOP 10 FOYDALANUVCHI
        # -------------------------------
        c.execute('''
            SELECT u.user_id, u.full_name, u.district, u.rating, u.joined_date,
                   COUNT(r.id) as report_count
            FROM users u
            LEFT JOIN reports r ON u.user_id = r.user_id
            WHERE u.role = 'user'
            GROUP BY u.user_id
            ORDER BY u.rating DESC
            LIMIT 10
        ''')
        
        top_users = []
        for row in c.fetchall():
            top_users.append({
                'user_id': row[0],
                'full_name': row[1],
                'district': row[2],
                'rating': row[3] or 0,
                'joined_date': row[4],
                'report_count': row[5] or 0
            })
        
        # -------------------------------
        # HUDUDLAR BO'YICHA STATISTIKA (olib tashlandi)
        # -------------------------------
        district_stats = []
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'avg_rating': avg_rating,
                'max_rating': max_rating
            },
            'top_users': top_users,
            'district_data': district_stats
        })
        
    except Exception as e:
        print(f"Reyting statistikasida xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/filter_ratings')
def filter_ratings():
    """Reytinglarni filtrlash"""
    try:
        district = request.args.get('district', 'all')
        level = request.args.get('level', 'all')
        sort = request.args.get('sort', 'rating_desc')
        
        # Baza so'rovi
        query = """
            SELECT 
                u.user_id,
                u.full_name,
                u.district,
                u.rating,
                u.joined_date,
                COUNT(r.id) as total_reports,
                SUM(CASE WHEN r.status = 'rated' THEN 1 ELSE 0 END) as rated_reports
            FROM users u
            LEFT JOIN reports r ON u.user_id = r.user_id
            WHERE u.role != 'debugger'
        """
        
        params = []
        
        # Hudud bo'yicha filtr
        if district != 'all':
            query += " AND u.district = %s"
            params.append(district)
        
        # Reyting darajasi bo'yicha filtr
        if level != 'all':
            if level == 'excellent':
                query += " AND u.rating >= 16"
            elif level == 'good':
                query += " AND u.rating BETWEEN 13 AND 15"
            elif level == 'average':
                query += " AND u.rating BETWEEN 10 AND 12"
            elif level == 'needs_improvement':
                query += " AND u.rating BETWEEN 7 AND 9"
            elif level == 'poor':
                query += " AND u.rating <= 6"
        
        query += " GROUP BY u.user_id"
        
        # Tartiblash
        if sort == 'rating_desc':
            query += " ORDER BY u.rating DESC"
        elif sort == 'rating_asc':
            query += " ORDER BY u.rating ASC"
        elif sort == 'name_asc':
            query += " ORDER BY u.full_name ASC"
        elif sort == 'name_desc':
            query += " ORDER BY u.full_name DESC"
        elif sort == 'reports_desc':
            query += " ORDER BY total_reports DESC"
        
        cursor.execute(query, params)
        users = cursor.fetchall()
        
        users_list = []
        for user in users:
            users_list.append({
                'user_id': user[0],
                'full_name': user[1],
                'district': get_region_name(user[2]) if get_region_name(user[2]) else user[2],
                'rating': user[3] or 0,
                'joined_date': user[4],
                'total_reports': user[5] or 0,
                'rated_reports': user[6] or 0
            })
        
        # Statistikani hisoblash
        if users_list:
            total_users = len(users_list)
            avg_rating = round(sum(u['rating'] for u in users_list) / total_users, 1)
            max_rating = max(u['rating'] for u in users_list)
            active_users = sum(1 for u in users_list if u['rating'] >= 10)
        else:
            total_users = avg_rating = max_rating = active_users = 0
        
        stats = {
            'total_users': total_users,
            'avg_rating': avg_rating,
            'max_rating': max_rating,
            'active_users': active_users
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'users': users_list
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/tasks_list')
def api_tasks_list():
    """Topshiriqlar ro'yxati API"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # 1. Statistikalar
        c.execute("SELECT COUNT(*) FROM user_tasks")
        total_tasks = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM user_tasks WHERE status = 'completed'")
        completed_tasks = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM user_tasks WHERE status IN ('pending', 'in_progress')")
        pending_tasks = c.fetchone()[0] or 0
        
        # Muddati o'tgan topshiriqlar
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute('''
            SELECT COUNT(*) FROM user_tasks 
            WHERE deadline < %s AND status NOT IN ('completed', 'cancelled')
        ''', (today,))
        overdue_tasks = c.fetchone()[0] or 0
        
        # 2. Topshiriqlar ro'yxati
        c.execute('''
            SELECT 
                ut.task_id,
                ut.title,
                ut.description,
                ut.assigned_to,
                CASE 
                    WHEN ut.assigned_to = 'all' THEN 'Barcha'
                    ELSE u.full_name 
                END as assignee_name,
                ut.deadline,
                ut.points,
                ut.status,
                ut.priority,
                ut.created_at,
                admin_u.full_name as admin_name
            FROM user_tasks ut
            LEFT JOIN users u ON ut.assigned_to = u.user_id
            LEFT JOIN users admin_u ON ut.assigned_by = admin_u.user_id
            ORDER BY 
                CASE ut.priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END,
                ut.deadline ASC
        ''')
        
        tasks = []
        rows = c.fetchall()
        for row in rows:
            deadline = row[5]
            deadline_formatted = None
            if deadline:
                try:
                    deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
                    deadline_formatted = deadline_date.strftime('%d.%m.%Y')
                except:
                    deadline_formatted = deadline
            
            tasks.append({
                'task_id': row[0],
                'title': row[1],
                'description': row[2],
                'assigned_to': row[3],
                'assignee_name': row[4],
                'deadline': row[5],
                'deadline_formatted': deadline_formatted,
                'points': row[6] or 0,
                'status': row[7] or 'pending',
                'priority': row[8] or 'medium',
                'created_at': row[9],
                'admin_name': row[10]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'pending_tasks': pending_tasks,
                'overdue_tasks': overdue_tasks
            },
            'tasks': tasks
        })
        
    except Exception as e:
        print(f"Topshiriqlarni olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/filter_tasks')
def filter_tasks():
    """Topshiriqlarni filtrlash"""
    try:
        status = request.args.get('status', 'all')
        assignee = request.args.get('assignee', 'all')
        deadline = request.args.get('deadline', 'all')
        
        # Baza so'rovi
        query = """
            SELECT 
                t.task_id,
                t.title,
                t.description,
                t.assigned_to,
                u.full_name as assignee_name,
                t.deadline,
                t.points,
                t.status,
                t.priority,
                t.created_at,
                a.full_name as admin_name
            FROM user_tasks t
            LEFT JOIN users u ON t.assigned_to = u.user_id
            LEFT JOIN users a ON t.assigned_by = a.user_id
            WHERE 1=1
        """
        
        params = []
        
        # Holat bo'yicha filtr
        if status != 'all':
            query += " AND t.status = %s"
            params.append(status)
        
        # Muddat bo'yicha filtr
        if deadline != 'all':
            today = datetime.now().date()
            if deadline == 'today':
                query += " AND DATE(t.deadline) = DATE(%s)"
                params.append(today)
            elif deadline == 'week':
                query += " AND t.deadline BETWEEN DATE(%s) AND DATE(%s, '+7 days')"
                params.append(today)
                params.append(today)
            elif deadline == 'month':
                query += " AND t.deadline BETWEEN DATE(%s) AND DATE(%s, '+30 days')"
                params.append(today)
                params.append(today)
            elif deadline == 'overdue':
                query += " AND t.deadline < DATE(%s) AND t.status NOT IN ('completed', 'cancelled')"
                params.append(today)
        
        query += " ORDER BY t.deadline ASC"
        
        cursor.execute(query, params)
        tasks = cursor.fetchall()
        
        tasks_list = []
        for task in tasks:
            tasks_list.append({
                'task_id': task[0],
                'title': task[1],
                'description': task[2],
                'assigned_to': task[3],
                'assignee_name': task[4] or 'Barcha foydalanuvchilar',
                'deadline': task[5],
                'points': task[6] or 0,
                'status': task[7] or 'pending',
                'priority': task[8] or 'medium',
                'created_at': task[9],
                'admin_name': task[10] or 'Sistema'
            })
        
        # Statistikani hisoblash
        total_tasks = len(tasks_list)
        completed_tasks = sum(1 for t in tasks_list if t['status'] == 'completed')
        pending_tasks = sum(1 for t in tasks_list if t['status'] == 'pending')
        
        # Muddati o'tgan topshiriqlar
        today = datetime.now().date()
        overdue_tasks = sum(1 for t in tasks_list 
                          if t['deadline'] and 
                          datetime.strptime(t['deadline'], '%Y-%m-%d').date() < today and 
                          t['status'] not in ['completed', 'cancelled'])
        
        stats = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_tasks': pending_tasks,
            'overdue_tasks': overdue_tasks
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'tasks': tasks_list
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/get_task/<task_id>', methods=['GET'])
@role_required(['admin', 'debugger'])
def get_single_task(task_id):
    """Bitta topshiriqni olish"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(f"DEBUG: get_task endpoint - task_id: {task_id}")
        
        # Avval ID raqami bo'yicha qidirish
        cursor.execute('''
            SELECT t.*, u.full_name as assignee_name, a.full_name as admin_name
            FROM user_tasks t
            LEFT JOIN users u ON t.assigned_to = u.user_id
            LEFT JOIN users a ON t.assigned_by = a.user_id
            WHERE t.id = %s
        ''', (task_id,))
        
        task = cursor.fetchone()
        
        # Agar topilmasa, task_id bo'yicha qidirish
        if not task:
            cursor.execute('''
                SELECT t.*, u.full_name as assignee_name, a.full_name as admin_name
                FROM user_tasks t
                LEFT JOIN users u ON t.assigned_to = u.user_id
                LEFT JOIN users a ON t.assigned_by = a.user_id
                WHERE t.task_id = %s
            ''', (task_id,))
            task = cursor.fetchone()
        
        conn.close()
        
        if not task:
            print(f"DEBUG: Topshiriq topilmadi - {task_id}")
            return jsonify({'success': False, 'error': 'Topshiriq topilmadi'}), 404
        
        # Formatlash
        task_dict = {
            'id': task[0],
            'task_id': task[1],
            'title': task[2],
            'description': task[3],
            'assigned_to': task[4],
            'deadline': task[5],
            'points': task[6],
            'task_type': task[7],
            'priority': task[8],
            'status': task[9],
            'assigned_by': task[10],
            'created_at': task[11],
            'assignee_name': task[12] if len(task) > 12 else '',
            'admin_name': task[13] if len(task) > 13 else ''
        }
        
        print(f"DEBUG: Topshiriq topildi - {task_dict['title']}")
        return jsonify({'success': True, 'task': task_dict})
        
    except Exception as e:
        print(f"ERROR: get_task endpointida xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# debugger.html da ishlatilgan, lekin app.py da yo'q:
@app.route('/api/admin/get_tasks/<task_id>')  # TOPSHIRIQNI OLISH (ID bo'yicha)
def api_get_task_by_id(task_id):
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        c.execute('''
            SELECT ut.*, 
                   u.full_name as admin_name,
                   CASE 
                       WHEN ut.assigned_to = 'all' THEN 'Barcha'
                       ELSE u2.full_name 
                   END as assignee_name
            FROM user_tasks ut
            LEFT JOIN users u ON ut.assigned_by = u.user_id
            LEFT JOIN users u2 ON ut.assigned_to = u2.user_id
            WHERE ut.task_id = %s
        ''', (task_id,))
        
        task = c.fetchone()
        conn.close()
        
        if not task:
            return jsonify({'success': False, 'error': 'Topshiriq topilmadi'})
        
        # Kolonka nomlari bilan formatlash
        columns = [desc[0] for desc in c.description]
        task_dict = {}
        for i, col in enumerate(columns):
            task_dict[col] = task[i]
        
        return jsonify({'success': True, 'task': task_dict})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# debugger.html da ishlatilgan, lekin app.py da yo'q:
# Barcha hisobotlarni olish endpointi
@app.route('/api/admin/get_reports')
def api_get_reports():
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                r.*,
                u.full_name,
                u.district,
                u.age,
                rt.faollik,
                rt.tashabbus,
                rt.intizom,
                rt.tasir,
                rt.total,
                rt.admin_comment as rating_comment
            FROM reports r
            LEFT JOIN users u ON r.user_id = u.user_id
            LEFT JOIN ratings rt ON r.id = rt.report_id
            ORDER BY r.submitted_date DESC
        ''')
        
        reports = c.fetchall()
        conn.close()
        
        # Ma'lumotlarni formatlash
        reports_list = []
        for report in reports:
            report_dict = {
                'id': report[0],
                'user_id': report[1],
                'month_year': report[2],
                'event_count': report[3],
                'material_count': report[4],
                'message_count': report[5],
                'safety_score': report[6],
                'file_path': report[7],
                'description': report[8],
                'challenges': report[9],
                'suggestions': report[10],
                'status': report[11],
                'admin_comment': report[12],
                'submitted_date': report[13],
                'full_name': report[14],
                'district': report[15],
                'age': report[16],
                'faollik': report[17],
                'tashabbus': report[18],
                'intizom': report[19],
                'tasir': report[20],
                'total': report[21],
                'rating_comment': report[22]
            }
            reports_list.append(report_dict)
        
        return jsonify({
            'success': True,
            'reports': reports_list,
            'count': len(reports_list)
        })
        
    except Exception as e:
        print(f"Hisobotlarni olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Hisobotni ko'rish (viewReport) uchun:
@app.route('/api/admin/view_report/<int:report_id>')
def api_view_report(report_id):
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                r.*, 
                u.full_name,
                u.district,
                u.age,
                rt.faollik,
                rt.tashabbus,
                rt.intizom,
                rt.tasir,
                rt.total,
                rt.admin_comment as rating_comment
            FROM reports r
            LEFT JOIN users u ON r.user_id = u.user_id
            LEFT JOIN ratings rt ON r.id = rt.report_id
            WHERE r.id = %s
        ''', (report_id,))
        
        report = c.fetchone()
        conn.close()
        
        if not report:
            return jsonify({'success': False, 'error': 'Hisobot topilmadi'})
        
        # Ma'lumotlarni formatlash
        report_dict = {
            'id': report[0],
            'user_id': report[1],
            'month_year': report[2],
            'event_count': report[3],
            'material_count': report[4],
            'message_count': report[5],
            'safety_score': report[6],
            'file_path': report[7],
            'description': report[8],
            'challenges': report[9],
            'suggestions': report[10],
            'status': report[11],
            'admin_comment': report[12],
            'submitted_date': report[13],
            'full_name': report[14],
            'district': report[15],
            'age': report[16],
            'faollik': report[17],
            'tashabbus': report[18],
            'intizom': report[19],
            'tasir': report[20],
            'total': report[21],
            'rating_comment': report[22]
        }
        
        return jsonify({
            'success': True,
            'report': report_dict
        })
        
    except Exception as e:
        print(f"Hisobot ko'rishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})


# Hisobotni tasdiqlash (approveReport) uchun:
@app.route('/api/admin/approve_report/<int:report_id>', methods=['POST'])
def api_approve_report(report_id):
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Hisobot holatini yangilash
        c.execute("UPDATE reports SET status = 'approved' WHERE id = %s", (report_id,))
        
        # Foydalanuvchi reytingini yangilash (+5 ball)
        c.execute('''
            UPDATE users 
            SET rating = rating + 5 
            WHERE user_id = (SELECT user_id FROM reports WHERE id = %s)
        ''', (report_id,))
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'approve_report', 
                  f"Hisobot tasdiqlandi: {report_id}")
        
        return jsonify({
            'success': True,
            'message': 'Hisobot tasdiqlandi va foydalanuvchi reytingi oshirildi'
        })
        
    except Exception as e:
        print(f"Hisobot tasdiqlashda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Hisobotni rad etish (rejectReport) uchun:
@app.route('/api/admin/reject_report/<int:report_id>', methods=['POST'])
def api_reject_report(report_id):
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        data = request.json
        comment = data.get('comment', '')
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute("UPDATE reports SET status = 'rejected', admin_comment = %s WHERE id = %s", 
                 (comment, report_id))
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'reject_report', 
                  f"Hisobot rad etildi: {report_id}")
        
        return jsonify({
            'success': True,
            'message': 'Hisobot rad etildi'
        })
        
    except Exception as e:
        print(f"Hisobot rad etishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Barcha topshiriqlarni olish (admin/debugger uchun)
# @app.route('/api/admin/get_tasks', methods=['GET'])
# def api_get_tasks():
#     """Barcha topshiriqlarni olish (rolga qarab filtr)"""
#     if session.get('role') not in ['admin', 'debugger']:
#         return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
#     try:
#         conn = get_db()
#         c = conn.cursor()
        
#         # Agar debugger bo'lsa, barcha topshiriqlar
#         if session.get('role') == 'debugger':
#             query = '''SELECT 
#                         ut.*,
#                         u.full_name as admin_name,
#                         CASE 
#                             WHEN ut.assigned_to = 'all' THEN 'Barcha'
#                             ELSE u2.full_name 
#                         END as assignee_name
#                      FROM user_tasks ut
#                      LEFT JOIN users u ON ut.assigned_by = u.user_id
#                      LEFT JOIN users u2 ON ut.assigned_to = u2.user_id
#                      ORDER BY ut.created_at DESC'''
#         else:
#             # Agar admin bo'lsa, faqat o'zi yaratgan topshiriqlar
#             query = '''SELECT 
#                         ut.*,
#                         u.full_name as admin_name,
#                         CASE 
#                             WHEN ut.assigned_to = 'all' THEN 'Barcha'
#                             ELSE u2.full_name 
#                         END as assignee_name
#                      FROM user_tasks ut
#                      LEFT JOIN users u ON ut.assigned_by = u.user_id
#                      LEFT JOIN users u2 ON ut.assigned_to = u2.user_id
#                      WHERE ut.assigned_by = ?
#                      ORDER BY ut.created_at DESC'''
        
#         if session.get('role') == 'debugger':
#             c.execute(query)
#         else:
#             c.execute(query, (session['user_id'],))
        
#         tasks = c.fetchall()
        
#         # Kolonka nomlari
#         columns = [desc[0] for desc in c.description]
        
#         conn.close()
        
#         # Formatlash
#         tasks_list = []
#         for task in tasks:
#             task_dict = {}
#             for i, col in enumerate(columns):
#                 task_dict[col] = task[i]
            
#             # Holat ranglari
#             status_colors = {
#                 'pending': '#f59e0b',
#                 'in_progress': '#3b82f6', 
#                 'completed': '#10b981',
#                 'cancelled': '#ef4444'
#             }
#             task_dict['status_color'] = status_colors.get(task_dict.get('status', 'pending'), '#6b7280')
            
#             tasks_list.append(task_dict)
        
#         return jsonify({
#             'success': True,
#             'tasks': tasks_list,
#             'total': len(tasks_list)
#         })
        
#     except Exception as e:
#         print(f"Topshiriqlarni olishda xatolik: {e}")
#         return jsonify({'success': False, 'error': str(e)})

# DEBUGGER PANEL funksiyasini to'g'rilash:
@app.route('/debugger')
def debugger():
    # Avval login tekshirish
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Debugger rolini tekshirish
    if session.get('role') != 'debugger':
        flash('Sizda super admin huquqi yo\'q!')
        return redirect(url_for('dashboard'))
    
    conn = get_db()
    c = conn.cursor()
    
    # Oddiy va ishonchli querylar
    # 1. Foydalanuvchilar soni
    c.execute("SELECT COUNT(*) FROM users")
    user_count = c.fetchone()[0]
    
    # 2. Hisobotlar soni
    c.execute("SELECT COUNT(*) FROM reports")
    report_count_result = c.fetchone()
    report_count = report_count_result[0] if report_count_result else 0
    
    # 3. Kutilayotgan hisobotlar
    c.execute("SELECT COUNT(*) FROM reports WHERE status = 'pending'")
    pending_result = c.fetchone()
    pending_reports = pending_result[0] if pending_result else 0
    
    # 4. Topshiriqlar soni
    try:
        c.execute("SELECT COUNT(*) FROM user_tasks")
        task_count_result = c.fetchone()
        task_count = task_count_result[0] if task_count_result else 0
    except:
        task_count = 0
    
    # 5. Aktiv foydalanuvchilar
    try:
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("SELECT COUNT(*) FROM users WHERE last_login IS NOT NULL AND last_login > %s", (seven_days_ago,))
        active_users_result = c.fetchone()
        active_users = active_users_result[0] if active_users_result else 0
    except:
        active_users = 0
    
    # 6. Barcha foydalanuvchilar
    c.execute("SELECT * FROM users ORDER BY id")
    all_users = c.fetchall()
    
    # 7. Sistem loglari
    try:
        c.execute('''SELECT 
                        strftime('%Y-%m-%d %H:%M', timestamp) as time,
                        user_id,
                        action,
                        details
                     FROM system_logs 
                     ORDER BY timestamp DESC 
                     LIMIT 20''')
        recent_logs = c.fetchall()
    except:
        recent_logs = []
    
    conn.close()
    
    # Debug uchun console ga chiqaramiz
    print(f"DEBUGGER: user_count={user_count}, report_count={report_count}, pending_reports={pending_reports}, task_count={task_count}")
    print(f"DEBUGGER: users count: {len(all_users)}")
    
    return render_template('debugger.html',
                         user_count=user_count,
                         report_count=report_count,
                         pending_reports=pending_reports,
                         task_count=task_count,
                         active_users=active_users,
                         all_users=all_users,
                         recent_logs=recent_logs)
                         
# Yordamchi funksiyalar

def get_db_connection():
    """Baza ulanishini olish"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    return conn

def get_all_users():
    """Barcha foydalanuvchilarni olish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY id")
    users = cursor.fetchall()
    conn.close()
    return users

def get_all_reports():
    """Barcha hisobotlarni olish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports ORDER BY submitted_date DESC")
    reports = cursor.fetchall()
    conn.close()
    return reports

def get_all_tasks():
    """Barcha topshiriqlarni olish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_tasks ORDER BY created_date DESC")
    tasks = cursor.fetchall()
    conn.close()
    return tasks

def get_recent_logs(limit=10):
    """Sistem loglarini olish"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, user_id, action, details 
            FROM system_logs 
            ORDER BY timestamp DESC 
            LIMIT %s
        ''', (limit,))
        logs = cursor.fetchall()
        conn.close()
        return logs
    except:
        # Agar system_logs jadvali mavjud bo'lmasa
        return []

def is_user_active(user_id):
    """Foydalanuvchi aktivligini tekshirish"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT last_login FROM users WHERE id = %s', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            from datetime import datetime, timedelta
            thirty_days_ago = datetime.now() - timedelta(days=30)
            last_login = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            return last_login > thirty_days_ago
        return False
    except:
        return False

        
@app.route('/set_password', methods=['GET', 'POST'])
def set_password():
    if request.method == 'POST':
        user_id = request.form['user_id']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('Parollar mos kelmadi!')
            return render_template('set_password.html', user_id=user_id)
        
        hashed_pw = generate_password_hash(new_password)
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET password = %s WHERE user_id = %s", (hashed_pw, user_id))
        conn.commit()
        conn.close()
        
        flash('Parol muvaffaqiyatli o\'rnatildi! Iltimos, tizimga kiring.')
        return redirect(url_for('login'))
    
    user_id = request.args.get('user_id', '')
    return render_template('set_password.html', user_id=user_id)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    c = conn.cursor()
    
    # Foydalanuvchi ma'lumotlari
    c.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
    user = c.fetchone()
    
    # Baholash tarixi
    c.execute('''SELECT r.*, rt.total, rt.admin_comment 
                 FROM reports r 
                 LEFT JOIN ratings rt ON r.id = rt.report_id 
                 WHERE r.user_id = %s 
                 ORDER BY r.submitted_date DESC''', (session['user_id'],))
    reports_history = c.fetchall()
    
    conn.close()
    
    return render_template('profile.html', user=user, reports=reports_history)

# @app.route('/reports_history')
# def reports_history():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
    
#     conn = get_db()
#     c = conn.cursor()
    
#     c.execute('''SELECT r.*, rt.total, rt.admin_comment, 
#                  rt.faollik, rt.tashabbus, rt.intizom, rt.tasir
#                  FROM reports r 
#                  LEFT JOIN ratings rt ON r.id = rt.report_id 
#                  WHERE r.user_id = %s 
#                  ORDER BY r.submitted_date DESC''', (session['user_id'],))
#     reports = c.fetchall()
    
#     conn.close()
    
#     return render_template('reports_history.html', reports=reports)

@app.route('/tasks')
def tasks_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM user_tasks ORDER BY created_date DESC")
    tasks = c.fetchall()
    
    conn.close()
    
    return render_template('tasks.html', tasks=tasks)

@app.route('/download/<filename>')
def download_file(filename):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Fayl nomini to'g'rilash
    safe_filename = secure_filename(filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    
    if os.path.exists(file_path):
        # Ruxsatni tekshirish
        conn = get_db()
        c = conn.cursor()
        
        # Task fayllarini tekshirish (birinchi)
        c.execute("SELECT assigned_to, assigned_by FROM user_tasks WHERE file_path = %s", (safe_filename,))
        task = c.fetchone()
        
        if task:
            # User yoki admin/debugger ruxsati
            if task[0] == session['user_id'] or task[1] == session['user_id'] or session.get('role') in ['admin', 'debugger']:
                conn.close()
                return send_file(file_path, as_attachment=True)
        
        # Fayl nomini bazada qidirish (reports)
        c.execute("SELECT user_id FROM reports WHERE file_path = %s", (safe_filename,))
        report = c.fetchone()
        
        # Agar fayl bazada topilmasa, boshqa fayllarni tekshirish
        if not report:
            c.execute("SELECT user_id FROM reports WHERE file_path LIKE %s", (f'%{safe_filename}%',))
            report = c.fetchone()
        
        conn.close()
        
        # Ruxsatni tekshirish
        if report:
            if report[0] == session['user_id'] or session.get('role') in ['admin', 'debugger']:
                return send_file(file_path, as_attachment=True)
            else:
                flash('Faylga kirish huquqingiz yoʻq!', 'danger')
        else:
            # Agar bazada topilmasa, lekin fayl mavjud bo'lsa
            if session.get('role') in ['admin', 'debugger']:
                return send_file(file_path, as_attachment=True)
            else:
                flash('Faylga kirish huquqingiz yoʻq!', 'danger')
    else:
        flash('Fayl topilmadi!', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# Flask routes for Super Admin

@app.route('/superadmin')
def superadmin():
    if session.get('role') != 'debugger':
        return redirect('/dashboard')
    
    # Statistik ma'lumotlarni olish
    user_count = len(get_all_users())
    report_count = len(get_all_reports())
    pending_reports = len([r for r in get_all_reports() if r[8] == 'pending'])
    task_count = len(get_all_tasks())
    active_users = len([u for u in get_all_users() if is_user_active(u[1])])
    
    return render_template('superadmin.html',
                         user_count=user_count,
                         report_count=report_count,
                         pending_reports=pending_reports,
                         task_count=task_count,
                         active_users=active_users,
                         all_users=get_all_users(),
                         regions=get_regions())

# API ADD_USER funksiyasini to'g'rilash:
@app.route('/api/admin/add_user', methods=['POST'])
def api_add_user():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
    
    try:
        data = request.get_json()
        
        user_id = data.get('user_id') or data.get('id')
        full_name = data.get('full_name')
        district = data.get('district')
        age = data.get('age')
        phone = data.get('phone', '')
        role = data.get('role', 'user')
        initial_rating = data.get('initial_rating', 10)
        password = data.get('password')
        
        # ID formatini tekshirish
        if not re.match(r'^\d{4}$', user_id):
            return jsonify({'success': False, 'error': 'ID 4 ta raqamdan iborat bo\'lishi kerak'}), 400
        
        conn = get_db()
        c = conn.cursor()
        
        # Mavjudligini tekshirish
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if c.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': f'Bu ID ({user_id}) allaqachon mavjud'}), 400
        
        # Parolni hash qilish
        hashed_password = generate_password_hash(password)
        
        # Foydalanuvchini qo'shish
        c.execute('''
            INSERT INTO users 
            (user_id, password, full_name, district, age, role, rating, phone, joined_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE)
        ''', (user_id, hashed_password, full_name, district, age, role, initial_rating, phone))
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'add_user', f"Yangi foydalanuvchi: {user_id} - {full_name}")
        
        return jsonify({
            'success': True,
            'message': f'Foydalanuvchi {user_id} muvaffaqiyatli qo\'shildi',
            'user_id': user_id
        })
        
    except Exception as e:
        print(f"Xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/import_excel', methods=['POST'])
def api_import_excel():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Fayl topilmadi'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Fayl tanlanmagan'})
    
    try:
        # Faylni o'qish
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)
        elif file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            return jsonify({'success': False, 'error': 'Faqat .xlsx yoki .csv fayllar qabul qilinadi'})
        
        # Sozlamalar
        update_existing = request.form.get('update_existing', 'true') == 'true'
        skip_duplicates = request.form.get('skip_duplicates', 'true') == 'true'
        
        conn = get_db()
        c = conn.cursor()
        
        added = 0
        updated = 0
        skipped = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                row_num = index + 1
                
                # Excel ID ni olish
                excel_id = str(row['ID']).strip()
                if not excel_id.isdigit():
                    errors.append(f"Qator {row_num}: ID raqam emas")
                    skipped += 1
                    continue
                
                user_id = excel_id.zfill(4)
                full_name = str(row['FullName']).strip()
                district = str(row['District']).strip()
                age = int(row['Age'])
                phone = str(row.get('Phone', '')).strip()
                role = str(row['Role']).strip().lower()
                initial_rating = int(row['InitialRating'])
                
                # Mavjudligini tekshirish
                c.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
                existing = c.fetchone()
                
                if existing:
                    if skip_duplicates:
                        skipped += 1
                        continue
                    
                    if update_existing:
                        # Yangilash
                        c.execute('''
                            UPDATE users 
                            SET full_name=%s, district=%s, age=%s, phone=%s, role=%s, rating=%s
                            WHERE user_id=%s
                        ''', (full_name, district, age, phone, role, initial_rating, user_id))
                        updated += 1
                else:
                    # Yangi qo'shish
                    password = generate_random_password()
                    hashed_password = generate_password_hash(password)
                    
                    c.execute('''
                        INSERT INTO users 
                        (user_id, password, full_name, district, age, phone, role, rating, joined_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE)
                    ''', (user_id, hashed_password, full_name, district, age, phone, role, initial_rating))
                    added += 1
                
            except Exception as e:
                errors.append(f"Qator {row_num}: {str(e)}")
                skipped += 1
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'import_excel', f'Import: {added} qoshildi, {updated} yangilandi, {skipped} otkazildi')
        
        return jsonify({
            'success': True,
            'message': f'Import yakunlandi! Qo\'shildi: {added}, Yangilandi: {updated}, O\'tkazib yuborildi: {skipped}',
            'added': added,
            'updated': updated,
            'skipped': skipped,
            'errors': errors[:5]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
        
# namuna exel shablonini yuklash
@app.route('/api/admin/download_template')
def api_download_template():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        # Excel shablon yaratish
        import pandas as pd
        from io import BytesIO
        
        # Namuna ma'lumotlar
        sample_data = [
            {
                'ID': '0001',
                'FullName': 'Ali Valiyev',
                'District': '01',  # Toshkent shahri
                'Age': 22,
                'Phone': '+998901234567',  # ixtiyoriy
                'Role': 'user',
                'InitialRating': 10
            },
            {
                'ID': '0002', 
                'FullName': 'Malika Karimova',
                'District': '02',  # Toshkent viloyati
                'Age': 24,
                'Phone': '',
                'Role': 'user',
                'InitialRating': 10
            }
        ]
        
        df = pd.DataFrame(sample_data)
        
        # Excel fayl yaratish
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Foydalanuvchilar', index=False)
            
            # Ko'rsatmalar uchun alohida sheet
            instructions = pd.DataFrame({
                'Maydon': ['ID', 'FullName', 'District', 'Age', 'Phone', 'Role', 'InitialRating'],
                'Tavsif': [
                    '4 ta raqam (masalan: 0001, 0123)',
                    'To\'liq ismi',
                    'Hudud raqami (01-14)',
                    'Yosh (18-35)',
                    'Telefon raqami (ixtiyoriy)',
                    'user/admin/debugger',
                    'Boshlang\'ich reyting (0-20)'
                ],
                'Namuna': ['0001', 'Ali Valiyev', '01', '22', '+998901234567', 'user', '10']
            })
            instructions.to_excel(writer, sheet_name='Ko\'rsatmalar', index=False)
        
        output.seek(0)
        
        return send_file(
            output,
            download_name='foydalanuvchi_import_shabloni.xlsx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"Shablon yuklashda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
        
# OPTIMIZE_DATABASE funksiyasini to'g'rilash:
@app.route('/api/admin/optimize_database', methods=['POST'])
def api_optimize_database():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()  # c o'zgaruvchisini aniqlaymiz
        
        # Oldin bazaning hajmini olamiz
        c.execute("PRAGMA page_size")
        page_size = c.fetchone()[0]
        
        c.execute("PRAGMA page_count")
        old_page_count = c.fetchone()[0]
        old_size = (page_size * old_page_count) / 1024  # KB da
        
        # VACUUM komandasi - SQLite da bazani optimizatsiya qilish
        c.execute('VACUUM')
        
        # Yangi hajmini olamiz
        c.execute("PRAGMA page_count")
        new_page_count = c.fetchone()[0]
        new_size = (page_size * new_page_count) / 1024  # KB da
        
        saved_space = old_size - new_size
        
        conn.commit()
        conn.close()
        
        # Log yozish
        log_action(session['user_id'], 'optimize_database', 
                  f'Baza optimizatsiya qilindi. {saved_space:.2f} KB bo\'sh joy')
        
        return jsonify({
            'success': True, 
            'message': f'Baza muvaffaqiyatli optimizatsiya qilindi!',
            'saved_space': round(saved_space, 2),
            'new_size': round(new_size, 2)
        })
        
    except Exception as e:
        print(f"Baza optimizatsiyasida xatolik: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/vacuum_database', methods=['POST'])
def vacuum_database():
    """Bazani tozalash (VACUUM)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # SQLite uchun VACUUM
        cursor.execute("VACUUM;")
        
        conn.commit()
        conn.close()
        
        # Log yozish
        log_action('debugger', 'vacuum_database', 'Database vacuumed')
        
        return jsonify({
            'success': True,
            'message': 'Database vacuum completed successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/admin/database_stats')
def api_database_stats():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Asosiy statistikalar
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM reports")
        total_reports = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM reports WHERE status = 'pending'")
        pending_reports_result = c.fetchone()
        pending_reports = pending_reports_result[0] if pending_reports_result else 0
        
        c.execute("SELECT COUNT(*) FROM user_tasks")
        total_tasks = c.fetchone()[0]
        
        # Faol foydalanuvchilar (oxirgi 7 kunda)
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("SELECT COUNT(*) FROM users WHERE last_login IS NOT NULL AND last_login > %s", (seven_days_ago,))
        active_users_result = c.fetchone()
        active_users = active_users_result[0] if active_users_result else 0
        
        # Baza hajmi
        try:
            c.execute("PRAGMA page_size")
            page_size = c.fetchone()[0]
            
            c.execute("PRAGMA page_count")
            page_count = c.fetchone()[0]
            
            database_size_kb = (page_size * page_count) / 1024
        except:
            database_size_kb = 0
        
        # Oxirgi optimizatsiya vaqtini olish
        try:
            c.execute("SELECT timestamp FROM system_logs WHERE action = 'optimize_database' ORDER BY timestamp DESC LIMIT 1")
            last_optimized = c.fetchone()
            if last_optimized:
                last_optimized = last_optimized[0]
            else:
                last_optimized = 'Hech qachon'
        except:
            last_optimized = 'Ma\'lumot yo\'q'
        
        # Hududlar bo'yicha statistikalar
        c.execute("SELECT district, COUNT(*) FROM users GROUP BY district")
        district_stats = c.fetchall()
        
        # Rol bo'yicha statistikalar
        c.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
        role_stats = c.fetchall()
        
        conn.close()
        
        # Grafiklar uchun ma'lumotlar
        district_chart_data = []
        for district, count in district_stats:
            if district:
                district_name = get_regions().get(district, f"Hudud {district}")
                district_chart_data.append({
                    'name': district_name,
                    'value': count
                })
        
        role_chart_data = []
        for role, count in role_stats:
            role_name = 'Foydalanuvchi' if role == 'user' else 'Admin' if role == 'admin' else 'Super Admin'
            role_chart_data.append({
                'name': role_name,
                'value': count
            })
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'total_reports': total_reports,
                'pending_reports': pending_reports,
                'total_tasks': total_tasks,
                'active_users': active_users,
                'database_size_kb': round(database_size_kb, 2),
                'last_optimized': last_optimized,
                'district_chart': district_chart_data,
                'role_chart': role_chart_data
            }
        })
        
    except Exception as e:
        print(f"Statistika olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/delete_user/<user_id>', methods=['POST'])
def api_delete_user(user_id):
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Foydalanuvchi mavjudligini tekshirish
        c.execute("SELECT full_name FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'Foydalanuvchi topilmadi'})
        
        # Foydalanuvchini o'chirish
        c.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        
        # Uning hisobotlarini ham o'chirish (ixtiyoriy)
        # c.execute("DELETE FROM reports WHERE user_id = %s", (user_id,))
        
        conn.commit()
        conn.close()
        
        # Log yozish
        log_action(session['user_id'], 'delete_user', f"Foydalanuvchi o'chirildi: {user_id}")
        
        return jsonify({
            'success': True,
            'message': f"Foydalanuvchi {user_id} muvaffaqiyatli o'chirildi"
        })
        
    except Exception as e:
        print(f"Foydalanuvchi o'chirishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/reset_password/<user_id>', methods=['POST'])
def api_reset_password(user_id):
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        # Yangi parol generatsiya qilish
        # generate_random_password funksiyasini aniqlaymiz:
        def generate_random_password_local(length=8):
            chars = string.ascii_letters + string.digits
            return ''.join(random.choice(chars) for _ in range(length))
        
        new_password = generate_random_password_local()
        hashed_password = generate_password_hash(new_password)
        
        conn = get_db()
        c = conn.cursor()
        
        # Parolni yangilash
        c.execute("UPDATE users SET password = %s WHERE user_id = %s", (hashed_password, user_id))
        
        conn.commit()
        conn.close()
        
        # Log yozish
        log_action(session['user_id'], 'reset_password', f"Parol tiklandi: {user_id}")
        
        return jsonify({
            'success': True,
            'message': "Parol muvaffaqiyatli tiklandi",
            'new_password': new_password
        })
        
    except Exception as e:
        print(f"Parol tiklashda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})
#edit tasks funksiyasi
@app.route('/api/admin/edit_task/<task_id>', methods=['POST'])
def api_edit_task(task_id):
    """Topshiriqni tahrirlash"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        data = request.json
        
        # Majburiy maydonlarni tekshirish
        required_fields = ['title', 'assigned_to', 'deadline']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'{field} maydoni to\'ldirilishi shart'})
        
        conn = get_db()
        c = conn.cursor()
        
        # Topshiriq mavjudligini tekshirish
        c.execute("SELECT assigned_by FROM user_tasks WHERE task_id = %s", (task_id,))
        existing_task = c.fetchone()
        
        if not existing_task:
            return jsonify({'success': False, 'error': 'Topshiriq topilmadi'})
        
        # Admin/Debugger huquqlarini tekshirish
        if session.get('role') != 'debugger':
            # Admin faqat o'zi yaratgan topshiriqlarni tahrirlay oladi
            if existing_task[0] != session['user_id']:
                return jsonify({
                    'success': False, 
                    'error': 'Siz faqat o\'zingiz yaratgan topshiriqlarni tahrirlay olasiz'
                })
        
        # Topshiriqni yangilash
        c.execute('''UPDATE user_tasks 
                    SET title = %s,
                        description = %s,
                        assigned_to = %s,
                        deadline = %s,
                        points = %s,
                        task_type = %s,
                        priority = %s,
                        status = %s
                    WHERE task_id = %s
                ''', (
                    data['title'],
                    data.get('description', ''),
                    data['assigned_to'],
                    data['deadline'],
                    data.get('points', 5),
                    data.get('task_type', 'regular'),
                    data.get('priority', 'medium'),
                    data.get('status', 'pending'),
                    task_id
                ))
        
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'edit_task', 
                  f"Topshiriq tahrirlandi: {task_id} - {data['title']}")
        
        return jsonify({
            'success': True,
            'message': 'Topshiriq muvaffaqiyatli tahrirlandi!',
            'task_id': task_id
        })
        
    except Exception as e:
        print(f"Topshiriq tahrirlashda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})
        
# EDIT_USER funksiyasini to'g'rilash:
# app.py faylida api_edit_user funksiyasini yangilaymiz:

@app.route('/api/admin/edit_user/<user_id>', methods=['GET', 'POST'])
def api_edit_user(user_id):
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    if request.method == 'GET':
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = c.fetchone()
            conn.close()
            
            if user:
                # users jadval strukturasini tekshiramiz
                user_dict = {
                    'id': user[0],
                    'user_id': user[1],
                    'full_name': user[3],
                    'district': user[4],
                    'age': user[5],
                    'role': user[6],
                    'rating': user[7] if len(user) > 7 else 0,
                    'joined_date': user[8] if len(user) > 8 else '',
                    'phone': user[10] if len(user) > 10 else '',
                    'yoshlar_guruhi': user[11] if len(user) > 11 else '',
                    'qomita': user[12] if len(user) > 12 else ''
                }
                return jsonify({'success': True, 'user': user_dict})
            else:
                return jsonify({'success': False, 'error': 'Foydalanuvchi topilmadi'})
                
        except Exception as e:
            print(f"Foydalanuvchi ma'lumotlarini olishda xatolik: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    elif request.method == 'POST':
        try:
            data = request.json
            
            conn = get_db()
            c = conn.cursor()
            
            # Foydalanuvchini yangilash
            update_fields = []
            update_values = []
            
            # Asosiy maydonlar
            if 'full_name' in data:
                update_fields.append("full_name = %s")
                update_values.append(data['full_name'])
            
            if 'district' in data:
                update_fields.append("district = %s")
                update_values.append(data['district'])
            
            if 'age' in data:
                update_fields.append("age = %s")
                update_values.append(data['age'])
            
            if 'role' in data:
                # Admin faqat user/admin rolini o'zgartira oladi, debugger bo'lsa ham
                current_role = session.get('role')
                if current_role == 'debugger' or data['role'] in ['user', 'admin']:
                    update_fields.append("role = %s")
                    update_values.append(data['role'])
                else:
                    return jsonify({'success': False, 'error': 'Siz faqat user/admin rolini o\'zgartira olasiz'})
            
            if 'rating' in data:
                update_fields.append("rating = %s")
                update_values.append(data['rating'])
            
            if 'phone' in data:
                update_fields.append("phone = %s")
                update_values.append(data['phone'])
            
            if 'yoshlar_guruhi' in data:
                update_fields.append("yoshlar_guruhi = %s")
                update_values.append(data['yoshlar_guruhi'])
            
            if 'qomita' in data:
                update_fields.append("qomita = %s")
                update_values.append(data['qomita'])
            
            # Parolni yangilash (agar berilgan bo'lsa)
            if 'password' in data and data['password']:
                hashed_password = generate_password_hash(data['password'])
                update_fields.append("password = %s")
                update_values.append(hashed_password)
            
            # Agar o'zgartiriladigan maydonlar bo'lsa
            if update_fields:
                update_values.append(user_id)
                query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = %s"
                c.execute(query, update_values)
                
                conn.commit()
                conn.close()
                
                # Log yozish
                log_action(session['user_id'], 'edit_user', f"Foydalanuvchi tahrirlandi: {user_id}")
                
                return jsonify({
                    'success': True,
                    'message': f"Foydalanuvchi {user_id} muvaffaqiyatli yangilandi"
                })
            else:
                return jsonify({'success': False, 'error': 'Yangilanish uchun ma\'lumotlar yo\'q'})
            
        except Exception as e:
            print(f"Foydalanuvchi tahrirlashda xatolik: {e}")
            return jsonify({'success': False, 'error': str(e)})

# BACKUP YUKLASH funksiyasini qo'shamiz:
@app.route('/api/admin/import_database', methods=['POST'])
def api_import_database():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Fayl topilmadi'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Fayl tanlanmagan'})
    
    if not file.filename.endswith('.sql'):
        return jsonify({'success': False, 'error': 'Faqat .sql fayllar qabul qilinadi'})
    
    try:
        # Faylni o'qish
        sql_content = file.read().decode('utf-8')
        
        # Hozirgi bazani backup qilish
        backup_filename = f"backup_before_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        backup_path = os.path.join(app.config['UPLOAD_FOLDER'], backup_filename)
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            conn = get_db()
            
            # Barcha jadvallarni dump qilish
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=%s", (table_name,))
                create_table_sql = cursor.fetchone()
                if create_table_sql:
                    f.write(create_table_sql[0] + ";\n\n")
                
                cursor.execute(f'SELECT * FROM "{table_name}"')
                rows = cursor.fetchall()
                
                if rows:
                    f.write(f'INSERT INTO "{table_name}" VALUES\n')
                    for i, row in enumerate(rows):
                        values = []
                        for value in row:
                            if value is None:
                                values.append('NULL')
                            elif isinstance(value, str):
                                escaped_value = str(value).replace("'", "''")
                                values.append(f"'{escaped_value}'")
                            else:
                                values.append(str(value))
                        
                        f.write(f"({', '.join(values)})")
                        if i < len(rows) - 1:
                            f.write(",\n")
                        else:
                            f.write(";\n\n")
            
            conn.close()
        
        # Yangi SQL faylni ishga tushirish
        conn = get_db()
        cursor = conn.cursor()
        
        # SQL komandalarni ajratish
        sql_commands = sql_content.split(';')
        
        for command in sql_commands:
            command = command.strip()
            if command:
                try:
                    cursor.execute(command)
                except Exception as e:
                    print(f"SQL komanda xatosi: {command[:50]}... - {e}")
        
        conn.commit()
        conn.close()
        
        # Log yozish
        log_action(session['user_id'], 'import_database', 
                  f'Database import qilindi. Oldingi backup: {backup_filename}')
        
        return jsonify({
            'success': True, 
            'message': 'Baza muvaffaqiyatli import qilindi!',
            'backup_file': backup_filename
        })
        
    except Exception as e:
        print(f"Database importda xatolik: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

def safe_log_action(user_id, action, details):
    """Xatolarga bardoshli log yozish funksiyasi"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Jadval mavjudligini tekshirish
        c.execute('''SELECT name FROM sqlite_master 
                     WHERE type='table' AND name='system_logs' ''')
        if not c.fetchone():
            # Agar jadval yo'q bo'lsa, yaratish
            c.execute('''CREATE TABLE system_logs (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT,
                            action TEXT,
                            details TEXT,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
            conn.commit()
        
        # Log yozish
        c.execute('''INSERT INTO system_logs (user_id, action, details) 
                     VALUES (%s, %s, %s)''', (user_id or 'unknown', action, details))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        # Xatoni console ga chiqaramiz, lekin programma to'xtamaydi
        print(f"⚠️ Log yozishda xatolik (lekin davom etamiz): {e}")
        return False

# @app.route('/api/admin/get_users')
# def api_get_users():
#     if session.get('role') not in ['debugger', 'admin']:
#         return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
#     try:
#         conn = get_db()
#         c = conn.cursor()
#         c.execute("SELECT * FROM users ORDER BY id")
#         users = c.fetchall()
#         conn.close()
        
#         # Ma'lumotlarni formatlash
#         users_list = []
#         for user in users:
#             users_list.append({
#                 'id': user[0],
#                 'user_id': user[1],
#                 'full_name': user[3],
#                 'district': user[4],
#                 'age': user[5],
#                 'role': user[6],
#                 'rating': user[7],
#                 'joined_date': user[8] if len(user) > 8 else ''
#             })
        
#         return jsonify({'success': True, 'users': users_list})
        
#     except Exception as e:
#         print(f"Foydalanuvchilarni olishda xatolik: {e}")
#         return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/get_users_for_tasks')
def get_users_for_tasks():
    """Topshiriqlar uchun foydalanuvchilar ro'yxati"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Barcha foydalanuvchilarni olish
        cursor.execute('''
            SELECT user_id, full_name, district, role, phone
            FROM users 
            WHERE role IN ('user', 'admin', 'debugger')
            ORDER BY 
                CASE role
                    WHEN 'debugger' THEN 1
                    WHEN 'admin' THEN 2
                    WHEN 'user' THEN 3
                    ELSE 4
                END,
                full_name
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        users_list = []
        for user in users:
            users_list.append({
                'user_id': user[0],
                'full_name': user[1],
                'district': user[2],
                'role': user[3],
                'phone': user[4] if len(user) > 4 else ''
            })
        
        print(f"📋 Topshiriqlar uchun {len(users_list)} ta foydalanuvchi")
        return jsonify({'success': True, 'users': users_list})
        
    except Exception as e:
        print(f"❌ Foydalanuvchilarni olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/add_points/<user_id>', methods=['POST'])
def add_points_to_user(user_id):
    """Foydalanuvchiga ball qo'shish"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        data = request.get_json()
        points = int(data.get('points', 0))
        reason = data.get('reason', '')
        task_id = data.get('task_id', '')
        
        if points <= 0:
            return jsonify({'success': False, 'error': 'Noto\'g\'ri ball miqdori'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Foydalanuvchini topish
        cursor.execute('SELECT rating FROM users WHERE user_id = %s', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'Foydalanuvchi topilmadi'})
        
        # Yangi reyting
        current_rating = user[0] or 0
        new_rating = min(20, current_rating + points)  # Maksimum 20
        
        # Yangilash
        cursor.execute('UPDATE users SET rating = %s WHERE user_id = %s', 
                      (new_rating, user_id))
        
        # Log yozish
        cursor.execute('''
            INSERT INTO rating_logs (user_id, points, reason, task_id, added_by, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (user_id, points, reason, task_id, session.get('user_id'), 
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        conn.close()
        
        print(f"✅ {user_id} ga {points} ball qo'shildi. Yangi reyting: {new_rating}")
        
        return jsonify({
            'success': True,
            'message': f'Foydalanuvchiga {points} ball qo\'shildi',
            'new_rating': new_rating,
            'added_points': points
        })
        
    except Exception as e:
        print(f"❌ Ball qo'shishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/get_tasks')
def get_tasks():
    """Barcha topshiriqlarni olish"""
    if session.get('role') not in ['admin', 'debugger']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.*, u.full_name as assignee_name, a.full_name as admin_name
            FROM user_tasks t
            LEFT JOIN users u ON t.assigned_to = u.user_id
            LEFT JOIN users a ON t.assigned_by = a.user_id
            ORDER BY t.created_at DESC
        ''')
        
        tasks = cursor.fetchall()
        conn.close()
        
        tasks_list = []
        
        # Jadval ustunlarini aniqlash
        cursor.execute("PRAGMA table_info(user_tasks)")
        task_columns = [col[1] for col in cursor.fetchall()]
        
        for task in tasks:
            task_dict = {}
            
            # Asosiy maydonlar
            for i, col_name in enumerate(task_columns):
                if i < len(task):
                    task_dict[col_name] = task[i]
            
            # Qo'shimcha maydonlar
            assignee_name = task[len(task_columns)] if len(task) > len(task_columns) else ''
            admin_name = task[len(task_columns)+1] if len(task) > len(task_columns)+1 else ''
            
            # Agar assignee_name bo'sh bo'lsa, assigned_to ni ishlat
            if not assignee_name and task_dict.get('assigned_to'):
                if task_dict['assigned_to'] == 'all':
                    assignee_name = 'Barcha foydalanuvchilar'
                else:
                    assignee_name = task_dict['assigned_to']
            
            task_dict['assignee_name'] = assignee_name
            task_dict['admin_name'] = admin_name
            
            # ID ni aniqlash (task_id yoki id)
            task_dict['display_id'] = task_dict.get('task_id') or task_dict.get('id') or 'N/A'
            
            tasks_list.append(task_dict)
        
        print(f"✅ {len(tasks_list)} ta topshiriq topildi")
        return jsonify({'success': True, 'tasks': tasks_list})
        
    except Exception as e:
        print(f"❌ Topshiriqlarni olishda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)})
                   
@app.route('/api/admin/export_database')
def api_export_database():
    if session.get('role') not in ['debugger', 'admin']:
        return jsonify({'success': False, 'error': 'Ruxsat yo\'q'})
    
    try:
        # Bazaning to'liq nusxasini SQL formatda yaratish
        conn = get_db()
        cursor = conn.cursor()
        
        # Barcha jadvallarni olish
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()
        
        # SQL dump yaratish
        sql_dump = "-- Database Backup\n"
        sql_dump += "-- Generated: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n\n"
        
        for table in tables:
            table_name = table[0]
            sql_dump += f"\n-- Table: {table_name}\n"
            
            # Table schema
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=%s", (table_name,))
            create_table_sql = cursor.fetchone()
            if create_table_sql:
                sql_dump += create_table_sql[0] + ";\n\n"
            
            # Table data
            cursor.execute(f'SELECT * FROM "{table_name}"')
            rows = cursor.fetchall()
            
            if rows:
                # Ustun nomlarini olish
                cursor.execute(f'PRAGMA table_info("{table_name}")')
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                sql_dump += f'INSERT INTO "{table_name}" ({", ".join(column_names)}) VALUES\n'
                
                for i, row in enumerate(rows):
                    values = []
                    for value in row:
                        if value is None:
                            values.append('NULL')
                        elif isinstance(value, str):
                            # SQL injectiondan himoya qilish
                            escaped_value = str(value).replace("'", "''")
                            values.append(f"'{escaped_value}'")
                        else:
                            values.append(str(value))
                    
                    sql_dump += f"({', '.join(values)})"
                    if i < len(rows) - 1:
                        sql_dump += ",\n"
                    else:
                        sql_dump += ";\n\n"
        
        conn.close()
        
        # Log yozish
        log_action(session.get('user_id', 'unknown'), 'export_database', 'Database backup exported')
        
        # Faylni yuborish
        return Response(sql_dump,
                       mimetype='application/sql',
                       headers={'Content-Disposition': 'attachment;filename=database_backup.sql'})
        
    except Exception as e:
        print(f"Database exportda xatolik: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Qo'shimcha yordamchi funksiyalar
def generate_random_password(length=8):
    import random
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# 3. LOG_ACTION funksiyasini to'g'rilash:
def log_action(user_id, action, details):
    """Sistem loglarini yozish"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Jadval mavjudligini tekshirish va yaratish
        c.execute('''CREATE TABLE IF NOT EXISTS system_logs (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT,
                        action TEXT,
                        details TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        c.execute('''
            INSERT INTO system_logs (user_id, action, details)
            VALUES (%s, %s, %s)
        ''', (user_id, action, details))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Log yozishda xatolik: {e}")
        return False

def get_regions():
    return {
        '01': 'Toshkent shahri',
        '02': 'Toshkent viloyati',
        '03': 'Andijon viloyati',
        '04': 'Fargʻona viloyati',
        '05': 'Namangan viloyati',
        '06': 'Samarqand viloyati',
        '07': 'Buxoro viloyati',
        '08': 'Xorazm viloyati',
        '09': 'Surxondaryo viloyati',
        '10': 'Qashqadaryo viloyati',
        '11': 'Jizzax viloyati',
        '12': 'Sirdaryo viloyati',
        '13': 'Navoiy viloyati',
        '14': 'Qoraqalpogʻiston Respublikasi'
    }
    
# Test uchun sahifa - barcha foydalanuvchilarni ko'rish
@app.route('/test_users')
def test_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, role FROM users")
    users = c.fetchall()
    conn.close()
    
    result = "<h1>Barcha foydalanuvchilar:</h1>"
    for user in users:
        result += f"<p>ID: {user[0]}, Ism: {user[1]}, Rol: {user[2]}</p>"
    
    return result + '<br><a href="/login">Login sahifasiga qaytish</a>'


# app.py faylining oxirgi qismi

if __name__ == '__main__':
    # FAKAT jadvallarni yaratish, eski bazani O'CHIRMAYMIZ!
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Jadvallarni yaratish (agar yo'q bo'lsa)
    conn = get_db()
    c = conn.cursor()
    
    # Foydalanuvchilar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT UNIQUE,
                    password TEXT,
                    full_name TEXT,
                    district TEXT,
                    age INTEGER,
                    role TEXT DEFAULT 'user',
                    rating INTEGER DEFAULT 0,
                    joined_date DATE DEFAULT CURRENT_DATE,
                    last_login TIMESTAMP
                )''')
    
    # Hisobotlar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    month_year TEXT,
                    event_count INTEGER DEFAULT 0,
                    material_count INTEGER DEFAULT 0,
                    message_count INTEGER DEFAULT 0,
                    safety_score INTEGER DEFAULT 5,
                    file_path TEXT,
                    description TEXT,
                    challenges TEXT,
                    suggestions TEXT,
                    status TEXT DEFAULT 'pending',
                    admin_comment TEXT,
                    submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )''')
    
    # Baholar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
                    id SERIAL PRIMARY KEY,
                    report_id INTEGER,
                    faollik INTEGER,
                    tashabbus INTEGER,
                    intizom INTEGER,
                    tasir INTEGER,
                    total INTEGER,
                    admin_comment TEXT,
                    rated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (report_id) REFERENCES reports(id)
                )''')
    
    # Topshiriqlar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    created_by TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # Sistem loglari jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS system_logs (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    action TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # Yangi ustunlarni qo'shish (migration)
    try:
        c.execute("ALTER TABLE users ADD COLUMN yoshlar_guruhi TEXT DEFAULT ''")
    except:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN qomita TEXT DEFAULT ''")
    except:
        pass
    
    conn.commit()
    conn.close()
    
    port = int(os.environ.get("PORT", 5001))
    print("=" * 50)
    print("🚀 Yoshlar Parlamenti Platformasi ISHGA TUSHIRILDI!")
    print(f"🌐 Manzil: http://localhost:{port}")
    print("👑 Debugger login: debug001 / debug123")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=True)
