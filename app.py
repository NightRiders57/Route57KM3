from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
import os, datetime
from werkzeug.utils import secure_filename
from functools import wraps

# ---------------- CONFIG ----------------
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY"

BASE_UPLOAD_FOLDER = "uploads"
os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)

# MongoDB Atlas
MONGO_URI = "mongodb+srv://user:password@cluster.mongodb.net/nightriders?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client.nightriders
iscrizioni_col = db.iscrizioni

# Password per accedere a /iscritti
ADMIN_PASSWORD = "night123"

# ---------------- DECORATOR PER LOGIN ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ---------------- ROUTE ----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/invia', methods=['POST'])
def invia():
    # --- DATI FORM ---
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

    # --- CREA CARTELLA PER FOTO ---
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    folder_name = os.path.join(BASE_UPLOAD_FOLDER, f"{timestamp}_{secure_filename(nome+''+cognome)}")
    os.makedirs(folder_name, exist_ok=True)

    foto1 = request.files['foto1']
    foto2 = request.files['foto2']
    foto1_filename = os.path.join(folder_name, secure_filename(foto1.filename))
    foto2_filename = os.path.join(folder_name, secure_filename(foto2.filename))
    foto1.save(foto1_filename)
    foto2.save(foto2_filename)

    # --- SALVA NEL DATABASE ---
    dati_iscrizione = {
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
        "foto1": foto1_filename,
        "foto2": foto2_filename,
        "timestamp": datetime.datetime.now()
    }
    iscrizioni_col.insert_one(dati_iscrizione)

    # --- CONFERMA ALL'UTENTE ---
    messaggio = f"Ciao {nome}, la tua iscrizione all’evento NIGHT RIDERS ROUTE KM3 è stata ricevuta! Ti aspettiamo 🤘"
    return render_template('conferma.html', nome=nome, messaggio=messaggio)

# ---------------- LOGIN ADMIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('iscritti'))
        else:
            return render_template('login.html', errore="Password sbagliata")
    return render_template('login.html')

# ---------------- PAGINA ISCRITTI ----------------
@app.route('/iscritti')
@login_required
def iscritti():
    tutti = list(iscrizioni_col.find().sort("timestamp", -1))
    return render_template('iscritti.html', iscrizioni=tutti)

# ---------------- LOGOUT ----------------
@app.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# ---------------- MAIN ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



