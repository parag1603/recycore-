from flask import Flask, render_template, request, redirect, url_for, session,flash
from flask_mail import Mail, Message
from datetime import datetime 
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash
import os
import mysql.connector

# =========================================================
#                 FLASK INITIALIZATION
# =========================================================
app = Flask(__name__)
app.secret_key = 'sejal'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# =========================================================
#                 MAIL CONFIGURATION
# =========================================================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'paragsakpal16@gmail.com'
app.config['MAIL_PASSWORD'] = 'aqquhjnjivnxhlmm'

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# =========================================================
#                 DATABASE CONNECTION
# =========================================================
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="parag",
        password="1234",
        database="ewaste_db",
        auth_plugin='mysql_native_password'
    )

print("✅ Database connected successfully!")

# =========================================================
#                      HOME PAGE
# =========================================================
@app.route('/')
def home():
    return render_template('index.html')

# =========================================================
#                    USER MODULE 
# =========================================================
@app.route('/user-entry')
def user_entry():
    return render_template('user-entry.html')

# ----- USER REGISTRATION -----
@app.route('/register_user', methods=['GET', 'POST'])
def register_user():
    session.pop('_flashes', None)
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        contact = request.form['contact']
        email = request.form['email']
        department = request.form['department']  #  Capture department
        password = request.form['password']

        hashed_password = generate_password_hash(password)
        try:
            db = get_db_connection()
            cursor = db.cursor()
        
            cursor.execute("""
                INSERT INTO users (name, address, contact, email, password, department, cc_hours)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, address, contact, email, hashed_password, department, 0))
            
            db.commit()
            cursor.close()
            db.close()
          
            return redirect(url_for('user_login'))
        except Exception as e:
            pass

    return render_template('user-registration.html')

# ----- USER LOGIN -----
@app.route('/user-login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user['password'], password):
            session['user'] = user['email']
            session['user_id'] = user['id']
         
            return redirect(url_for('user_dashboard'))

    return render_template('user-login.html')

@app.route('/user-logout')
def user_logout():
    session.pop('user', None)
    session.pop('user_id', None)
    return redirect(url_for('user_login'))

# ----- USER DASHBOARD -----
@app.route('/user-dashboard')
def user_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('user_login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get user's CC hours and name
    cursor.execute("SELECT name, cc_hours FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    if result:
        user_name = result[0]
        cc_hours = result[1]
    else:
        user_name = "User"
        cc_hours = 0

    # Fetch the global pickup date set by admin
    cursor.execute("SELECT pickup_date FROM pickup_schedule ORDER BY id DESC LIMIT 1")
    date_result = cursor.fetchone()
    pickup_date = date_result[0] if date_result else None

    cursor.close()
    conn.close()

    return render_template(
        'user-dashboard.html',
        user_name=user_name,
        cc_hours=cc_hours,
        pickup_date=pickup_date
    )

@app.route('/user-profile')
def user_profile():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user info
    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        flash("User not found.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('user_dashboard'))

    # Fetch user's e-waste submissions
    cursor.execute("""
        SELECT item_name, quantity, created_at
        FROM pickup_requests
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (user_id,))
    submissions = cursor.fetchall()

    # Calculate total quantity across all submissions
    total_quantity_all = sum(row['quantity'] for row in submissions)

    # Award 2 CC hours if user hasn't already received it and total_quantity >= 5
    if user['cc_hours'] < 2 and total_quantity_all >= 5:
        new_cc_hours = user['cc_hours'] + 2
        cursor.execute("UPDATE users SET cc_hours=%s WHERE id=%s", (new_cc_hours, user_id))
        conn.commit()
        user['cc_hours'] = new_cc_hours

    # Prepare submissions for template
    ewaste_list = []
    for row in submissions:
        ewaste_list.append({
            'item_names': row['item_name'],
            'total_quantity': row['quantity'],
            'submission_date': row['created_at']
        })

    cursor.close()
    conn.close()

    return render_template(
        'user_profile.html',
        username=user['name'],
        email=user['email'],
        address=user['address'],
        cc_hours=user['cc_hours'],
        ewaste_list=ewaste_list
    )

@app.route('/pickup_request', methods=['GET', 'POST'])
def pickup_request():
    if request.method == 'POST':
        user_id = request.form.get('userid')
        selected_items = request.form.getlist('item_type[]')  # List of checked items

        if not selected_items:
            flash("Please select at least one item.", "danger")
            return redirect(url_for('pickup_request'))

        conn = get_db_connection()
        cursor = conn.cursor()

        submission_time = datetime.now()

        for item in selected_items:
            # Get the quantity for this item
            quantity_field = f"quantity_{item}"
            quantity = request.form.get(quantity_field)
            if quantity is None or quantity == '':
                quantity = 1  # Default if user forgets
            quantity = int(quantity)

            # If user chose "Other", get the custom name
            if item == "Other":
                other_name = request.form.get("other_item_name").strip()
                if other_name:
                    item_name = other_name
                else:
                    item_name = "Other"
            else:
                item_name = item

            # Insert each item with its quantity
            cursor.execute(
                "INSERT INTO pickup_requests (user_id, item_name, quantity, created_at) VALUES (%s, %s, %s, %s)",
                (user_id, item_name, quantity, submission_time)
            )

        conn.commit()
        cursor.close()
        conn.close()

        flash("E-Waste submitted successfully!", "success")
        return redirect(url_for('user_profile'))

    return render_template('pickup-request.html')


@app.route('/assign-recycler/<int:request_id>', methods=['POST'])
def assign_recycler(request_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get recycler_id and pickup_date from form
    recycler_id = request.form.get('recycler_id')
    pickup_date = request.form.get('pickup_date')

    if not recycler_id or not pickup_date:
        flash("Please select a recycler and pickup date.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('view_recyclers'))

    # Get recycler's email and name
    cursor.execute("SELECT email, name FROM recyclers WHERE id = %s", (recycler_id,))
    recycler = cursor.fetchone()
    if not recycler:
        flash("Recycler not found.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('view_recyclers'))

    recycler_email = recycler['email']
    recycler_name = recycler['name']

    # Insert assigned pickup record
    cursor.execute("""
        INSERT INTO assigned_pickups (recycler_id, pickup_date)
        VALUES (%s, %s)
    """, (recycler_id, pickup_date))
    conn.commit()

    # Update pickup_requests to mark which recycler and date is assigned
    cursor.execute("""
        UPDATE pickup_requests
        SET recycler_id = %s, pickup_date = %s, status = 'Assigned'
        WHERE request_id = %s
    """, (recycler_id, pickup_date, request_id))
    conn.commit()
   
    accept_link = url_for('recycler_response', request_id=request_id, action='accept', _external=True)
    reject_link = url_for('recycler_response', request_id=request_id, action='reject', _external=True)

    # Send email to recycler
    msg = Message(
    subject="E-Waste Pickup Assigned",
    sender="youremail@gmail.com",  # your configured sender
    recipients=[recycler_email],
    html=f"""
    <p>Hello {recycler_name},</p>
    <p>You have been assigned a new e-waste pickup from RJ College, Ghatkopar.</p>
    <p>Pickup Date: {pickup_date}</p>
    <p>Please check your dashboard for details.</p>
    <p>Please respond:</p>
    <a href="{accept_link}">✅ Accept</a> | <a href="{reject_link}">❌ Reject</a>
    """
)
    mail.send(msg)

    cursor.close()
    conn.close()

    flash("Recycler assigned successfully and notified via email.", "success")
    return redirect(url_for('view_recyclers'))


@app.route('/recycler-response/<int:request_id>/<action>')
def recycler_response(request_id, action):
    if action not in ['accept', 'reject']:
        return "Invalid action", 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get assigned recycler for this request
    cursor.execute("SELECT recycler_id, pickup_date FROM pickup_requests WHERE request_id=%s", (request_id,))
    request_row = cursor.fetchone()
    if not request_row:
        cursor.close()
        conn.close()
        return "Request not found", 404

    # Update status based on action
    status = "Accepted" if action == "accept" else "Rejected"
    cursor.execute("UPDATE pickup_requests SET status=%s WHERE request_id=%s", (status, request_id))
    conn.commit()

    # Notify admin
    admin_email = "hulesejal085@gmail.com"  # admin email
    msg = Message(
        subject=f"Recycler {status} Pickup",
        sender="youremail@gmail.com",
        recipients=[admin_email],
        body=f"The recycler (ID: {request_row['recycler_id']}) has {status.lower()} the pickup scheduled on {request_row['pickup_date']}."
    )
    mail.send(msg)

    cursor.close()
    conn.close()

    return f"Pickup {status} successfully. Admin has been notified."


# =========================================================
#                    ADMIN MODULE 
# =========================================================
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if email == 'admin@gmail.com' and password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin-login.html', error="Invalid credentials")

    return render_template('admin-login.html')


@app.route('/admin-dashboard')
def admin_dashboard():
    return render_template('admin-panel.html')  # use the correct file name
@app.route('/admin-panel')
def admin_panel():
    return render_template('admin-panel.html')

@app.route("/admin_logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

# ----- Manage Users -----
@app.route('/view-users')
def view_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, address, contact, email, cc_hours FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('view-users.html', users=users)

@app.route('/delete-user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        session.pop('_flashes', None)
        cursor.execute("DELETE FROM pickup_requests WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('view_users'))

# ----- Manage Recyclers -----
@app.route('/add-recycler', methods=['GET', 'POST'])
def add_recycler():
    if request.method == 'POST':
        rname = request.form['rname']
        remail = request.form['remail']
        rpassword = request.form['rpassword']
        rcontact = request.form['rcontact']
        rlocation = request.form['rlocation']

        hashed_password = generate_password_hash(rpassword)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recyclers (name, email, password, contact, location)
                VALUES (%s, %s, %s, %s, %s)
            """, (rname, remail, hashed_password, rcontact, rlocation))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('recycler_options'))

    return render_template('add-recycler.html')

@app.route('/update-user/<int:user_id>', methods=['GET', 'POST'])
def update_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        new_cc_hours = request.form['cc_hours']
        cursor.execute("UPDATE users SET cc_hours = %s WHERE id = %s", (new_cc_hours, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash('✅ CC Hours updated successfully!', 'success')
        return redirect(url_for('view_users'))  # same as your registered users function name

    cursor.execute("SELECT id, name, address, email, cc_hours FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('update_user.html', user=user)


@app.route('/view-recyclers')
def view_recyclers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all recyclers
    cursor.execute("SELECT id, name, email, contact, location FROM recyclers")
    recyclers = cursor.fetchall()

    # Fetch all pending pickup requests (not yet assigned)
    cursor.execute("""
        SELECT p.request_id, u.name AS user_name, p.item_name, p.quantity, p.created_at
        FROM pickup_requests p
        JOIN users u ON p.user_id = u.id
        WHERE p.recycler_id IS NULL OR p.recycler_id = ''
        ORDER BY p.created_at DESC
    """)
    pickup_requests = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('view-recyclers.html',
                           recyclers=recyclers,
                           pickup_requests=pickup_requests)


@app.route('/delete-recycler/<int:id>', methods=['POST'])
def delete_recycler(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recyclers WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('view_recyclers'))



@app.route('/admin-view-pickups', methods=['GET', 'POST'])
def admin_view_pickups():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Handle pickup date submission
    if request.method == 'POST':
        pickup_date = request.form.get('pickup_date')
        if pickup_date:
            cursor.execute("DELETE FROM pickup_schedule")
            cursor.execute("INSERT INTO pickup_schedule (pickup_date) VALUES (%s)", (pickup_date,))
            conn.commit()

    # Get current pickup date
    cursor.execute("SELECT pickup_date FROM pickup_schedule ORDER BY id DESC LIMIT 1")
    current_date = cursor.fetchone()

    # Fetch all submissions
    cursor.execute("""
    SELECT 
        p.user_id, 
        u.name AS user_name, 
        p.item_name, 
        p.quantity, 
        p.created_at
    FROM pickup_requests p
    JOIN users u ON u.id = p.user_id
    ORDER BY p.created_at DESC
""")
    submissions = cursor.fetchall()

    # Group submissions by user + timestamp
    grouped = {}
    for row in submissions:
        key = (row['user_id'], row['created_at'])
        if key not in grouped:
            grouped[key] = {
                'user_id': row['user_id'],
                'user_name': row['user_name'],
                'items': [],
                'total_quantity': 0,
                'submission_date': row['created_at']
            }
        grouped[key]['items'].append(row['item_name'])
        grouped[key]['total_quantity'] += row['quantity']  # ✅ sum quantities

    # Prepare final list for template
    pickups = []
    for v in grouped.values():
        pickups.append({
            'user_id': v['user_id'],
            'user_name': v['user_name'],
            'submitted_items': ', '.join(v['items']),
            'total_quantity': v['total_quantity'],  # ✅ use summed quantity
            'submission_date': v['submission_date']
        })

    cursor.close()
    conn.close()

    return render_template('admin-view-pickups.html', pickups=pickups, current_date=current_date)


# =========================================================
#                    RECYCLER MODULE 
# =========================================================
@app.route('/recycler-login', methods=['GET', 'POST'])
def recycler_login():
    if request.method == 'POST':
        remail = request.form['remail']
        rpassword = request.form['rpassword']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM recyclers WHERE email = %s", (remail,))
        recycler = cursor.fetchone()
        cursor.close()
        conn.close()

        if recycler and check_password_hash(recycler['password'], rpassword):
            session['recycler_logged_in'] = True
            session['recycler_id'] = recycler['id']
            session['recycler_email'] = recycler['email']
            return redirect(url_for('recycler_dashboard'))
        else:
            return redirect(url_for('recycler_login'))
    return render_template('recycler-login.html')

@app.route('/recycler-dashboard')
def recycler_dashboard():
    if not session.get('recycler_logged_in'):
        return redirect(url_for('recycler_login'))

    # Simply render the dashboard page with buttons
    return render_template('recycler-dashboard.html')


@app.route('/send-to-recycler', methods=['POST'])
def send_to_recycler():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Mark all unprocessed pickup requests as processed
        cursor.execute("UPDATE pickup_requests SET processed_by_admin = 1 WHERE processed_by_admin = 0")
        conn.commit()

        # Fetch recyclers with their assigned pickups
        cursor.execute("""
            SELECT r.id AS recycler_id, r.name, r.email, p.item_name, COUNT(*) AS total_quantity
            FROM recyclers r
            JOIN assigned_pickups a ON r.id = a.recycler_id
            JOIN pickup_requests p ON a.request_id = p.request_id
            GROUP BY r.id, r.name, r.email, p.item_name
        """)
        rows = cursor.fetchall()

        # Group pickups by recycler
        recyclers = {}
        for row in rows:
            rid = row['recycler_id']
            if rid not in recyclers:
                recyclers[rid] = {'name': row['name'], 'email': row['email'], 'pickups': []}
            recyclers[rid]['pickups'].append(f"{row['item_name']}: {row['total_quantity']}")

        # Send email to each recycler
        for r in recyclers.values():
            body = f"Hello {r['name']},\n\nYou have been assigned the following e-waste pickups:\n\n"
            body += "\n".join(r['pickups'])
            body += "\n\nPlease check your dashboard for details."

            msg = Message(
                subject="E-Waste Pickup Notification",
                sender=app.config['MAIL_USERNAME'],
                recipients=[r['email']],
                body=body
            )
            mail.send(msg)
            print(f"✅ Email sent to {r['email']}")

    except Exception as e:
        print("❌ Error sending emails:", e)
        flash("An error occurred while sending emails. Check console for details.", "danger")

    finally:
        cursor.close()
        conn.close()

    flash("E-Waste summary sent to recyclers successfully!", "success")
    return redirect(url_for('admin_view_pickups'))






@app.route('/recycler-options')
def recycler_options():
    return render_template('recycler-options.html')

@app.route('/recycler-pickups')
def recycler_pickups():
    if not session.get('recycler_logged_in'):
        return redirect(url_for('recycler_login'))

    recycler_id = session.get('recycler_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all items assigned to this recycler or unassigned
    cursor.execute("""
        SELECT item_name, SUM(quantity) AS total_quantity
        FROM pickup_requests
        WHERE recycler_id = %s OR recycler_id IS NULL
        GROUP BY item_name
        ORDER BY item_name
    """, (recycler_id,))
    total_items_list = cursor.fetchall()  # [{'item_name': ..., 'total_quantity': ...}, ...]

    # Handle "Other" items separately if needed
    # In your form, "Other" items are stored with their name in `item_name`, so they are included already
    # So no extra code is needed; they will appear like any other item

    cursor.close()
    conn.close()

    return render_template('recycler-pickups.html', total_items=total_items_list)

@app.route('/recycler-profile')
def recycler_profile():
    if not session.get('recycler_logged_in'):
        return redirect(url_for('recycler_login'))

    recycler_id = session.get('recycler_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recyclers WHERE id = %s", (recycler_id,))
    recycler = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('recycler-profile.html', recycler=recycler)


@app.route('/update_status/<int:request_id>', methods=['POST'])
def update_status(request_id):
    if not session.get('recycler_logged_in'):
        return redirect(url_for('recycler_login'))

    new_status = request.form['status']
    recycler_id = session.get('recycler_id')

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # ✅ Step 1: Verify this recycler is assigned for this request
    cursor.execute("""
        SELECT a.recycler_id, a.pickup_date, u.email AS admin_email
        FROM assigned_pickups a
        JOIN admin u ON 1=1
        WHERE a.recycler_id = %s
    """, (recycler_id,))
    assignment = cursor.fetchone()

    if not assignment:
        flash("You are not authorized to update this pickup request.", "error")
        cursor.close()
        db.close()
        return redirect(url_for('recycler_pickups'))

    # ✅ Step 2: Update pickup request status
    cursor.execute("UPDATE pickup_requests SET status = %s WHERE request_id = %s",
                   (new_status, request_id))
    db.commit()

    # ✅ Step 3: Update assigned_pickups status
    cursor.execute("""
        UPDATE assigned_pickups 
        SET status = %s 
        WHERE recycler_id = %s
    """, (new_status, recycler_id))
    db.commit()

    # ✅ Step 4: Send email notification to admin
    msg = Message(
        subject=f"Recycler {new_status} Pickup Notification",
        sender=app.config['MAIL_USERNAME'],
        recipients=["paragsakpal16@gmail.com"],
        body=f"The recycler (ID: {recycler_id}) has {new_status.lower()} the pickup request scheduled on {assignment['pickup_date']}."
    )
    mail.send(msg)

    cursor.close()
    db.close()

    flash(f"Pickup request {new_status}. Admin has been notified.", "success")
    return redirect(url_for('recycler_pickups'))


@app.route('/recycler-logout')
def recycler_logout():
    session.pop('recycler_logged_in', None)
    return redirect(url_for('recycler_login'))


# =========================================================
#                FORGOT PASSWORD
# =========================================================
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        token = serializer.dumps(email, salt='password-reset')

        link = url_for('reset_password', token=token, _external=True)
        msg = Message('Recycore Password Reset Link',
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[email])
        msg.body = f"Hello, to reset your password click the link below:\n\n{link}\n\nThis link will expire in 10 minutes."
        mail.send(msg)

        return redirect(url_for('forgot-password'))

    return render_template('forgot-password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset', max_age=3600)
    except Exception:
        return redirect(url_for('forgot-password'))

    if request.method == 'POST':
        new_password = request.form['new_password']
        hashed_password = generate_password_hash(new_password)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE recyclers SET password=%s WHERE email=%s", (hashed_password, email))
        conn.commit()
        conn.close()

        return redirect(url_for('recycler-login'))

    return render_template('reset_password.html')

# =========================================================
#                    MAIN RUN
# =========================================================
if __name__ == '__main__':
    app.run()
