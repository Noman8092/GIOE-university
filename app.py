from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime
from datetime import date
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a strong secret


#-----------------------------------------------------Student Result Data connect with flask--------------------------------->

def fetch_result(roll, name):
    conn = sqlite3.connect('students.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE roll=? AND name=?", (roll, name))
    row = cursor.fetchone()
    conn.close()
    return row
 

# ------------------ Configuration ------------------
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if not exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ------------------ Helpers ------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# ------------------ Initialize DB ------------------


def add_missing_columns():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Get all existing column names from the 'students' table
    cursor.execute("PRAGMA table_info(students)")
    existing_columns = [column[1] for column in cursor.fetchall()]

    # Add 'last_login' column if not exists
    if 'last_login' not in existing_columns:
        cursor.execute("ALTER TABLE students ADD COLUMN last_login TEXT")
        print("✅ Added 'last_login' column")

    # Add 'discussion_status' column if not exists
    if 'discussion_status' not in existing_columns:
        cursor.execute("ALTER TABLE students ADD COLUMN discussion_status TEXT DEFAULT 'pending'")
        print("✅ Added 'discussion_status' column")

    conn.commit()
    conn.close()

add_missing_columns()

# ------------------ Public Routes ------------------
@app.route('/')
def home():
    return render_template("index1.html")

@app.route('/courses')
def view_courses():
    conn = get_db_connection()
    courses = conn.execute("SELECT * FROM courses").fetchall()
    conn.close()
    return render_template('courses.html', courses=courses)

#-------------------------------------------Don't show courses before  user login---------------------------------------------
@app.route('/course/<int:id>')
def course_detail(id):
    if not session.get('user_id'):
        flash("Please login to view full course details.", "warning")
        return redirect(url_for('login'))
    conn = get_db_connection()
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (id,)).fetchone()
    conn.close()
    return render_template("course_detail.html", course=course)



@app.route('/faculty')
def faculty():
    return render_template("faculty.html")

@app.route('/gallery')
def gallery():
    return render_template("gallery.html")

# ------------------ Student Registration & Login ------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        try:
            conn = get_db_connection()
            conn.execute("INSERT INTO students (name, email, password) VALUES (?, ?, ?)", 
                         (name, email, password))
            conn.commit()
            conn.close()
            flash("Registration successful!", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
            return redirect(url_for('register'))
    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password_input = request.form['password']

        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()

        if student and check_password_hash(student['password'], password_input):
            session['user_id'] = student['id']
            session['user_name'] = student['name']

            login_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("UPDATE students SET last_login = ? WHERE id = ?", (login_time, student['id']))
            conn.commit()
            conn.close()

            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials", "danger")
            conn.close()
            return redirect(url_for('login'))

    return render_template("login.html")

@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    courses = conn.execute("SELECT * FROM courses").fetchall()
    conn.close()

    return render_template("dashboard.html", name=session['user_name'], courses=courses)

@app.route('/generate_certificate')
def generate_certificate():
    if 'user_name' not in session:
        return redirect(url_for('login'))

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, height - 100, "Certificate of Completion")

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, height - 160, f"Awarded to: {session['user_name']}")

    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 200, "For successfully completing the course")

    date = datetime.now().strftime("%d %B %Y")
    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(width / 2, height - 240, f"Issued on: {date}")

    c.showPage()
    c.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="certificate.pdf", mimetype='application/pdf')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))


#---------------------------------------------To Veiw Students of results-------------------------------------------->

@app.route('/result', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        roll = request.form['roll']
        name = request.form['name']
        result = fetch_result(roll, name)
        if result:
            total = sum(result[3:])  # Sum all 8 subject marks
            student = {
                'roll': result[0],
                'name': result[1],
                'position': result[2],
                'subjects': result[3:],
                'total': total
            }
            return render_template('result.html', student=student)
        else:
            return "<h2>❌ نتیجہ نہیں ملا۔ براہ کرم نام اور رول نمبر درست درج کریں۔</h2><a href='/'>واپس جائیں</a>"
    return render_template('index.html')
 
    
# ------------------ Admin Routes ------------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "admin123":
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid admin credentials", "danger")
    return render_template("admin/admin_login.html")

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    courses = conn.execute("SELECT * FROM courses").fetchall()
    conn.close()
    return render_template("admin/admin_dashboard.html", courses=courses)

@app.route('/admin/add_course', methods=['GET', 'POST'])
def add_course():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        pdf_file = request.files['pdf']
        pdf_filename = ""

        if pdf_file and allowed_file(pdf_file.filename):
            filename = secure_filename(pdf_file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            pdf_file.save(path)
            pdf_filename = f"/{path}"

        conn = get_db_connection()
        conn.execute("INSERT INTO courses (title, description, pdf) VALUES (?, ?, ?)", 
                     (title, description, pdf_filename))
        conn.commit()
        conn.close()
        flash("Course added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template("admin/add_course.html")

@app.route('/admin/delete_course/<int:id>')
def delete_course(id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    conn.execute("DELETE FROM courses WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Course deleted!", "warning")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/students')
def view_students():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    query = "SELECT * FROM students WHERE 1=1"
    search = request.args.get('search')
    filter_date = request.args.get('date')
    discussion = request.args.get('discussion')

    params = []

    if search:
        query += " AND (name LIKE ? OR email LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    if filter_date:
        query += " AND date(last_login) = ?"
        params.append(filter_date)

    if discussion:
        query += " AND discussion_status = ?"
        params.append(discussion)

    conn = get_db_connection()
    students = conn.execute(query, params).fetchall()
    conn.close()

    return render_template("admin/view_students.html", students=students)


@app.route('/admin/mark_discussed/<int:id>')
def mark_discussed(id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    conn.execute("UPDATE students SET discussion_status = 'discussed' WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Marked as discussed", "success")
    return redirect(url_for('view_students'))

@app.route('/admin/delete_student/<int:id>')
def delete_student(id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    if session.get('user_id') == id:
        flash("Cannot delete an active student!", "danger")
        return redirect(url_for('view_students'))

    conn = get_db_connection()
    conn.execute("DELETE FROM students WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Student deleted!", "success")
    return redirect(url_for('view_students'))




@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash("Logged out from admin panel", "info")
    return redirect(url_for('admin_login'))

# ------------------ Run ------------------
if __name__ == '__main__':
    app.run(debug=True)
