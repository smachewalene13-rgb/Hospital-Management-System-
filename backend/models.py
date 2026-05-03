from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import bcrypt
from datetime import datetime, timedelta
import jwt
from functools import wraps

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
CORS(app, supports_credentials=True, origins=['http://localhost:5000', 'http://127.0.0.1:5000', 'http://localhost:5500'])

# Database setup
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'hospital.db')

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'staff',
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create patients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create doctors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            phone TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create appointments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            status TEXT DEFAULT 'Scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    # Create default admin user
    admin = cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',)).fetchone()
    if not admin:
        password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, full_name)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin', 'admin@hospital.com', password_hash, 'admin', 'System Administrator'))
        conn.commit()
        print("✅ Admin user created: admin / admin123")
    
    # Add sample data
    doctor_count = cursor.execute('SELECT COUNT(*) as count FROM doctors').fetchone()['count']
    if doctor_count == 0:
        cursor.execute('INSERT INTO doctors (name, specialization, phone) VALUES (?, ?, ?)',
                      ('Dr. John Smith', 'Cardiologist', '1234567890'))
        cursor.execute('INSERT INTO doctors (name, specialization, phone) VALUES (?, ?, ?)',
                      ('Dr. Sarah Johnson', 'Neurologist', '1234567891'))
        conn.commit()
        print("✅ Sample doctors added")
    
    conn.close()
    print("✅ Database initialized successfully!")

# JWT Token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = token.split(' ')[1] if ' ' in token else token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = data['user_id']
        except:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(*args, **kwargs)
    return decorated

# Serve frontend
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/pages/<path:path>')
def serve_pages(path):
    return send_from_directory('../frontend/pages', path)

@app.route('/css/<path:path>')
def serve_css(path):
    return send_from_directory('../frontend/css', path)

@app.route('/js/<path:path>')
def serve_js(path):
    return send_from_directory('../frontend/js', path)

# ============ AUTHENTICATION ROUTES ============
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        print(f"Login attempt: {username}")
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            token = jwt.encode({
                'user_id': user['id'],
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, app.config['SECRET_KEY'], algorithm='HS256')
            
            return jsonify({
                'access_token': token,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'role': user['role'],
                    'full_name': user['full_name']
                }
            }), 200
        
        return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, full_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['username'], data['email'], password_hash, 'staff', data.get('full_name', '')))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'message': 'User created successfully', 'user_id': user_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ============ PATIENT ROUTES ============
@app.route('/api/patients', methods=['GET'])
@token_required
def get_patients():
    conn = get_db()
    patients = conn.execute('SELECT * FROM patients ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(p) for p in patients])

@app.route('/api/patients', methods=['POST'])
@token_required
def add_patient():
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO patients (name, age, gender, phone, email)
        VALUES (?, ?, ?, ?, ?)
    ''', (data['name'], data['age'], data['gender'], data['phone'], data.get('email', '')))
    conn.commit()
    patient_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': patient_id, 'message': 'Patient added successfully'}), 201

# ============ DOCTOR ROUTES ============
@app.route('/api/doctors', methods=['GET'])
@token_required
def get_doctors():
    conn = get_db()
    doctors = conn.execute('SELECT * FROM doctors ORDER BY name').fetchall()
    conn.close()
    return jsonify([dict(d) for d in doctors])

@app.route('/api/doctors', methods=['POST'])
@token_required
def add_doctor():
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO doctors (name, specialization, phone)
        VALUES (?, ?, ?)
    ''', (data['name'], data['specialization'], data['phone']))
    conn.commit()
    doctor_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': doctor_id, 'message': 'Doctor added successfully'}), 201

# ============ APPOINTMENT ROUTES ============
@app.route('/api/appointments', methods=['GET'])
@token_required
def get_appointments():
    conn = get_db()
    appointments = conn.execute('''
        SELECT a.*, p.name as patient_name, d.name as doctor_name 
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        ORDER BY a.appointment_date DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(a) for a in appointments])

@app.route('/api/appointments', methods=['POST'])
@token_required
def add_appointment():
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time)
        VALUES (?, ?, ?, ?)
    ''', (data['patient_id'], data['doctor_id'], data['appointment_date'], data['appointment_time']))
    conn.commit()
    appointment_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': appointment_id, 'message': 'Appointment scheduled successfully'}), 201

@app.route('/api/appointments/<int:appointment_id>/status', methods=['PUT'])
@token_required
def update_appointment_status(appointment_id):
    data = request.get_json()
    conn = get_db()
    conn.execute('UPDATE appointments SET status = ? WHERE id = ?', (data['status'], appointment_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Appointment status updated'})

# ============ DASHBOARD STATS ============
@app.route('/api/dashboard/stats', methods=['GET'])
@token_required
def get_stats():
    conn = get_db()
    total_patients = conn.execute('SELECT COUNT(*) as count FROM patients').fetchone()['count']
    total_doctors = conn.execute('SELECT COUNT(*) as count FROM doctors').fetchone()['count']
    total_appointments = conn.execute('SELECT COUNT(*) as count FROM appointments').fetchone()['count']
    today_appointments = conn.execute(
        "SELECT COUNT(*) as count FROM appointments WHERE appointment_date = date('now')"
    ).fetchone()['count']
    conn.close()
    
    return jsonify({
        'total_patients': total_patients,
        'total_doctors': total_doctors,
        'total_appointments': total_appointments,
        'scheduled_appointments': today_appointments
    })

# Test endpoint
@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({'message': 'API is working!', 'status': 'success'}), 200

if __name__ == '__main__':
    init_db()
    print("\n" + "="*50)
    print("🚀 Server Starting...")
    print("📍 URL: http://localhost:5000")
    print("🔐 Login: admin / admin123")
    print("="*50 + "\n")
    app.run(debug=True, host='127.0.0.1', port=5000)