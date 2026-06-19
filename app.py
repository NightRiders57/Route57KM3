from flask import Flask, render_template, request, redirect, send_file
from pymongo import MongoClient
from bson.objectid import ObjectId
from openpyxl import Workbook
import gridfs
import io
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
import datetime
import qrcode
import requests

register_heif_opener()

app = Flask(__name__, template_folder='templates', static_folder='static')

# --- MongoDB Atlas ---
MONGO_URI = "mongodb+srv://francescofittaiolo_db_user:Chloe16@cluster0.nrsedvh.mongodb.net/nightriders?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.nightriders
fs = gridfs.GridFS(db)
iscrizioni_col = db.iscrizioni
TELEGRAM_TOKEN = "8910850640:AAFZb5KlkUYfmoDo6alZlam-tidwLYxGWgw"
TELEGRAM_CHAT_ID = "1233257009"


# ✅ funzione correttamente fuori dalla route
def salva_immagine_ridotta(file, nome, cognome):
    try:
        img = Image.open(file)
        img.load()
    except UnidentifiedImageError:
            raise Exception(
            "Formato immagine non supportato. "
            "Ridimensiona oppure carica uno screen dell'immagine."
        )

    max_size = 1280
    img.thumbnail((max_size, max_size))

    if img.mode != "RGB":
        img = img.convert("RGB")

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=70, optimize=True)
    buffer.seek(0)

    return fs.put(buffer, filename=f"foto_{nome}_{cognome}.jpg")

# FUNZIONE PER BOT TELEGRAM
def invia_notifica_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": messaggio
    }

    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Errore Telegram:", e)

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
    targa = request.form['targa'].strip().upper()
    intolleranze = request.form.get('intolleranze', '')
    passeggeri = request.form['passeggeri']
    andatura = request.form.get('andatura', '')
    instagram = request.form['instagram']

    # ✅ correttamente dentro la funzione
    foto1_file = request.files['foto1']
    foto2_file = request.files['foto2']

    try:
        foto1_id = salva_immagine_ridotta(foto1_file, nome, cognome)
        foto2_id = salva_immagine_ridotta(foto2_file, nome, cognome)

    except Exception as e:
        return str(e), 400

    targa_esistente = iscrizioni_col.find_one({"targa": targa.upper()})
    
    if targa_esistente:
        return render_template('errore_gia_iscritto.html', messaggio="La targa inserita è già associata a un'iscrizione. Verrai presto ricontattato.")
    
    result = iscrizioni_col.insert_one({
        "nome": nome,
        "cognome": cognome,
        "cellulare": cellulare,
        "email": email,
        "auto": auto,
        "targa": targa,
        "intolleranze": intolleranze,
        "passeggeri": passeggeri,
        "andatura": andatura,
        "instagram": instagram,
        "foto1_id": foto1_id,
        "foto2_id": foto2_id,
        "checkin": False,
        "stato_whatsapp": None,
        "pagato": False,
        "sconti": 0,
        "importo_pagato": 0.0,
        "timestamp": datetime.datetime.now()
    })
        
        

    messaggio_telegram = (
    f"🔥 NUOVA ISCRIZIONE 🔥\n\n"
    f"👤 {nome} {cognome}\n"
    f"🚗 {auto}\n"
    f"🔢 {targa}\n"
    f"👥 Passeggeri: {passeggeri}\n"
    f"📱 @{instagram}"
    )

    invia_notifica_telegram(messaggio_telegram)



    iscrizione_id = str(result.inserted_id)

    qr_data = f"https://route57km3.onrender.com/checkin/{iscrizione_id}"
    qr_img = qrcode.make(qr_data)
    qr_bytes = BytesIO()
    qr_img.save(qr_bytes, format="PNG")
    qr_bytes.seek(0)
    qr_id = fs.put(qr_bytes, filename=f"QR_{nome}_{cognome}.png")

    iscrizioni_col.update_one(
        {"_id": result.inserted_id},
        {"$set": {"qr_id": qr_id}}
    )

    messaggio = f"Ciao {nome}, la tua iscrizione all’evento Route57 KM.3 è stata ricevuta! 🤘"
    return render_template('conferma.html', nome=nome, messaggio=messaggio)
    

    

# --- Mostra iscritti (con password semplice) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == "Nightriders2026":
            iscritti = list(iscrizioni_col.find())

            totale = len(iscritti)
            checkin_effettuati = sum(1 for i in iscritti if i.get("checkin"))
            totale_accettati = sum(1 for i in iscritti if i.get("whatsapp_accettato"))
            totale_rifiutati = sum(1 for i in iscritti if i.get("whatsapp_rifiutato"))
            totale_passeggeri = sum(
                int(i.get("passeggeri",1)) 
                for i in iscritti
                if i.get("pagato")
                )
            totale_pagamenti = sum(1 for i in iscritti if i.get("pagato"))
            
            incasso_totale = 0

            for i in iscritti:
                if not i.get("pagato"):
                    continue

                importo = i.get("importo_pagato")

                if importo in [None, "", 0]:
                    passeggeri = int(i.get("passeggeri", 1))
                    importo = passeggeri * 42

                incasso_totale += float(importo)
            
            totale_attesa = sum(1 for i in iscritti if not i.get("whatsapp_accettato") and not i.get("whatsapp_rifiutato"))

            totale_ristorante = 0
            for iscrizione in iscritti:
                if iscrizione.get("pagato", False):
                    totale_ristorante += int(iscrizione.get("passeggeri",0)) * 35

            guadagno_totale = incasso_totale - totale_ristorante

            return render_template('iscritti.html',iscritti=iscritti, totale=totale, checkin_effettuati=checkin_effettuati, totale_accettati=totale_accettati, totale_rifiutati=totale_rifiutati, totale_passeggeri=totale_passeggeri, totale_pagamenti=totale_pagamenti, incasso_totale=incasso_totale, totale_attesa=totale_attesa, guadagno_totale=guadagno_totale, totale_ristorante=totale_ristorante)
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

    #  Recupero il documento
    iscrizione = iscrizioni_col.find_one({"_id": obj_id})

    if not iscrizione:
        return "Biglietto non trovato", 404

    #  SE È GIÀ SCANSIONATO → MOSTRA LA PAGINA DEDICATA
    #if iscrizione.get("checkin") == True:
    #    return render_template("gia_scansionato.html", iscrizione=iscrizione)

    #  ALTRIMENTI aggiorno checkin a True (prima scansione)
    #try:
    #    iscrizioni_col.update_one(
    #        {"_id": obj_id},
    #        {"$set": {"checkin": True}}
    #    )
    #except Exception as e:
    #    print("Errore aggiornamento checkin:", e)
    #    return "Errore interno", 500

    #  Mostro il biglietto
    return render_template('biglietto.html', iscrizione=iscrizione)

@app.route('/checkin/<id_iscrizione>')
def checkin(id_iscrizione):
    try:
        obj_id = ObjectId(id_iscrizione)
    except:
        return "ID non valido", 400

    iscrizione = iscrizioni_col.find_one({"_id": obj_id})
    if not iscrizione:
        return "Biglietto non trovato", 404
    
    # 🚫 pagamento mancante
    if not iscrizione.get("pagato", False):
        return render_template("pagamento_mancante.html", iscrizione=iscrizione)

    # 🚫 già scansionato
    if iscrizione.get("checkin") is True:
        return render_template("gia_scansionato.html", iscrizione=iscrizione)

    # ✅ primo check-in
    iscrizioni_col.update_one(
        {"_id": obj_id},
        {"$set": {"checkin": True, "checkin_time": datetime.datetime.now()}}
    )

    return render_template("checkin_ok.html", iscrizione=iscrizione)


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
    if password != "Nightriders2026":
        return "Accesso negato", 403

    try:
        iscrizioni_col.drop()
        db.fs.files.drop()
        db.fs.chunks.drop()
        return "✅ Database completamente resettato!"
    except Exception as e:
        print("ERRORE RESET:", e)
        return "Errore reset database", 500
    
@app.route('/export_checkin')
def export_checkin():
    # Preleva solo gli utenti con check-in effettuato
    iscritti = list(iscrizioni_col.find({"checkin": True}))

    # Crea un file Excel in memoria
    wb = Workbook()
    ws = wb.active
    ws.title = "Check-in"

    # Intestazioni colonne
    ws.append(["Nome", "Cognome", "Email", "Cellulare", "Auto", "Targa", "Intolleranze"])

    # Inserimento dati
    for i in iscritti:
        ws.append([
            i.get("nome", ""),
            i.get("cognome", ""),
            i.get("email", ""),
            i.get("cellulare", ""),
            i.get("auto", ""),
            i.get("targa", ""),
            i.get("intolleranze", "")
        ])

    # Salva il file in memoria
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    # Invia il file al browser per il download
    return send_file(
        file_stream,
        as_attachment=True,
        download_name="checkin.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )    

@app.route('/export_iscrizioni')
def export_iscrizioni():
    
    iscritti = list(iscrizioni_col.find({
        "pagato": True
    }))
    # Crea un file Excel in memoria
    wb = Workbook()
    ws = wb.active
    ws.title = "Iscrizioni"

    # Intestazioni colonne
    ws.append(["Nome", "Cognome", "Cellulare", "Auto", "Targa", "Intolleranze", "Passeggeri", "Andatura"])

    # Inserimento dati
    for i in iscritti:
        ws.append([
            i.get("nome", ""),
            i.get("cognome", ""),
            i.get("cellulare", ""),
            i.get("auto", ""),
            i.get("targa", ""),
            i.get("intolleranze", ""),
            i.get("passeggeri", ""),
            i.get("andatura", "")
        ])

    # Salva il file in memoria
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    # Invia il file al browser per il download
    return send_file(
        file_stream,
        as_attachment=True,
        download_name="iscrizioni.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )   

@app.route('/toggle_pagato/<id_iscrizione>', methods=['POST'])
def toggle_pagato(id_iscrizione):
    try:
        obj_id = ObjectId(id_iscrizione)

        iscrizione = iscrizioni_col.find_one({"_id": obj_id})

        nuovo_stato = not iscrizione.get("pagato", False)

        iscrizioni_col.update_one(
            {"_id": obj_id},
            {"$set": {"pagato": nuovo_stato}}
        )

        return "OK", 200

    except Exception as e:
        print(e)
        return "Errore", 500
    
@app.route('/update_sconti/<id_iscrizione>', methods=['POST'])
def update_sconti(id_iscrizione):

    try:
        obj_id = ObjectId(id_iscrizione)

        sconti = int(request.args.get("sconti", 0))

        iscrizioni_col.update_one(
            {"_id": obj_id},
            {"$set": {"sconti": sconti}}
        )

        return "OK", 200

    except Exception as e:
        print("Errore update sconti:", e)
        return "Errore", 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)