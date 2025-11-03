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
    try:
        with open('sermons.json', 'r') as f:
            sermons = json.load(f)
    except:
        sermons = []
    return render_template('sermons.html', sermons=sermons)

@sermons_bp.route('/add_sermon', methods=['GET', 'POST'])
def add_sermon():
    if not session.get('admin'):
        flash('Admin access required.')
        session['next'] = 'add_sermon'
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        title = request.form['title']
        preacher = request.form['preacher']
        date = request.form['date']
        summary = request.form['summary']

        with open('sermons.json', 'r') as f:
            sermons = json.load(f)

        sermon_id = sermons[-1]['id'] + 1 if sermons else 1
        sermons.append({
            "id": sermon_id,
            "title": title,
            "preacher": preacher,
            "date": date,
            "summary": summary
        })

        with open('sermons.json', 'w') as f:
            json.dump(sermons, f, indent=4)

        flash('Sermon added.')
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
