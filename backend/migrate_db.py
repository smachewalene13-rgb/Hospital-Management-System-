import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'hospital.db')

def migrate_database():
    """Add symptoms column to appointments table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if symptoms column exists
        cursor.execute("PRAGMA table_info(appointments)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'symptoms' not in columns:
            print("Adding symptoms column to appointments table...")
            cursor.execute("ALTER TABLE appointments ADD COLUMN symptoms TEXT")
            conn.commit()
            print("✅ Symptoms column added successfully!")
        else:
            print("✅ Symptoms column already exists!")
            
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()

if __name__ == "__main__":
    migrate_database()