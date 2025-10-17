# database.py
import sqlite3

def init_db():
    # Membuat atau menghubungkan ke file database bernama chat_history.db
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    # Membuat tabel 'conversations' jika belum ada
    # - id: Nomor unik untuk setiap chat
    # - title: Judul chat untuk ditampilkan di sidebar
    # - messages: Seluruh isi percakapan (user dan AI) disimpan sebagai teks JSON
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            messages TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()