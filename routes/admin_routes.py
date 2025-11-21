from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import os

# Blueprint setup with a URL prefix handled in __init__.py
admin_bp = Blueprint('admin', __name__)

# Default admin credentials (override via .env)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "church123")

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            flash('✅ Logged in as admin.')

            next_page = session.pop('next', None)
            if next_page:
                try:
                    return redirect(url_for(next_page))
                except:
                    flash("⚠️ Couldn't redirect to the next page.")

            # Default admin landing
            return redirect(url_for('home'))
        else:
            flash('❌ Invalid credentials. Try again.')

    return render_template('admin_login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('admin', None)
    flash('👋 Logged out successfully.')
    return redirect(url_for('home'))



