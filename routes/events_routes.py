from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import json, os
from datetime import datetime

# Blueprint name simplified
events_bp = Blueprint('events', __name__)
EVENTS_FILE = 'events.json'


def load_events():
    if not os.path.exists(EVENTS_FILE):
        return []
    with open(EVENTS_FILE, 'r') as f:
        return json.load(f)


def save_events(events):
    with open(EVENTS_FILE, 'w') as f:
        json.dump(events, f, indent=4)


# ==================== ROUTES ====================

@events_bp.route('/events')
def events():
    events = load_events()
    return render_template('events.html', events=events)


@events_bp.route('/add_event', methods=['GET', 'POST'])
def add_event():
    if not session.get('admin'):
        flash('Admin login required.')
        session['next'] = 'events.add_event'
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        title = request.form.get('title')
        date = request.form.get('date')
        description = request.form.get('description')

        if not title or not date:
            flash('Title and Date are required.')
            return redirect(url_for('events.add_event'))

        events = load_events()
        events.append({
            'title': title,
            'date': date,
            'description': description,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_events(events)
        flash('Event added successfully!')
        return redirect(url_for('events.events'))

    return render_template('add_event.html')


@events_bp.route('/delete_event/<int:event_index>', methods=['POST'])
def delete_event(event_index):
    if not session.get('admin'):
        flash('Admin privileges required.')
        return redirect(url_for('admin.admin_login'))  # ✅ fixed here

    events = load_events()
    if 0 <= event_index < len(events):
        deleted_event = events.pop(event_index)
        save_events(events)
        flash(f"Deleted event '{deleted_event['title']}'")
    else:
        flash('Event not found.')

    return redirect(url_for('events.events'))
