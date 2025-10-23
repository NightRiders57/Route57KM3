from flask import Flask, render_template, request, redirect, send_file
from pymongo import MongoClient
from bson.objectid import ObjectId
import gridfs
from io import BytesIO
import datetime
import qrcode

app = Flask(__name__, template_folder='templates', static_folder='static')

# --- MongoDB Atlas ---
MONGO_URI = "mongodb+srv://francescofittaiolo_db_user:Chloe16@cluster0.nrsedvh.mongodb.net/nightriders?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.nightriders
fs = gridfs.GridFS(db)
iscrizioni_col = db.iscrizioni

# --- Routes ---
@app.route('/invia', methods=['POST'])
def invia():
    nome = request.form['nome']
    cognome = request.form['cognome']
    cellulare = request.form['cellulare']
    email = request.form['email']
    auto = request.form['auto']
    club = request.form.get('club', '')
    clubs = request.form['clubs']
    passeggeri = request.form['passeggeri']
    brioches = request.form['brioches']
    intolleranze = request.form.get('intolleranze', '')

    # --- Salva le foto in GridFS ---
    foto1_file = request.files['foto1']
    foto2_file = request.files['foto2']
    foto1_id = fs.put(foto1_file, filename=f"foto1_{nome}_{cognome}")
    foto2_id = fs.put(foto2_file, filename=f"foto2_{nome}_{cognome}")

    # --- Salva i dati nel database (senza QR per ora) ---
    result = iscrizioni_col.insert_one({
        "nome": nome,
        "cognome": cognome,
        "cellulare": cellulare,
        "email": email,
        "auto": auto,
        "club": club,
        "clubs": clubs,
        "passeggeri": passeggeri,
        "brioches": brioches,
        "intolleranze": intolleranze,
        "foto1_id": foto1_id,
        "foto2_id": foto2_id,
        "timestamp": datetime.datetime.now()
    })

    # --- Prendi l'_id generato da MongoDB ---
    iscrizione_id = str(result.inserted_id)

    # --- Genera codice QR con URL che include l'_id ---
    qr_data = f"https://route57km3.onrender.com/biglietto/{iscrizione_id}"
    qr_img = qrcode.make(qr_data)
    qr_bytes = BytesIO()
    qr_img.save(qr_bytes, format="PNG")
    qr_bytes.seek(0)
    qr_id = fs.put(qr_bytes, filename=f"QR_{nome}_{cognome}.png")

    # --- Aggiorna documento con qr_id ---
    iscrizioni_col.update_one(
        {"_id": result.inserted_id},
        {"$set": {"qr_id": qr_id}}
    )

    messaggio = f"Ciao {nome}, la tua iscrizione all’evento NIGHT RIDERS ROUTE KM3 è stata ricevuta! Ti aspettiamo 🤘"
    return render_template('conferma.html', nome=nome, messaggio=messaggio)

# --- Mostra iscritti (con password semplice) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == "Nightriders2025":  # Cambia con la password che vuoi
            iscritti = list(iscrizioni_col.find())
            return render_template('iscritti.html', iscritti=iscritti)
        else:
            return "Password errata", 401
    return render_template('login.html')

# --- Serve le foto da GridFS ---
@app.route('/foto/<file_id>')
def mostra_foto(file_id):
    file = fs.get(ObjectId(file_id))
    return send_file(BytesIO(file.read()), mimetype='image/jpeg')

# --- Serve i QR code ---
@app.route('/qr/<file_id>')
def mostra_qr(file_id):
    file = fs.get(ObjectId(file_id))
    return send_file(BytesIO(file.read()), mimetype='image/png')

@app.route('/biglietto/<id_iscrizione>')
def biglietto(id_iscrizione):
    iscrizione = iscrizioni_col.find_one({"_id": ObjectId(id_iscrizione)})
    if not iscrizione:
        return "Biglietto non trovato", 404
    return render_template('biglietto.html', iscrizione=iscrizione)

# --- Main ---
if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)






