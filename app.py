from flask import Flask, render_template, request, redirect
import csv, os, datetime

app = Flask(__name__, template_folder='templates', static_folder='static')
BASE_UPLOAD_FOLDER = "uploads"
os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

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

    # Genera cartella unica per l'iscrizione
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    folder_name = f"{BASE_UPLOAD_FOLDER}/{timestamp}{nome}{cognome}"
    os.makedirs(folder_name, exist_ok=True)

    # Salva le foto dentro la cartella
    foto1 = request.files['foto1']
    foto2 = request.files['foto2']
    foto1.save(os.path.join(folder_name, 'foto1.jpg'))
    foto2.save(os.path.join(folder_name, 'foto2.jpg'))

    # Salva i dati in CSV verticale dentro la cartella dell'iscrizione
    dati_file = os.path.join(folder_name, 'dati.csv')
    with open(dati_file, 'w', encoding='utf-8') as file:
        file.write(f"Data iscrizione: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        file.write(f"Nome: {nome}\n")
        file.write(f"Cognome: {cognome}\n")
        file.write(f"Cellulare: {cellulare}\n")
        file.write(f"Email: {email}\n")
        file.write(f"Auto: {auto}\n")
        file.write(f"Club: {club}\n")
        file.write(f"Clubs: {clubs}\n")
        file.write(f"Passeggeri: {passeggeri}\n")
        file.write(f"Brioches: {brioches}\n")
        file.write(f"Intolleranze: {intolleranze}\n")

    # Messaggio di conferma
    messaggio = f"Ciao {nome}, la tua iscrizione all’evento NIGHT RIDERS ROUTE KM3 è stata ricevuta! Ti aspettiamo 🤘"

    return render_template('conferma.html', nome=nome, messaggio=messaggio)

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

