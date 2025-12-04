from flask import Flask, render_template, request, jsonify, current_app, session, redirect, url_for
from collections import deque
from routes import register_blueprints
import os
from dotenv import load_dotenv
import cloudinary
import json
from datetime import datetime
import uuid
import os
import hmac
import hashlib
import base64
import logging
import io
import csv
from db import init_app as db_init_app, init_db, add_payment, get_payments, get_summary, set_target_amount
from db import create_campaign, get_campaigns, set_active_campaign, get_active_campaign, get_campaign, get_audits

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

# initialize database helper
db_init_app(app)

# Run migrations automatically if environment requests it
if os.getenv('RUN_MIGRATIONS', 'false').lower() in ('1', 'true', 'yes'):
    init_db()

# Ensure logs directory exists and configure webhook logger
os.makedirs('logs', exist_ok=True)
wh_logger = logging.getLogger('webhooks')
wh_logger.setLevel(logging.INFO)
wh_handler = logging.FileHandler('logs/webhooks.log')
wh_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
wh_logger.addHandler(wh_handler)


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


# Contributions page
@app.route('/contributions')
def contributions_page():
    active = get_active_campaign()
    return render_template('contributions.html', active_campaign=active)


@app.route('/contributions/data')
def contributions_data():
    """Return current contributions summary as JSON."""
    # return DB-backed summary; if an active campaign exists, show campaign-specific progress
    active = get_active_campaign()
    if active and active.get('id'):
        campaign_id = active.get('id')
        summary = get_summary(campaign_id=campaign_id)
        payments = get_payments(200)
        # filter payments for campaign on the fly for listing
        payments_filtered = [p for p in payments if p.get('campaign_id') == campaign_id]
        return jsonify({
            'campaign': active,
            'target_amount': summary['target_amount'],
            'total_contributed': summary['total_contributed'],
            'remaining': summary['remaining'],
            'percent': summary['percent'],
            'payments': payments_filtered
        })
    else:
        summary = get_summary()
        payments = get_payments(200)
        return jsonify({
            'target_amount': summary['target_amount'],
            'total_contributed': summary['total_contributed'],
            'remaining': summary['remaining'],
            'percent': summary['percent'],
            'payments': payments
        })


@app.route('/contributions/simulate', methods=['POST'])
def contributions_simulate():
    """Simulate receiving a contribution (for testing). Expects JSON {name, amount}.
    This endpoint is for local testing only and should be disabled or protected in production.
    """
    # Simulation endpoint is disabled by default in production. To enable locally,
    # set the environment variable `ENABLE_MPESA_SIMULATE=true`.
    enabled = os.getenv('ENABLE_MPESA_SIMULATE', 'false').lower() in ('1', 'true', 'yes')
    if not enabled:
        return jsonify({'error': 'simulation endpoint disabled'}), 403

    payload = request.get_json() or {}
    name = payload.get('name', 'Test')
    try:
        amount = float(payload.get('amount', 0) or 0)
    except Exception:
        return jsonify({'error': 'invalid amount'}), 400

    # associate with active campaign if present
    active = get_active_campaign()
    entry = {
        'id': str(uuid.uuid4()),
        'from': name,
        'amount': amount,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'method': 'mpesa-sim',
        'campaign_id': active.get('id') if active else None
    }

    # insert into DB
    try:
        add_payment(entry)
    except Exception as e:
        return jsonify({'error': 'failed to write to DB', 'details': str(e)}), 500
    return jsonify({'status': 'ok', 'entry': entry})


@app.route('/contributions/webhook', methods=['POST'])
def contributions_webhook():
    """Endpoint to receive real Mpesa callbacks/webhooks (STK push or confirmation).
    For real integration, validate signatures and secrets. Here we accept JSON payloads
    and attempt to append an entry if it contains an `amount` and `msisdn`/`name`.
    """
    # Verify webhook signature if configured
    secret = os.getenv('MPESA_WEBHOOK_SECRET')
    raw_body = request.get_data() or b''

    sig_header = (request.headers.get('X-Mpesa-Signature')
                  or request.headers.get('X-Signature')
                  or request.headers.get('X-Callback-Signature'))

    if secret:
        if not sig_header:
            return jsonify({'error': 'missing signature header'}), 401
        try:
            # compute HMAC-SHA256 then base64 encode (common pattern)
            mac = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).digest()
            computed = base64.b64encode(mac).decode()
        except Exception:
            return jsonify({'error': 'signature computation failed'}), 500

        # constant-time comparison
        if not hmac.compare_digest(computed, sig_header):
            return jsonify({'error': 'invalid signature'}), 401
    else:
        # If no secret configured, allow but warn in logs
        current_app.logger.warning('MPESA_WEBHOOK_SECRET not set — accepting webhook without verification')

    # parse payload and attempt to extract amount and sender
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        payload = {}

    # log raw request body for audit (already verified if secret set)
    try:
        wh_logger.info(request.get_data(as_text=True))
    except Exception:
        current_app.logger.exception('failed to write webhook log')

    amount = None
    name = None

    # Daraja typical structure: { "Body": { "stkCallback": { "CallbackMetadata": { "Item": [...] } } } }
    # Try common locations for amount and phone/account
    def extract_from_items(items):
        a = None
        n = None
        if not isinstance(items, list):
            return a, n
        for it in items:
            if not isinstance(it, dict):
                continue
            key = it.get('Name') or it.get('name')
            val = it.get('Value') if 'Value' in it else it.get('value')
            if key and val is not None:
                k = key.lower()
                if 'amount' in k and a is None:
                    try:
                        a = float(val)
                    except Exception:
                        pass
                if ('msisdn' in k or 'phone' in k or 'number' in k or 'account' in k) and n is None:
                    n = str(val)
        return a, n

    # drill for callback metadata
    if isinstance(payload, dict):
        # search for CallbackMetadata items
        def find_items(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k and 'CallbackMetadata' in k:
                        items = v.get('Item') if isinstance(v, dict) else None
                        if items:
                            return items
                    res = find_items(v)
                    if res:
                        return res
            elif isinstance(obj, list):
                for v in obj:
                    res = find_items(v)
                    if res:
                        return res
            return None

        items = find_items(payload)
        if items:
            a, n = extract_from_items(items)
            amount = amount or a
            name = name or n

    # fallback simple fields
    amount = amount or payload.get('amount') or payload.get('Amount')
    name = name or payload.get('msisdn') or payload.get('phone') or payload.get('name') or 'Mpesa'

    try:
        amount = float(amount) if amount is not None else None
    except Exception:
        amount = None

    if amount is None:
        return jsonify({'error': 'no amount found in payload'}), 400

    entry = {
        'id': str(uuid.uuid4()),
        'from': name,
        'amount': amount,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'method': 'mpesa',
        'campaign_id': None
    }

    # associate with active campaign (if any)
    try:
        active = get_active_campaign()
        if active and active.get('id'):
            entry['campaign_id'] = active.get('id')
    except Exception:
        entry['campaign_id'] = None

    # insert into DB
    try:
        add_payment(entry)
    except Exception as e:
        current_app.logger.exception('db insert failed')
        return jsonify({'error': 'failed to write to DB', 'details': str(e)}), 500
    return jsonify({'status': 'ok'})


# Admin: view contributions
@app.route('/admin/contributions')
def admin_contributions():
    if not session.get('admin'):
        # Save desired endpoint so admin login can redirect back
        session['next'] = 'admin_contributions'
        return redirect(url_for('admin.admin_login'))
    summary = get_summary()
    payments = get_payments(500)
    updated = bool(request.args.get('ok'))
    campaigns = get_campaigns()
    audits = []
    try:
        audits = get_audits(200)
    except Exception:
        audits = []
    return render_template('admin_contributions.html', payments=payments, summary=summary, updated=updated, campaigns=campaigns, audits=audits)


# Temporary admin-only debug route to fetch recent server log lines.
# Useful when you can't copy the terminal output; shows tail of `logs/server.log`.
@app.route('/debug/logs')
def debug_logs():
    if not session.get('admin'):
        return redirect(url_for('admin.admin_login'))
    log_path = os.path.join(os.getcwd(), 'logs', 'server.log')
    if not os.path.exists(log_path):
        msg = (
            "No server log found at logs/server.log.\n"
            "Start the app with logging to file, for example:\n\n"
            "python app.py 2>&1 | Tee-Object -FilePath logs/server.log\n\n"
            "Then reproduce the error and refresh this page.\n"
        )
        return current_app.response_class(msg, mimetype='text/plain')

    # read last 500 lines
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            dq = deque(f, maxlen=500)
        text = ''.join(dq)
    except Exception as e:
        text = f'Failed to read log: {e}\n'
    return current_app.response_class(text, mimetype='text/plain')


@app.route('/admin/campaigns/create', methods=['POST'])
def create_campaign_route():
    if not session.get('admin'):
        session['next'] = 'create_campaign_route'
        return redirect(url_for('admin.admin_login'))
    title = request.form.get('title') or (request.json and request.json.get('title'))
    target = request.form.get('target_amount') or (request.json and request.json.get('target_amount'))
    if not title or not target:
        return redirect(url_for('admin_contributions'))
    try:
        target_f = float(target)
    except Exception:
        target_f = 0.0
    entry = {
        'id': str(uuid.uuid4()),
        'title': title,
        'description': '',
        'target_amount': target_f,
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'active': 0
    }
    try:
        # call DB helper directly (avoid name collision)
        create_campaign(entry)
    except Exception:
        current_app.logger.exception('failed create campaign')
    return redirect(url_for('admin_contributions'))


@app.route('/admin/campaigns/<campaign_id>/activate', methods=['POST'])
def activate_campaign(campaign_id):
    if not session.get('admin'):
        session['next'] = 'activate_campaign'
        return redirect(url_for('admin.admin_login'))
    try:
        set_active_campaign(campaign_id)
    except Exception:
        current_app.logger.exception('failed to activate')
    return redirect(url_for('admin_contributions'))


@app.route('/admin/campaigns/<campaign_id>/status', methods=['POST'])
def update_campaign_status(campaign_id):
    if not session.get('admin'):
        session['next'] = 'update_campaign_status'
        return redirect(url_for('admin.admin_login'))
    new_status = request.form.get('status') or (request.json and request.json.get('status'))
    if not new_status:
        return redirect(url_for('admin_contributions'))
    try:
        set_campaign_status(campaign_id, new_status)
    except Exception:
        current_app.logger.exception('failed to set campaign status')
    return redirect(url_for('admin_contributions'))


@app.route('/admin/contributions/export')
def export_contributions():
    if not session.get('admin'):
        session['next'] = 'export_contributions'
        return redirect(url_for('admin.admin_login'))
    payments = get_payments(10000)
    # build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'timestamp', 'from', 'amount', 'method', 'campaign_id', 'campaign_title'])
    for p in payments:
        cid = p.get('campaign_id')
        title = ''
        try:
            if cid:
                c = get_campaign(cid)
                title = c.get('title') if c else ''
        except Exception:
            title = ''
        writer.writerow([p.get('id'), p.get('timestamp'), p.get('from_name'), p.get('amount'), p.get('method'), cid, title])
    resp = current_app.response_class(output.getvalue(), mimetype='text/csv')
    resp.headers.set('Content-Disposition', 'attachment', filename='contributions.csv')
    return resp


@app.route('/admin/contributions/target', methods=['POST'])
def admin_set_target():
    if not session.get('admin'):
        session['next'] = 'admin_set_target'
        return redirect(url_for('admin.admin_login'))
    # accept form or JSON
    amt = None
    if request.form and 'target_amount' in request.form:
        amt = request.form.get('target_amount')
    else:
        data = request.get_json(silent=True) or {}
        amt = data.get('target_amount')

    try:
        amt_f = float(amt)
    except Exception:
        return jsonify({'error': 'invalid amount'}), 400

    try:
        set_target_amount(amt_f)
    except Exception as e:
        current_app.logger.exception('failed to set target')
        return jsonify({'error': 'failed to update target', 'details': str(e)}), 500

    return '', 302, {'Location': (request.referrer or '/admin/contributions') + '?ok=1'}


# Error handlers (optional but pro)
@app.errorhandler(404)
def not_found(_):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(_):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
