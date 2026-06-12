import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secure_phc_secret_encryption_key'

# Configuration settings for Image Evidence uploads
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the static upload storage layer exists on machine initialization
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema and creates users and grievances tables."""
    conn = get_db_connection()
    # Users Credentials Storage Layer
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'client'))
        )
    ''')
    # Grievances Master Storage Layer
    conn.execute('''
        CREATE TABLE IF NOT EXISTS grievances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            patient_name TEXT NOT NULL,
            facility_name TEXT NOT NULL,
            department TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            image_filename TEXT,
            status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Under Investigation', 'Resolved')),
            admin_remarks TEXT DEFAULT '',
            FOREIGN KEY(client_id) REFERENCES users(id)
        )
    ''')
    # Generate default credential presets inside the system if tables are fresh
    try:
        conn.execute("INSERT INTO users (username, password, role) VALUES ('admin01', 'SemenHC@123', 'admin')")
        conn.execute("INSERT INTO users (username, password, role) VALUES ('patient01', 'patient123', 'client')")
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def allowed_file(filename):
    # Ensure there is a dot in the filename and check the extension safely
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Run database configuration checks instantly on boot script execution
init_db()

@app.route('/')
def index():
    return redirect(url_for('login'))

# --- AUTHENTICATION FLOWS ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('client_dashboard'))
        
        flash('Invalid verification credentials. Try again.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- CLIENT SUBMISSION MANAGEMENT ---
@app.route('/client', methods=['GET', 'POST'])
def client_dashboard():
    if 'user_id' not in session or session['role'] != 'client':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    if request.method == 'POST':
        patient_name = request.form['patient_name']
        facility_name = request.form['facility_name']
        department = request.form['department']
        category = request.form['category']
        description = request.form['description']
        
        # Binary multi-part stream image extraction
        filename = None
        if 'evidence_image' in request.files:
            file = request.files['evidence_image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"user_{session['user_id']}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn.execute('''
            INSERT INTO grievances (client_id, patient_name, facility_name, department, category, description, image_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], patient_name, facility_name, department, category, description, filename))
        conn.commit()
        flash('Grievance logged successfully into health network tracking.')

    my_cases = conn.execute('SELECT * FROM grievances WHERE client_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('client.html', grievances=my_cases)

# --- ADMIN CASE ASSESSMENT HUB ---
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    if request.method == 'POST':
        grievance_id = request.form['grievance_id']
        status = request.form['status']
        remarks = request.form['remarks']
        
        conn.execute('''
            UPDATE grievances SET status = ?, admin_remarks = ? WHERE id = ?
        ''', (status, remarks, grievance_id))
        conn.commit()
        flash(f'Case Record #{grievance_id} updated successfully.')

    all_cases = conn.execute('SELECT * FROM grievances ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin.html', grievances=all_cases)

if __name__ == '__main__':
    # Render routes traffic through a specific port automatically
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)