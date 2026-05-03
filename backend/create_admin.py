import sqlite3
import bcrypt
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'hospital.db')

def create_admin():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if admin exists
    admin = cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',)).fetchone()
    
    if not admin:
        # Create admin user
        password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, full_name)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin', 'admin@hospital.com', password_hash, 'admin', 'System Administrator'))
        conn.commit()
        print("✅ Admin user created successfully!")
        print("   Username: admin")
        print("   Password: admin123")
    else:
        print("✅ Admin user already exists")
        print("   Username: admin")
        print("   Password: admin123")
    
    conn.close()

if __name__ == "__main__":
    create_admin()