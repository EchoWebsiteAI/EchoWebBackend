import os
import json
import sqlite3
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Muat environment variables dari file .env
load_dotenv()

# Konfigurasi Flask App
app = Flask(__name__)
CORS(app) # Mengizinkan akses dari domain lain (frontend)

# Konfigurasi Google Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY tidak ditemukan. Pastikan ada di file .env")
genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name='gemini-2.5-flash')

DATABASE = 'chat_history.db'

# Fungsi bantuan untuk koneksi ke database
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

SYSTEM_PROMPT = """
[AWAL DARI SYSTEM PROMPT]
Peran & Persona:
Kamu adalah "Echo", seorang sahabat virtual. Peranmu adalah menjadi pendengar yang baik, empatik, hangat, dan suportif. Tujuan utamamu adalah untuk membuat pengguna merasa didengar, dimengerti, divalidasi perasaannya, dan tidak sendirian. Kamu hadir untuk mendengarkan keluh kesah tanpa menghakimi.

Aturan Perilaku & Interaksi:
- Validasi Emosi: Selalu validasi perasaan pengguna. Gunakan frasa seperti "Aku mengerti itu pasti terasa berat," "Wajar sekali kamu merasa seperti itu," atau "Terima kasih sudah berbagi denganku."
- Ajukan Pertanyaan Terbuka: Dorong pengguna untuk bercerita lebih lanjut dengan pertanyaan terbuka yang reflektif. Contoh: "Apa yang paling kamu rasakan saat itu terjadi?", "Bagaimana perasaanmu sekarang?". **Hindari pertanyaan yang mengarahkan pada solusi atau tindakan di masa depan. Fokuskan pertanyaan untuk mendalami apa yang dirasakan atau dialami pengguna saat ini atau di masa lalu.**
- Fokus pada Pengguna: Jangan pernah membicarakan dirimu sendiri sebagai AI. Jaga agar fokus percakapan selalu pada pengguna dan perasaannya.
- Gunakan Riwayat Percakapan: Manfaatkan informasi dari riwayat chat untuk menunjukkan bahwa kamu mengingatnya. Contoh: "Tadi kamu sempat cerita tentang pekerjaan yang menumpuk, apakah itu yang membuatmu sulit tidur sekarang?".
- Jaga Respon Singkat & Padat: Usahakan jawabanmu tetap singkat dan terasa natural seperti percakapan (idealnya 2-5 kalimat). Namun, **jangan korbankan konteks atau empati demi keringkasan**.

Batasan & Hal yang Dilarang Keras (Guardrails):
- JANGAN MEMBERIKAN NASIHAT: Kamu bukan seorang terapis atau profesional. Jangan pernah memberikan nasihat konkret.
- JANGAN MENGHAKIMI: Apapun yang diceritakan pengguna, terima tanpa penilaian.
- JANGAN MENDIAGNOSIS: Kamu dilarang keras mendiagnosis kondisi kesehatan mental atau masalah medis apapun.
- TANGANI TOPIK KRISIS DENGAN HATI-HATI: Jika pengguna mengungkapkan pikiran untuk menyakiti diri sendiri, respon dengan tenang, tunjukkan kepedulian mendalam, dan dengan lembut sarankan untuk berbicara dengan seorang profesional.

Gaya Bahasa & Nada Bicara:
Gunakan bahasa Indonesia yang santai, modern, dan manusiawi. Sapaan "kamu". Nada bicara harus selalu tenang, hangat, dan **menenangkan**.
Hindari bahasa yang terlalu formal, teknis, atau kaku. Jangan gunakan jargon psikologi atau istilah klinis.
Apabila pengguna menggunakan bahasa gaul atau santai, sesuaikan gaya bahasamu agar terasa lebih akrab dan relatable.
Apabila pengguna menggunakan bahasa inggris, balaskan dengan bahasa inggris dan sesuaikan gaya bahasa agar tetap santai dan akrab.
[AKHIR DARI SYSTEM PROMPT]
"""

# === API ENDPOINTS ===

# [READ & DELETE] Endpoint GABUNGAN untuk mengambil atau menghapus chat
@app.route('/api/chat/<int:chat_id>', methods=['GET', 'DELETE'])
def handle_specific_chat(chat_id):
    conn = get_db_connection()
    
    # Jika metodenya adalah GET, ambil data pesan
    if request.method == 'GET':
        chat = conn.execute('SELECT messages FROM conversations WHERE id = ?', (chat_id,)).fetchone()
        conn.close()
        if chat is None:
            return jsonify({"error": "Chat not found"}), 404
        return jsonify(json.loads(chat['messages']))

    # Jika metodenya adalah DELETE, hapus chat
    elif request.method == 'DELETE':
        conn.execute('DELETE FROM conversations WHERE id = ?', (chat_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Chat deleted successfully"})

# [UPDATE & CREATE] Endpoint utama untuk berinteraksi dengan AI
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message')
    chat_id = data.get('chat_id')

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    conn = get_db_connection()
    
    try:
        # Jika chat_id ada, berarti ini adalah percakapan lanjutan
        if chat_id:
            # Ambil histori pesan dari database
            db_chat = conn.execute('SELECT messages FROM conversations WHERE id = ?', (chat_id,)).fetchone()
            if not db_chat:
                return jsonify({"error": "Chat not found"}), 404
            
            history = json.loads(db_chat['messages'])
            
        # Jika chat_id tidak ada, ini adalah percakapan baru
        else:
            history = []

        # Kirim pesan ke Gemini AI
        chat_session = model.start_chat(history=history)
        response = chat_session.send_message(user_message)
        ai_response_text = response.text

        # Update histori dengan pesan baru
        # Format Gemini: {'role': 'user'/'model', 'parts': [text]}
        new_history = chat_session.history
        messages_json = json.dumps([{'role': msg.role, 'parts': [p.text for p in msg.parts]} for msg in new_history])

        # Simpan kembali ke database
        if chat_id:
            # UPDATE chat yang sudah ada
            conn.execute('UPDATE conversations SET messages = ? WHERE id = ?', (messages_json, chat_id))
            new_chat_id = chat_id
        else:
            # CREATE chat baru
            title = user_message[:30] + '...' if len(user_message) > 30 else user_message
            cursor = conn.execute('INSERT INTO conversations (title, messages) VALUES (?, ?)', (title, messages_json))
            new_chat_id = cursor.lastrowid # Dapatkan ID dari chat yang baru dibuat
        
        conn.commit()

        return jsonify({"ai_response": ai_response_text, "chat_id": new_chat_id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


if __name__ == '__main__':
    # Pastikan database diinisialisasi sebelum server berjalan
    from database import init_db
    init_db()
    # Jalankan server Flask
    app.run(debug=True, port=5000)