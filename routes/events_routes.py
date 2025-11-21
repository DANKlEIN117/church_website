from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
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
    with open('events.json', 'r') as f:
        events = json.load(f)
    return render_template('events.html', events=events)


@events_bp.route('/data')
def events_data():
    """Return events as JSON for the interactive calendar."""
    events = load_events()
    return jsonify(events)

@events_bp.route('/add_event', methods=['GET', 'POST'])
def add_event():
    if not session.get('admin'):
        flash('Admin access required.')
        session['next'] = 'events.add_event'
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        description = request.form['description']

        with open('events.json', 'r') as f:
            events = json.load(f)

        event_id = (events[-1]['id'] + 1) if events else 1
        events.append({"id": event_id, "title": title, "date": date, "description": description})

        with open('events.json', 'w') as f:
            json.dump(events, f, indent=4)

        flash("Event added.")
        return redirect(url_for('events.events'))

    return render_template('add_event.html')

@events_bp.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if not session.get('admin'):
        flash('Admin access required.')
        return redirect(url_for('admin.admin_login'))

    with open('events.json', 'r') as f:
        events = json.load(f)

    events = [e for e in events if e['id'] != event_id]

    with open('events.json', 'w') as f:
        json.dump(events, f, indent=4)

    flash("Event deleted.")
    return redirect(url_for('events.events'))