from flask import Flask, render_template, request, redirect, send_file
from pymongo import MongoClient
from bson.objectid import ObjectId
import gridfs
import io
from io import BytesIO
from PIL import Image
import datetime
import qrcode

app = Flask(__name__, template_folder='templates', static_folder='static')

# --- MongoDB Atlas ---
MONGO_URI = "mongodb+srv://francescofittaiolo_db_user:Chloe16@cluster0.nrsedvh.mongodb.net/nightriders?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.nightriders
fs = gridfs.GridFS(db)
iscrizioni_col = db.iscrizioni


# ✅ funzione correttamente fuori dalla route
def salva_immagine_ridotta(file, nome, cognome):
    img = Image.open(file)

    max_size = 1280
    img.thumbnail((max_size, max_size))

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=70, optimize=True)
    buffer.seek(0)

    return fs.put(buffer, filename=f"foto_{nome}_{cognome}.jpg")


@app.route('/')
def index():
    return render_template('index.html')


# --- Routes ---
@app.route('/invia', methods=['POST'])
def invia():
    nome = request.form['nome']
    cognome = request.form['cognome']
    cellulare = request.form['cellulare']
    email = request.form['email']
    auto = request.form['auto']
    targa = request.form['targa']
    club = request.form.get('club', '')
    clubs = request.form['clubs']

    # ✅ correttamente dentro la funzione
    foto1_file = request.files['foto1']
    foto2_file = request.files['foto2']

    foto1_id = salva_immagine_ridotta(foto1_file, nome, cognome)
    foto2_id = salva_immagine_ridotta(foto2_file, nome, cognome)

    result = iscrizioni_col.insert_one({
        "nome": nome,
        "cognome": cognome,
        "cellulare": cellulare,
        "email": email,
        "auto": auto,
        "targa": targa,
        "club": club,
        "clubs": clubs,
        "foto1_id": foto1_id,
        "foto2_id": foto2_id,
        "checkin": False,
        "stato_whatsapp": None,
        "timestamp": datetime.datetime.now()
    })

    # --- Prendi l'_id generato da MongoDB ---
    iscrizione_id = str(result.inserted_id)

    # --- Genera QR + locandina ---
    qr_data = f"https://route57km3.onrender.com/biglietto/{iscrizione_id}"

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # ✅ Carica locandina (assicurati che sia in /static/img/)
    poster = Image.open("static/img/locandina.png")

    # ✅ Mantiene locandina a 500x300
    poster = poster.resize((500, 300))

    # ✅ Ridimensiona il QR (puoi aumentare o diminuire)
    qr_size = 180
    qr_img = qr_img.resize((qr_size, qr_size))

    # ✅ Posizione BASSO DESTRA
    margin = 10
    x = poster.width - qr_img.width - margin
    y = poster.height - qr_img.height - margin

    poster.paste(qr_img, (x, y))

    # ✅ Salva in GridFS
    qr_bytes = BytesIO()
    poster.save(qr_bytes, format="PNG")
    qr_bytes.seek(0)

    qr_id = fs.put(qr_bytes, filename=f"QR_{nome}_{cognome}.png")

    # ✅ Aggiorna documento Mongo con qr_id
    iscrizioni_col.update_one(
        {"_id": result.inserted_id},
        {"$set": {"qr_id": qr_id}}
    )

    messaggio = f"Ciao {nome}, la tua iscrizione all’evento NOVEMBER RIDERS è stata ricevuta! 🤘"
    return render_template('conferma.html', nome=nome, messaggio=messaggio)


# --- Mostra iscritti (con password semplice) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == "Nightriders2025":
            iscritti = list(iscrizioni_col.find())
            return render_template('iscritti.html', iscritti=iscritti)
        else:
            return "Password errata", 401
    return render_template('login.html')


@app.route('/foto/<file_id>')
def mostra_foto(file_id):
    file = fs.get(ObjectId(file_id))
    return send_file(BytesIO(file.read()), mimetype='image/jpeg')


@app.route('/qr/<file_id>')
def mostra_qr(file_id):
    file = fs.get(ObjectId(file_id))
    return send_file(BytesIO(file.read()), mimetype='image/png')


@app.route('/biglietto/<id_iscrizione>')
def biglietto(id_iscrizione):
    try:
        obj_id = ObjectId(id_iscrizione)
    except Exception:
        return "ID non valido", 400

    try:
        result = iscrizioni_col.find_one_and_update(
            {"_id": obj_id},
            {"$set": {"checkin": True}},
            return_document=True
        )
    except Exception as e:
        print("Errore aggiornamento checkin:", e)
        return "Errore interno", 500

    if not result:
        return "Biglietto non trovato", 404

    return render_template('biglietto.html', iscrizione=result)


@app.route('/aggiorna_whatsapp/<id_iscrizione>', methods=['POST'])
def aggiorna_whatsapp(id_iscrizione):
    tipo = request.args.get('tipo')
    if tipo not in ["accetta", "rifiuta"]:
        return "Tipo non valido", 400

    try:
        obj_id = ObjectId(id_iscrizione)
        field = "whatsapp_accettato" if tipo == "accetta" else "whatsapp_rifiutato"
        iscrizioni_col.update_one({"_id": obj_id}, {"$set": {field: True}})
        return "OK", 200
    except Exception as e:
        print("Errore aggiornamento whatsapp:", e)
        return "Errore", 500


@app.route('/reset_db', methods=['POST'])
def reset_db():
    password = request.form.get("password_reset", "")
    if password != "Nightriders2025":
        return "Accesso negato", 403

    try:
        iscrizioni_col.drop()
        db.fs.files.drop()
        db.fs.chunks.drop()
        return "✅ Database completamente resettato!"
    except Exception as e:
        print("ERRORE RESET:", e)
        return "Errore reset database", 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)