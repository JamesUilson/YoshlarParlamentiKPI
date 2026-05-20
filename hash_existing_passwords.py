# hash_existing_passwords.py
import sqlite3
from werkzeug.security import generate_password_hash

def hash_existing_plain_passwords():
    """Mavjud plain text parollarni hash qilish"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Hash qilinmagan (qisqa) parolli foydalanuvchilarni topish
    cursor.execute("SELECT user_id, password FROM users WHERE LENGTH(password) < 50")
    users = cursor.fetchall()
    
    print(f"🔍 {len(users)} ta foydalanuvchi paroli hash qilinmagan")
    
    updated = 0
    for user_id, plain_password in users:
        if plain_password and len(plain_password) < 50:
            # Hash qilish
            hashed = generate_password_hash(plain_password)
            
            # Yangilash
            cursor.execute("UPDATE users SET password = ? WHERE user_id = ?", 
                          (hashed, user_id))
            
            updated += 1
            print(f"  🔄 {user_id}: '{plain_password}' -> hash qilindi")
    
    conn.commit()
    
    # Tekshirish
    cursor.execute("SELECT COUNT(*) FROM users WHERE LENGTH(password) < 50")
    remaining = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n✅ {updated} ta parol hash qilindi")
    print(f"📊 Qolgan plain text parollar: {remaining} ta")
    
    return updated

if __name__ == '__main__':
    hash_existing_plain_passwords()