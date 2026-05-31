from flask import Flask, render_template,request,redirect,session
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename

import config
import os

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

mysql = MySQL(app)

# ---------------- Citizen Routes ----------------

@app.route('/')
def home():
    return render_template('index.html')

# Register
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name=request.form['name']
        email=request.form['email']
        phone=request.form['phone']
        password=request.form['password']

        cur=mysql.connection.cursor()
        cur.execute("INSERT INTO users(name,email,phone,password) VALUES(%s,%s,%s,%s)",
                    (name,email,phone,password))
        mysql.connection.commit()

        return redirect('/login')

    return render_template('citizen/register.html')

# Login
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':

        email=request.form['email']
        password=request.form['password']

        cur=mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s AND password=%s",(email,password))
        user=cur.fetchone()

        if user:
            session['user']=user[0]
            return redirect('/dashboard')

    return render_template('citizen/login.html')

# Dashboard
# ---------------- Citizen Dashboard ----------------

@app.route('/dashboard')
def dashboard():

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    # total complaints
    cur.execute("SELECT COUNT(*) FROM complaints WHERE user_id=%s",
                (session['user'],))
    total = cur.fetchone()[0]

    # pending complaints
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending' AND user_id=%s",
                (session['user'],))
    pending = cur.fetchone()[0]

    # resolved complaints
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved' AND user_id=%s",
                (session['user'],))
    resolved = cur.fetchone()[0]

    # latest complaints
    cur.execute("""
        SELECT id,title,category,status,created_at
        FROM complaints
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """,(session['user'],))

    complaints_list = cur.fetchall()

    return render_template(
        'citizen/dashboard.html',
        total=total,
        pending=pending,
        resolved=resolved,
        complaints=complaints_list
    )

# Report Problem
@app.route('/report', methods=['GET','POST'])
def report():

    if request.method == 'POST':

        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        location = request.form['location']

        file = request.files['image']
        filename = secure_filename(file.filename)

        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)

        cur = mysql.connection.cursor()

        # get user name using session user id
        cur.execute("SELECT name FROM users WHERE id=%s", (session['user'],))
        user = cur.fetchone()
        user_name = user[0]

        # insert complaint
        cur.execute("""
        INSERT INTO complaints
        (user_id, user_name, title, description, category, location, image)
        VALUES(%s,%s,%s,%s,%s,%s,%s)
        """,
        (session['user'], user_name, title, description, category, location, filename))

        mysql.connection.commit()

        return redirect('/complaints')

    return render_template('citizen/report_problem.html')

# My complaints
@app.route('/complaints')
def complaints():

    cur=mysql.connection.cursor()
    cur.execute("SELECT * FROM complaints WHERE user_id=%s",(session['user'],))
    data=cur.fetchall()

    return render_template('citizen/my_complaints.html',data=data)

# Complaint Details
# ---------------- Complaint Details ----------------

@app.route('/complaint/<int:complaint_id>')
def complaint_details(complaint_id):

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id,title,description,category,location,image,
               status,department,created_at,status_note
        FROM complaints
        WHERE id=%s AND user_id=%s
    """,(complaint_id,session['user']))

    complaint = cur.fetchone()

    if not complaint:
        return "Complaint not found"

    return render_template(
        'citizen/complaint_details.html',
        complaint=complaint
    )

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('../')

# ---------------- ADMIN ----------------

# ---------------- Admin Login ----------------

@app.route('/admin', methods=['GET','POST'])
def admin_login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT * FROM admin
            WHERE username=%s AND password=%s
        """,(username,password))

        admin = cur.fetchone()

        if admin:
            session['admin'] = admin[0]
            return redirect('/admin/dashboard')
        else:
            error = "Invalid Username or Password"
            return render_template(
                'admin/admin_login.html',
                error=error
            )

    return render_template('admin/admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():

    cur = mysql.connection.cursor()

    # Total complaints
    cur.execute("SELECT COUNT(*) FROM complaints")
    total = cur.fetchone()[0]

    # Pending complaints
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
    pending = cur.fetchone()[0]

    # Resolved complaints
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'")
    resolved = cur.fetchone()[0]

    # Department count
    cur.execute("SELECT COUNT(*) FROM departments")
    departments = cur.fetchone()[0]

    # Recent complaints
    cur.execute("""
        SELECT id, title, category, status, created_at
        FROM complaints
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_complaints = cur.fetchall()

    return render_template(
        'admin/dashboard.html',
        total=total,
        pending=pending,
        resolved=resolved,
        departments=departments,
        recent_complaints=recent_complaints
    )

# Manage complaints
@app.route('/admin/complaints')
def manage_complaints():

    # check admin login
    if 'admin' not in session:
        return redirect('/admin')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, user_name, category, status
        FROM complaints
        ORDER BY id DESC
    """)

    complaints_list = cur.fetchall()

    return render_template(
        'admin/manage_complaints.html',
        complaints=complaints_list
    )

# Update status
@app.route('/admin/update/<int:complaint_id>', methods=['GET','POST'])
def update_status(complaint_id):

    if 'admin' not in session:
        return redirect('/admin')

    cur = mysql.connection.cursor()

    if request.method == 'POST':

        status = request.form['status']
        note = request.form['status_note']

        cur.execute("""
        UPDATE complaints
        SET status=%s, status_note=%s
        WHERE id=%s
        """,(status, note, complaint_id))

        mysql.connection.commit()

        return redirect('/admin/complaints')

    return render_template('admin/update_status.html')

# ---------------- Citizen Profile ----------------

@app.route('/profile', methods=['GET','POST'])
def profile():

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    # Update profile
    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        cur.execute("""
            UPDATE users
            SET name=%s, email=%s, phone=%s
            WHERE id=%s
        """,(name,email,phone,session['user']))

        mysql.connection.commit()

        return redirect('/profile')

    # Fetch user data
    cur.execute("SELECT id,name,email,phone FROM users WHERE id=%s",
                (session['user'],))

    user = cur.fetchone()

    return render_template(
        'citizen/profile.html',
        user=user
    )


# ---------------- Admin Complaint Details ----------------

@app.route('/admin/complaint/<int:complaint_id>')
def admin_complaint_details(complaint_id):

    if 'admin' not in session:
        return redirect('/admin')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id,user_id,title,description,category,
               location,image,status,department,created_at
        FROM complaints
        WHERE id=%s
    """,(complaint_id,))

    complaint = cur.fetchone()

    if not complaint:
        return "Complaint not found"

    return render_template(
        'admin/complaint_details.html',
        complaint=complaint
    )

# ---------------- Assign Department ----------------

@app.route('/admin/assign/<int:complaint_id>', methods=['GET','POST'])
def assign_department(complaint_id):

    if 'admin' not in session:
        return redirect('/admin')

    cur = mysql.connection.cursor()

    if request.method == 'POST':

        department = request.form['department']

        cur.execute("""
            UPDATE complaints
            SET department=%s
            WHERE id=%s
        """,(department,complaint_id))

        mysql.connection.commit()

        return redirect('/admin/complaints')

    # Fetch complaint data
    cur.execute("SELECT id,title,category FROM complaints WHERE id=%s",(complaint_id,))
    complaint = cur.fetchone()

    return render_template(
        'admin/assign_department.html',
        complaint=complaint
    )

# ---------------- Admin Reports ----------------

@app.route('/admin/reports')
def admin_reports():

    if 'admin' not in session:
        return redirect('/admin')

    cur = mysql.connection.cursor()

    # total complaints
    cur.execute("SELECT COUNT(*) FROM complaints")
    total = cur.fetchone()[0]

    # pending complaints
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
    pending = cur.fetchone()[0]

    # resolved complaints
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'")
    resolved = cur.fetchone()[0]

    # complaints by category
    cur.execute("""
        SELECT category, COUNT(*)
        FROM complaints
        GROUP BY category
    """)
    category_data = cur.fetchall()

    # complaints by department
    cur.execute("""
        SELECT department, COUNT(*)
        FROM complaints
        GROUP BY department
    """)
    department_data = cur.fetchall()

    return render_template(
        'admin/reports.html',
        total=total,
        pending=pending,
        resolved=resolved,
        category_data=category_data,
        department_data=department_data
    )

# ---------------- Admin Manage Users ----------------

@app.route('/admin/manage_users')
def manage_users():

    if 'admin' not in session:
        return redirect('/admin')

    cur = mysql.connection.cursor()

    cur.execute("SELECT id, name, email, phone FROM users")

    users = cur.fetchall()

    return render_template('admin/manage_users.html', users=users)

@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):

    if 'admin' not in session:
        return redirect('/admin')

    cur = mysql.connection.cursor()

    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))

    mysql.connection.commit()

    return redirect('/admin/manage_users')




if __name__ == '__main__':
    app.run(debug=True)
