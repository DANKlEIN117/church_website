from flask import Flask, render_template
from routes import register_blueprints
import os
from dotenv import load_dotenv
import cloudinary

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-key")

# Cloudinary setup
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# Register blueprints from /routes/__init__.py
register_blueprints(app)


@app.route('/')
def home():
    # Load events and compute simple upcoming / past summaries for home notifications
    events = []
    try:
        with open('events.json', 'r') as f:
            events = json.load(f)
    except Exception:
        events = []

    from datetime import datetime, date
    today = date.today()
    upcoming = []
    past = []
    for e in events:
        try:
            d = datetime.fromisoformat(e.get('date')).date()
        except Exception:
            continue
        if d >= today:
            upcoming.append((d, e))
        else:
            past.append((d, e))

    upcoming.sort(key=lambda x: x[0])
    past.sort(key=lambda x: x[0], reverse=True)

    events_summary = {
        'upcoming_count': len(upcoming),
        'past_count': len(past),
        'upcoming': [ {'date': d.isoformat(), 'title': ev.get('title','')} for d, ev in upcoming[:3] ],
        'past': [ {'date': d.isoformat(), 'title': ev.get('title','')} for d, ev in past[:3] ],
    }

    return render_template('index.html', events_summary=events_summary)


# Simple calendar route so the calendar page can be reached from the nav
@app.route('/calendar')
def calendar():
    return render_template('calendar.html')


# Error handlers (optional but pro)
@app.errorhandler(404)
def not_found(_):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(_):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
