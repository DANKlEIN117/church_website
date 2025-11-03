from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import json
import os
from datetime import datetime

sermons_bp = Blueprint('sermons', __name__)
SERMONS_FILE = 'sermons.json'


def load_sermons():
    if not os.path.exists(SERMONS_FILE):
        return []
    with open(SERMONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_sermons(sermons):
    with open(SERMONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sermons, f, indent=4)


@sermons_bp.route('/sermons')
def sermons():
    sermons = load_sermons()
    return render_template('sermons.html', sermons=sermons)


@sermons_bp.route('/add_sermon', methods=['GET', 'POST'])
def add_sermon():
    if not session.get('admin'):
        flash('⚠️ Admin login required.')
        session['next'] = 'sermons.add_sermon'
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        preacher = request.form.get('preacher', '').strip()
        date = request.form.get('date', '')
        message = request.form.get('message', '').strip()

        if not title or not preacher:
            flash('❌ Title and Preacher are required.')
            return redirect(url_for('sermons.add_sermon'))

        sermons = load_sermons()
        sermons.append({
            'title': title,
            'preacher': preacher,
            'date': date,
            'message': message,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_sermons(sermons)
        flash('✅ Sermon added successfully!')
        return redirect(url_for('sermons.sermons'))

    return render_template('add_sermon.html')


@sermons_bp.route('/delete_sermon/<int:sermon_index>', methods=['POST'])
def delete_sermon(sermon_index):
    if not session.get('admin'):
        flash('⚠️ Admin privileges required.')
        return redirect(url_for('admin.admin_login'))

    sermons = load_sermons()
    if 0 <= sermon_index < len(sermons):
        deleted_sermon = sermons.pop(sermon_index)
        save_sermons(sermons)
        flash(f"🗑️ Sermon '{deleted_sermon['title']}' deleted successfully.")
    else:
        flash('❌ Sermon not found.')
    return redirect(url_for('sermons.sermons'))
