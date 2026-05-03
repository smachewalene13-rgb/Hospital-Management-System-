from flask import Flask, request, jsonify, send_from_directory, make_response, send_file
from flask_cors import CORS
import sqlite3
import os
import bcrypt
import jwt
import re
import csv
import io
from datetime import datetime, timedelta
from functools import wraps
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Initialize Flask app FIRST
app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config['SECRET_KEY'] = 'hospital-management-system-secret-key-2024'
CORS(app, supports_credentials=True)

# Database setup
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'hospital.db')

def get_db():
    """Get database connection"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_pharmacy_table():
    """Create pharmacy inventory table"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pharmacy_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            generic_name TEXT,
            category TEXT,
            manufacturer TEXT,
            stock_quantity INTEGER DEFAULT 0,
            unit_price REAL DEFAULT 0,
            expiry_date DATE,
            reorder_level INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Pharmacy inventory table created")

def init_db():
    """Initialize database with tables and sample data"""
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
            department TEXT,
            phone TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
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
            address TEXT,
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
            email TEXT,
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
            symptoms TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
            FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Create pharmacy table
    create_pharmacy_table()
    
    # Create default admin user
    conn = get_db()
    cursor = conn.cursor()
    admin = cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',)).fetchone()
    if not admin:
        password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, full_name, department)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('admin', 'admin@hospital.com', password_hash, 'admin', 'System Administrator', 'IT'))
        conn.commit()
        print("✅ Admin user created: admin / admin123")
    
    # Add sample doctors if none exist
    doctor_count = cursor.execute('SELECT COUNT(*) as count FROM doctors').fetchone()['count']
    if doctor_count == 0:
        sample_doctors = [
            ('Dr. John Smith', 'Cardiologist', '1234567890', 'john@hospital.com'),
            ('Dr. Sarah Johnson', 'Neurologist', '1234567891', 'sarah@hospital.com'),
            ('Dr. Michael Lee', 'Pediatrician', '1234567892', 'michael@hospital.com'),
            ('Dr. Emily Brown', 'Dermatologist', '1234567893', 'emily@hospital.com'),
            ('Dr. David Wilson', 'Orthopedic', '1234567894', 'david@hospital.com')
        ]
        for doctor in sample_doctors:
            cursor.execute('INSERT INTO doctors (name, specialization, phone, email) VALUES (?, ?, ?, ?)', doctor)
        conn.commit()
        print("✅ Sample doctors added")
    
    # Add sample patients if none exist
    patient_count = cursor.execute('SELECT COUNT(*) as count FROM patients').fetchone()['count']
    if patient_count == 0:
        sample_patients = [
            ('John Doe', 35, 'Male', '9876543210', 'john@example.com', '123 Main St'),
            ('Jane Smith', 28, 'Female', '9876543211', 'jane@example.com', '456 Oak Ave'),
            ('Bob Wilson', 42, 'Male', '9876543212', 'bob@example.com', '789 Pine Rd'),
            ('Alice Johnson', 25, 'Female', '9876543213', 'alice@example.com', '321 Elm St'),
            ('Charlie Brown', 50, 'Male', '9876543214', 'charlie@example.com', '654 Maple Ave')
        ]
        for patient in sample_patients:
            cursor.execute('INSERT INTO patients (name, age, gender, phone, email, address) VALUES (?, ?, ?, ?, ?, ?)', patient)
        conn.commit()
        print("✅ Sample patients added")
    
    # Add sample medicines if none exist
    medicine_count = cursor.execute('SELECT COUNT(*) as count FROM pharmacy_inventory').fetchone()['count']
    if medicine_count == 0:
        sample_medicines = [
            ('Paracetamol', 'Acetaminophen', 'Painkiller', 'Generic Pharma', 100, 5.99, '2025-12-31', 20),
            ('Amoxicillin', 'Amoxicillin', 'Antibiotic', 'MediCorp', 50, 12.99, '2025-10-31', 15),
            ('Ibuprofen', 'Ibuprofen', 'Painkiller', 'HealthCare Ltd', 75, 8.50, '2025-11-30', 15),
            ('Cetirizine', 'Cetirizine HCl', 'Antihistamine', 'AllergyCare', 30, 15.99, '2025-09-30', 10),
            ('Vitamin C', 'Ascorbic Acid', 'Vitamin', 'NutriLife', 200, 4.99, '2026-01-31', 30)
        ]
        for medicine in sample_medicines:
            cursor.execute('''
                INSERT INTO pharmacy_inventory (medicine_name, generic_name, category, manufacturer, stock_quantity, unit_price, expiry_date, reorder_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', medicine)
        conn.commit()
        print("✅ Sample medicines added")
    
    conn.close()
    print("✅ Database initialized successfully!")
    return True

# JWT token decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = data['user_id']
            
            # Check if user is admin
            conn = get_db()
            user = conn.execute('SELECT role FROM users WHERE id = ?', (request.user_id,)).fetchone()
            conn.close()
            
            if not user or user['role'] != 'admin':
                return jsonify({'error': 'Admin access required'}), 403
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated

# Serve frontend files
@app.route('/')
def serve_index():
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

# ============ AUTHENTICATION & REGISTRATION ============

@app.route('/api/auth/check-username', methods=['GET'])
def check_username():
    """Check if username is available"""
    username = request.args.get('username')
    if not username:
        return jsonify({'exists': False}), 200
    
    conn = get_db()
    user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    return jsonify({'exists': user is not None})

@app.route('/api/auth/check-email', methods=['GET'])
def check_email():
    """Check if email is available"""
    email = request.args.get('email')
    if not email:
        return jsonify({'exists': False}), 200
    
    conn = get_db()
    user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    
    return jsonify({'exists': user is not None})

@app.route('/api/auth/register', methods=['POST'])
def register_user():
    """Register a new user"""
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['username', 'email', 'password', 'role']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        username = data['username']
        email = data['email']
        password = data['password']
        role = data['role']
        full_name = data.get('full_name', username)
        department = data.get('department', '')
        phone = data.get('phone', '')
        
        # Validate username length
        if len(username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate password strength
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Validate role
        valid_roles = ['admin', 'doctor', 'staff']
        if role not in valid_roles:
            return jsonify({'error': 'Invalid role selected'}), 400
        
        conn = get_db()
        
        # Check if username exists
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing_user:
            conn.close()
            return jsonify({'error': 'Username already taken'}), 400
        
        # Check if email exists
        existing_email = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing_email:
            conn.close()
            return jsonify({'error': 'Email already registered'}), 400
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insert new user
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, full_name, department, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, email, password_hash, role, full_name, department, phone))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        print(f"✅ New user registered: {username} ({role})")
        
        return jsonify({
            'message': 'User registered successfully',
            'user_id': user_id,
            'username': username,
            'role': role
        }), 201
        
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND is_active = 1', (username,)).fetchone()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            # Update last login
            conn = get_db()
            conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            conn.commit()
            conn.close()
            
            token = jwt.encode({
                'user_id': user['id'],
                'username': user['username'],
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
        
        return jsonify({'error': 'Invalid username or password'}), 401
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============ USER MANAGEMENT (Admin only) ============

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users (admin only)"""
    try:
        conn = get_db()
        users = conn.execute('''
            SELECT id, username, email, role, full_name, department, phone, 
                   created_at, last_login, is_active 
            FROM users 
            ORDER BY created_at DESC
        ''').fetchall()
        conn.close()
        
        return jsonify([dict(user) for user in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """Get single user (admin only)"""
    try:
        conn = get_db()
        user = conn.execute('''
            SELECT id, username, email, role, full_name, department, phone, 
                   created_at, last_login, is_active 
            FROM users 
            WHERE id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify(dict(user))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Update user (admin only)"""
    try:
        conn = get_db()
        
        # Check if user exists
        existing_user = conn.execute('SELECT id, role FROM users WHERE id = ?', (user_id,)).fetchone()
        if not existing_user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Don't allow admin to change their own role to non-admin
        if user_id == request.user_id:
            data = request.get_json()
            if 'role' in data and data['role'] != 'admin':
                conn.close()
                return jsonify({'error': 'Cannot demote your own admin role'}), 400
        
        data = request.get_json()
        
        update_fields = []
        values = []
        
        allowed_fields = ['role', 'full_name', 'department', 'phone', 'is_active']
        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = ?")
                values.append(data[field])
        
        if update_fields:
            values.append(user_id)
            conn.execute(f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?", values)
            conn.commit()
        
        conn.close()
        return jsonify({'message': 'User updated successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete user (admin only)"""
    try:
        conn = get_db()
        
        # Check if user exists
        existing_user = conn.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
        if not existing_user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Don't allow deleting yourself
        if user_id == request.user_id:
            conn.close()
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'User deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ============ PATIENTS ============
@app.route('/api/patients', methods=['GET'])
@token_required
def get_patients():
    try:
        conn = get_db()
        patients = conn.execute('SELECT * FROM patients ORDER BY created_at DESC').fetchall()
        conn.close()
        return jsonify([dict(p) for p in patients])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/patients', methods=['POST'])
@token_required
def add_patient():
    try:
        data = request.get_json()
        print(f"Received patient data: {data}")
        
        # Validate required fields
        if not data.get('name') or not data.get('age') or not data.get('gender') or not data.get('phone'):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO patients (name, age, gender, phone, email, address)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['name'], data['age'], data['gender'], data['phone'], 
              data.get('email', ''), data.get('address', '')))
        conn.commit()
        patient_id = cursor.lastrowid
        conn.close()
        
        print(f"Patient added successfully with ID: {patient_id}")
        
        return jsonify({'id': patient_id, 'message': 'Patient added successfully'}), 201
    except Exception as e:
        print(f"Error adding patient: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/patients/<int:patient_id>', methods=['DELETE'])
@token_required
def delete_patient(patient_id):
    try:
        conn = get_db()
        
        # Check if patient exists
        patient = conn.execute('SELECT id FROM patients WHERE id = ?', (patient_id,)).fetchone()
        if not patient:
            conn.close()
            return jsonify({'error': 'Patient not found'}), 404
        
        # Delete the patient
        conn.execute('DELETE FROM patients WHERE id = ?', (patient_id,))
        conn.commit()
        conn.close()
        
        print(f"Patient {patient_id} deleted successfully")
        
        return jsonify({'message': 'Patient deleted successfully'}), 200
    except Exception as e:
        print(f"Error deleting patient: {str(e)}")
        return jsonify({'error': str(e)}), 400

# ============ DOCTORS ============
@app.route('/api/doctors', methods=['GET'])
@token_required
def get_doctors():
    try:
        conn = get_db()
        doctors = conn.execute('SELECT * FROM doctors ORDER BY name').fetchall()
        conn.close()
        return jsonify([dict(d) for d in doctors])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/doctors', methods=['POST'])
@token_required
def add_doctor():
    try:
        data = request.get_json()
        print(f"Received doctor data: {data}")
        
        # Validate required fields
        if not data.get('name') or not data.get('specialization') or not data.get('phone'):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO doctors (name, specialization, phone, email)
            VALUES (?, ?, ?, ?)
        ''', (data['name'], data['specialization'], data['phone'], data.get('email', '')))
        conn.commit()
        doctor_id = cursor.lastrowid
        conn.close()
        
        print(f"Doctor added successfully with ID: {doctor_id}")
        
        return jsonify({'id': doctor_id, 'message': 'Doctor added successfully'}), 201
    except Exception as e:
        print(f"Error adding doctor: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/doctors/<int:doctor_id>', methods=['DELETE'])
@token_required
def delete_doctor(doctor_id):
    try:
        conn = get_db()
        
        # Check if doctor exists
        doctor = conn.execute('SELECT id FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
        if not doctor:
            conn.close()
            return jsonify({'error': 'Doctor not found'}), 404
        
        # Delete the doctor
        conn.execute('DELETE FROM doctors WHERE id = ?', (doctor_id,))
        conn.commit()
        conn.close()
        
        print(f"Doctor {doctor_id} deleted successfully")
        
        return jsonify({'message': 'Doctor deleted successfully'}), 200
    except Exception as e:
        print(f"Error deleting doctor: {str(e)}")
        return jsonify({'error': str(e)}), 400

# ============ APPOINTMENTS ============
@app.route('/api/appointments', methods=['GET'])
@token_required
def get_appointments():
    try:
        conn = get_db()
        appointments = conn.execute('''
            SELECT a.*, p.name as patient_name, d.name as doctor_name, d.specialization
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
        ''').fetchall()
        conn.close()
        return jsonify([dict(a) for a in appointments])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/appointments', methods=['POST'])
@token_required
def add_appointment():
    try:
        data = request.get_json()
        print(f"Received appointment data: {data}")
        
        # Validate required fields
        if not data.get('patient_id') or not data.get('doctor_id') or not data.get('appointment_date') or not data.get('appointment_time'):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, symptoms)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['patient_id'], data['doctor_id'], data['appointment_date'], data['appointment_time'], data.get('symptoms', '')))
        conn.commit()
        appointment_id = cursor.lastrowid
        conn.close()
        
        print(f"Appointment added successfully with ID: {appointment_id}")
        
        return jsonify({'id': appointment_id, 'message': 'Appointment scheduled successfully'}), 201
    except Exception as e:
        print(f"Error adding appointment: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/appointments/<int:appointment_id>', methods=['DELETE'])
@token_required
def delete_appointment(appointment_id):
    try:
        conn = get_db()
        
        # Check if appointment exists
        appointment = conn.execute('SELECT id FROM appointments WHERE id = ?', (appointment_id,)).fetchone()
        if not appointment:
            conn.close()
            return jsonify({'error': 'Appointment not found'}), 404
        
        # Delete the appointment
        conn.execute('DELETE FROM appointments WHERE id = ?', (appointment_id,))
        conn.commit()
        conn.close()
        
        print(f"Appointment {appointment_id} deleted successfully")
        
        return jsonify({'message': 'Appointment deleted successfully'}), 200
    except Exception as e:
        print(f"Error deleting appointment: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/appointments/<int:appointment_id>/status', methods=['PUT'])
@token_required
def update_appointment_status(appointment_id):
    try:
        data = request.get_json()
        conn = get_db()
        
        # Check if appointment exists
        appointment = conn.execute('SELECT id FROM appointments WHERE id = ?', (appointment_id,)).fetchone()
        if not appointment:
            conn.close()
            return jsonify({'error': 'Appointment not found'}), 404
        
        conn.execute('UPDATE appointments SET status = ? WHERE id = ?', (data['status'], appointment_id))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Appointment status updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ============ PHARMACY MANAGEMENT ============

@app.route('/api/pharmacy/medicines', methods=['GET'])
@token_required
def get_medicines():
    try:
        conn = get_db()
        medicines = conn.execute('SELECT * FROM pharmacy_inventory ORDER BY medicine_name').fetchall()
        conn.close()
        return jsonify([dict(m) for m in medicines])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pharmacy/medicines', methods=['POST'])
@token_required
def add_medicine():
    try:
        data = request.get_json()
        print(f"Received medicine data: {data}")
        
        # Validate required fields
        if not data.get('medicine_name') or data.get('stock_quantity') is None or data.get('unit_price') is None:
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pharmacy_inventory (medicine_name, generic_name, category, manufacturer, stock_quantity, unit_price, expiry_date, reorder_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['medicine_name'], data.get('generic_name', ''), data.get('category', ''),
              data.get('manufacturer', ''), data['stock_quantity'], data['unit_price'],
              data.get('expiry_date'), data.get('reorder_level', 10)))
        conn.commit()
        medicine_id = cursor.lastrowid
        conn.close()
        
        print(f"Medicine added successfully with ID: {medicine_id}")
        
        return jsonify({'id': medicine_id, 'message': 'Medicine added successfully'}), 201
    except Exception as e:
        print(f"Error adding medicine: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/pharmacy/medicines/<int:medicine_id>', methods=['DELETE'])
@token_required
def delete_medicine(medicine_id):
    try:
        conn = get_db()
        
        # Check if medicine exists
        medicine = conn.execute('SELECT id FROM pharmacy_inventory WHERE id = ?', (medicine_id,)).fetchone()
        if not medicine:
            conn.close()
            return jsonify({'error': 'Medicine not found'}), 404
        
        # Delete the medicine
        conn.execute('DELETE FROM pharmacy_inventory WHERE id = ?', (medicine_id,))
        conn.commit()
        conn.close()
        
        print(f"Medicine {medicine_id} deleted successfully")
        
        return jsonify({'message': 'Medicine deleted successfully'}), 200
    except Exception as e:
        print(f"Error deleting medicine: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/pharmacy/medicines/<int:medicine_id>', methods=['PUT'])
@token_required
def update_medicine(medicine_id):
    try:
        data = request.get_json()
        conn = get_db()
        
        # Check if medicine exists
        medicine = conn.execute('SELECT id FROM pharmacy_inventory WHERE id = ?', (medicine_id,)).fetchone()
        if not medicine:
            conn.close()
            return jsonify({'error': 'Medicine not found'}), 404
        
        # Update medicine
        conn.execute('''
            UPDATE pharmacy_inventory 
            SET stock_quantity = ?, unit_price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (data['stock_quantity'], data['unit_price'], medicine_id))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Medicine updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/pharmacy/low-stock', methods=['GET'])
@token_required
def get_low_stock():
    try:
        conn = get_db()
        medicines = conn.execute('''
            SELECT * FROM pharmacy_inventory 
            WHERE stock_quantity <= reorder_level 
            ORDER BY stock_quantity ASC
        ''').fetchall()
        conn.close()
        return jsonify([dict(m) for m in medicines])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ GLOBAL SEARCH ============

@app.route('/api/search', methods=['GET'])
@token_required
def global_search():
    """Global search across all modules"""
    try:
        query = request.args.get('q', '')
        filter_type = request.args.get('filter', 'all')
        
        if len(query) < 2:
            return jsonify({})
        
        search_term = f"%{query}%"
        results = {}
        
        conn = get_db()
        
        # Search Patients
        if filter_type in ['all', 'patients']:
            patients = conn.execute('''
                SELECT id, name, age, gender, phone, email, address 
                FROM patients 
                WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? OR CAST(id AS TEXT) LIKE ?
                LIMIT 20
            ''', (search_term, search_term, search_term, search_term)).fetchall()
            results['patients'] = [dict(p) for p in patients]
        
        # Search Doctors
        if filter_type in ['all', 'doctors']:
            doctors = conn.execute('''
                SELECT id, name, specialization, phone, email 
                FROM doctors 
                WHERE name LIKE ? OR specialization LIKE ? OR phone LIKE ? OR email LIKE ?
                LIMIT 20
            ''', (search_term, search_term, search_term, search_term)).fetchall()
            results['doctors'] = [dict(d) for d in doctors]
        
        # Search Appointments
        if filter_type in ['all', 'appointments']:
            appointments = conn.execute('''
                SELECT a.id, p.name as patient_name, d.name as doctor_name, 
                       a.appointment_date, a.appointment_time, a.status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                JOIN doctors d ON a.doctor_id = d.id
                WHERE p.name LIKE ? OR d.name LIKE ? OR a.status LIKE ?
                LIMIT 20
            ''', (search_term, search_term, search_term)).fetchall()
            results['appointments'] = [dict(a) for a in appointments]
        
        # Search Pharmacy
        if filter_type in ['all', 'pharmacy']:
            medicines = conn.execute('''
                SELECT id, medicine_name, generic_name, category, manufacturer, stock_quantity, unit_price
                FROM pharmacy_inventory 
                WHERE medicine_name LIKE ? OR generic_name LIKE ? OR category LIKE ? OR manufacturer LIKE ?
                LIMIT 20
            ''', (search_term, search_term, search_term, search_term)).fetchall()
            results['pharmacy'] = [dict(m) for m in medicines]
        
        conn.close()
        
        return jsonify(results)
        
    except Exception as e:
        print(f"Search error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============ REPORT EXPORT FUNCTIONS ============

@app.route('/api/reports/export-pdf/<report_type>', methods=['GET'])
@token_required
def export_pdf(report_type):
    """Export report as PDF"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#667eea'),
            alignment=1
        )
        
        title = Paragraph(f"Hospital Management System - {report_type.upper()} Report", title_style)
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Date range
        date_style = ParagraphStyle('DateStyle', parent=styles['Normal'], alignment=1)
        date_text = Paragraph(f"Period: {start_date} to {end_date}", date_style)
        elements.append(date_text)
        elements.append(Spacer(1, 20))
        
        conn = get_db()
        
        if report_type == 'patients':
            # Patients report
            patients = conn.execute('''
                SELECT id, name, age, gender, phone, email, address, created_at 
                FROM patients 
                WHERE DATE(created_at) BETWEEN ? AND ?
                ORDER BY created_at DESC
            ''', (start_date, end_date)).fetchall()
            
            # Table data
            data = [['ID', 'Name', 'Age', 'Gender', 'Phone', 'Email', 'Address', 'Registered Date']]
            for p in patients:
                data.append([
                    str(p['id']), p['name'], str(p['age']), p['gender'], 
                    p['phone'], p['email'] or '-', p['address'] or '-', 
                    p['created_at'][:10] if p['created_at'] else '-'
                ])
            
            # Create table
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
            
        elif report_type == 'appointments':
            # Appointments report
            appointments = conn.execute('''
                SELECT a.id, p.name as patient_name, d.name as doctor_name, 
                       d.specialization, a.appointment_date, a.appointment_time, a.status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                JOIN doctors d ON a.doctor_id = d.id
                WHERE DATE(a.appointment_date) BETWEEN ? AND ?
                ORDER BY a.appointment_date DESC
            ''', (start_date, end_date)).fetchall()
            
            data = [['ID', 'Patient', 'Doctor', 'Specialization', 'Date', 'Time', 'Status']]
            for a in appointments:
                data.append([
                    str(a['id']), a['patient_name'], a['doctor_name'], 
                    a['specialization'], a['appointment_date'], a['appointment_time'], a['status']
                ])
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
        
        elif report_type == 'pharmacy':
            # Pharmacy inventory report
            medicines = conn.execute('''
                SELECT id, medicine_name, category, manufacturer, stock_quantity, unit_price, expiry_date
                FROM pharmacy_inventory
                ORDER BY medicine_name
            ''').fetchall()
            
            data = [['ID', 'Medicine', 'Category', 'Manufacturer', 'Stock', 'Price', 'Expiry']]
            for m in medicines:
                data.append([
                    str(m['id']), m['medicine_name'], m['category'] or '-', 
                    m['manufacturer'] or '-', str(m['stock_quantity']), 
                    f"${m['unit_price']}", m['expiry_date'] or '-'
                ])
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
        
        conn.close()
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{report_type}_report_{start_date}_to_{end_date}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"PDF Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/export-csv/<report_type>', methods=['GET'])
@token_required
def export_csv(report_type):
    """Export report as CSV"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn = get_db()
        
        # Create CSV output
        output = io.StringIO()
        writer = csv.writer(output)
        
        if report_type == 'patients':
            patients = conn.execute('''
                SELECT id, name, age, gender, phone, email, address, created_at 
                FROM patients 
                WHERE DATE(created_at) BETWEEN ? AND ?
                ORDER BY created_at DESC
            ''', (start_date, end_date)).fetchall()
            
            writer.writerow(['ID', 'Name', 'Age', 'Gender', 'Phone', 'Email', 'Address', 'Registered Date'])
            for p in patients:
                writer.writerow([p['id'], p['name'], p['age'], p['gender'], p['phone'], p['email'] or '-', p['address'] or '-', p['created_at'][:10] if p['created_at'] else '-'])
                
        elif report_type == 'appointments':
            appointments = conn.execute('''
                SELECT a.id, p.name as patient_name, d.name as doctor_name, 
                       d.specialization, a.appointment_date, a.appointment_time, a.status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                JOIN doctors d ON a.doctor_id = d.id
                WHERE DATE(a.appointment_date) BETWEEN ? AND ?
                ORDER BY a.appointment_date DESC
            ''', (start_date, end_date)).fetchall()
            
            writer.writerow(['ID', 'Patient', 'Doctor', 'Specialization', 'Date', 'Time', 'Status'])
            for a in appointments:
                writer.writerow([a['id'], a['patient_name'], a['doctor_name'], a['specialization'], a['appointment_date'], a['appointment_time'], a['status']])
                
        elif report_type == 'pharmacy':
            medicines = conn.execute('''
                SELECT id, medicine_name, category, manufacturer, stock_quantity, unit_price, expiry_date
                FROM pharmacy_inventory
                ORDER BY medicine_name
            ''').fetchall()
            
            writer.writerow(['ID', 'Medicine', 'Category', 'Manufacturer', 'Stock', 'Unit Price', 'Expiry Date'])
            for m in medicines:
                writer.writerow([m['id'], m['medicine_name'], m['category'] or '-', m['manufacturer'] or '-', m['stock_quantity'], m['unit_price'], m['expiry_date'] or '-'])
        
        conn.close()
        
        # Prepare response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={report_type}_report_{start_date}_to_{end_date}.csv'
        
        return response
        
    except Exception as e:
        print(f"CSV Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============ DASHBOARD STATS ============
@app.route('/api/dashboard/stats', methods=['GET'])
@token_required
def get_dashboard_stats():
    try:
        conn = get_db()
        total_patients = conn.execute('SELECT COUNT(*) as count FROM patients').fetchone()['count']
        total_doctors = conn.execute('SELECT COUNT(*) as count FROM doctors').fetchone()['count']
        total_appointments = conn.execute('SELECT COUNT(*) as count FROM appointments').fetchone()['count']
        today_appointments = conn.execute(
            "SELECT COUNT(*) as count FROM appointments WHERE appointment_date = date('now')"
        ).fetchone()['count']
        total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
        total_medicines = conn.execute('SELECT COUNT(*) as count FROM pharmacy_inventory').fetchone()['count']
        low_stock_count = conn.execute('SELECT COUNT(*) as count FROM pharmacy_inventory WHERE stock_quantity <= reorder_level').fetchone()['count']
        conn.close()
        
        return jsonify({
            'total_patients': total_patients,
            'total_doctors': total_doctors,
            'total_appointments': total_appointments,
            'scheduled_appointments': today_appointments,
            'total_users': total_users,
            'total_medicines': total_medicines,
            'low_stock_count': low_stock_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ TEST ENDPOINT ============
@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({'message': 'API is working!', 'status': 'success', 'timestamp': str(datetime.now())}), 200

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🏥 HOSPITAL MANAGEMENT SYSTEM - BACKEND SERVER")
    print("="*60)
    
    # Initialize database
    init_db()
    
    print("\n📋 SERVER INFORMATION:")
    print(f"   • Host: 127.0.0.1")
    print(f"   • Port: 5000")
    print(f"   • URL: http://127.0.0.1:5000")
    print(f"\n🔐 LOGIN CREDENTIALS:")
    print(f"   • Username: admin")
    print(f"   • Password: admin123")
    print(f"\n📁 DATABASE LOCATION:")
    print(f"   • {DB_PATH}")
    print("\n" + "="*60)
    print("🚀 Starting server... Press CTRL+C to stop")
    print("="*60 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)