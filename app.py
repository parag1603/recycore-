from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash
import os

# =========================================================
#                 FLASK INITIALIZATION
# =========================================================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "temporary_secret")

app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

serializer = URLSafeTimedSerializer(app.secret_key)

# =========================================================
#                 DATABASE DISABLED (FOR LIVE DEPLOY)
# =========================================================
def get_db_connection():
    return None


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


@app.route('/register_user', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        flash("Registration temporarily disabled (Database not connected).", "info")
        return redirect(url_for('user_login'))
    return render_template('user-registration.html')


@app.route('/user-login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        session['user'] = "demo_user"
        session['user_id'] = 1
        return redirect(url_for('user_dashboard'))
    return render_template('user-login.html')


@app.route('/user-logout')
def user_logout():
    session.clear()
    return redirect(url_for('user_login'))


@app.route('/user-dashboard')
def user_dashboard():
    if 'user' not in session:
        return redirect(url_for('user_login'))
    return render_template('user-dashboard.html',
                           user_name="Demo User",
                           cc_hours=0,
                           pickup_date=None)


@app.route('/user-profile')
def user_profile():
    if 'user' not in session:
        return redirect(url_for('user_login'))
    return render_template('user_profile.html',
                           username="Demo User",
                           email="demo@email.com",
                           address="Demo Address",
                           cc_hours=0,
                           ewaste_list=[])


@app.route('/pickup_request', methods=['GET', 'POST'])
def pickup_request():
    if request.method == 'POST':
        flash("Pickup submitted (Demo Mode).", "success")
        return redirect(url_for('user_profile'))
    return render_template('pickup-request.html')


# =========================================================
#                    ADMIN MODULE
# =========================================================
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['email'] == 'admin@gmail.com' and request.form['password'] == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        flash("Invalid credentials", "danger")
    return render_template('admin-login.html')


@app.route('/admin-panel')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    return render_template('admin-panel.html')


@app.route('/admin_logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/view-users')
def view_users():
    return render_template('view-users.html', users=[])


@app.route('/view-recyclers')
def view_recyclers():
    return render_template('view-recyclers.html',
                           recyclers=[],
                           pickup_requests=[])


@app.route('/admin-view-pickups')
def admin_view_pickups():
    return render_template('admin-view-pickups.html',
                           pickups=[],
                           current_date=None)


# =========================================================
#                    RECYCLER MODULE
# =========================================================
@app.route('/recycler-login', methods=['GET', 'POST'])
def recycler_login():
    if request.method == 'POST':
        session['recycler_logged_in'] = True
        return redirect(url_for('recycler_dashboard'))
    return render_template('recycler-login.html')


@app.route('/recycler-dashboard')
def recycler_dashboard():
    if not session.get('recycler_logged_in'):
        return redirect(url_for('recycler_login'))
    return render_template('recycler-dashboard.html')


@app.route('/recycler-options')
def recycler_options():
    return render_template('recycler-options.html')


@app.route('/recycler-pickups')
def recycler_pickups():
    return render_template('recycler-pickups.html', total_items=[])


@app.route('/recycler-profile')
def recycler_profile():
    return render_template('recycler-profile.html', recycler=None)


@app.route('/recycler-logout')
def recycler_logout():
    session.clear()
    return redirect(url_for('recycler-login'))


# =========================================================
#                    FORGOT PASSWORD (DISABLED EMAIL)
# =========================================================
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        flash("Password reset disabled (Demo Mode).", "info")
        return redirect(url_for('forgot_password'))
    return render_template('forgot-password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    flash("Reset disabled (Demo Mode).", "info")
    return redirect(url_for('forgot_password'))


# =========================================================
#                    MAIN RUN
# =========================================================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)