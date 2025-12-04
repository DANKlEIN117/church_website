import sqlite3
import os
from flask import g, session
from datetime import datetime
import uuid

DB_PATH = os.getenv('CONTRIB_DB', os.path.join(os.getcwd(), 'contributions.db'))


def get_db():
    if 'db' not in g:
        conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables from schema.sql (idempotent)."""
    dbdir = os.path.dirname(DB_PATH)
    if dbdir and not os.path.exists(dbdir):
        os.makedirs(dbdir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    if os.path.exists(schema_path):
        with open(schema_path, 'rb') as f:
            conn.executescript(f.read().decode('utf-8'))
    else:
        # fallback: create minimal tables
        cur.executescript('''
        CREATE TABLE IF NOT EXISTS contributions (
            id TEXT PRIMARY KEY,
            from_name TEXT,
            amount REAL NOT NULL,
            timestamp TEXT,
            method TEXT
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        INSERT OR IGNORE INTO meta(key, value) VALUES('target_amount', '100000.0');
        ''')
    conn.commit()
    conn.close()

    # Ensure schema evolution: add campaign_id to contributions if missing
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(contributions)")
        cols = [r[1] for r in cur.fetchall()]
        if 'campaign_id' not in cols:
            cur.execute('ALTER TABLE contributions ADD COLUMN campaign_id TEXT')
    except Exception:
        pass

    # ensure campaigns table has status column
    try:
        cur.execute("PRAGMA table_info(campaigns)")
        crow = cur.fetchall()
        if crow:
            ccols = [r[1] for r in crow]
            if 'status' not in ccols:
                cur.execute("ALTER TABLE campaigns ADD COLUMN status TEXT DEFAULT 'pending'")
    except Exception:
        pass

    conn.commit()
    conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def add_payment(entry):
    db = get_db()
    db.execute('INSERT INTO contributions(id, from_name, amount, timestamp, method, campaign_id) VALUES (?, ?, ?, ?, ?, ?)',
               (entry['id'], entry.get('from'), entry.get('amount'), entry.get('timestamp'), entry.get('method'), entry.get('campaign_id')))
    db.commit()


def create_campaign(entry):
    db = get_db()
    # Try to insert using `status` column; if the DB still has the old `active` column,
    # fall back to inserting into `active` (1 for active, 0 otherwise).
    try:
        db.execute('INSERT INTO campaigns(id, title, description, target_amount, created_at, status) VALUES(?, ?, ?, ?, ?, ?)',
                   (entry['id'], entry.get('title'), entry.get('description'), entry.get('target_amount'), entry.get('created_at'), entry.get('status', 'pending')))
    except sqlite3.OperationalError:
        active_flag = 1 if entry.get('status') == 'active' or entry.get('active') else 0
        db.execute('INSERT INTO campaigns(id, title, description, target_amount, created_at, active) VALUES(?, ?, ?, ?, ?, ?)',
                   (entry['id'], entry.get('title'), entry.get('description'), entry.get('target_amount'), entry.get('created_at'), active_flag))
    db.commit()


def get_campaigns():
    db = get_db()
    try:
        cur = db.execute('SELECT id, title, description, target_amount, created_at, status FROM campaigns ORDER BY created_at DESC')
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        # older schema: no `status` column, fall back to `active` flag
        cur = db.execute('SELECT id, title, description, target_amount, created_at, active FROM campaigns ORDER BY created_at DESC')
        rows = cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d['status'] = 'active' if d.get('active') else 'inactive'
            out.append(d)
        return out


def set_active_campaign(campaign_id):
    db = get_db()
    # determine actor if available
    actor = None
    try:
        actor = session.get('admin_user') or ('admin' if session.get('admin') else None)
    except Exception:
        actor = None

    # find previously active campaign (if any)
    prev = get_active_campaign()
    prev_id = prev.get('id') if prev else None
    prev_status = prev.get('status') if prev else None

    # set all to inactive/pending (prefer `status` column)
    try:
        db.execute("UPDATE campaigns SET status = 'inactive' WHERE status = 'active'")
        # activate the requested one
        db.execute("UPDATE campaigns SET status = 'active' WHERE id = ?", (campaign_id,))
    except sqlite3.OperationalError:
        # fallback: older schema used `active` integer flag
        db.execute("UPDATE campaigns SET active = 0 WHERE active = 1")
        db.execute("UPDATE campaigns SET active = 1 WHERE id = ?", (campaign_id,))
    # store in meta for quick lookup
    db.execute('INSERT INTO meta(key,value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('active_campaign_id', campaign_id))
    db.commit()

    # audit: record deactivation of previous active campaign
    try:
        if prev_id and prev_id != campaign_id:
            add_audit(prev_id, actor or 'system', 'deactivate', prev_status, 'inactive')
        # record activation of new campaign
        cur = db.execute('SELECT status FROM campaigns WHERE id = ?', (campaign_id,))
        row = cur.fetchone()
        # if `status` missing, fall back to `active` field mapping
        old_status = None
        try:
            old_status = row['status'] if row else None
        except Exception:
            # try to read active flag
            try:
                crow = db.execute('SELECT active FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()
                old_status = 'active' if crow and crow['active'] else 'inactive'
            except Exception:
                old_status = None
        add_audit(campaign_id, actor or 'system', 'activate', old_status, 'active')
    except Exception:
        # don't let auditing failures break activation
        pass


def set_campaign_status(campaign_id, status):
    db = get_db()
    # determine actor if available
    actor = None
    try:
        actor = session.get('admin_user') or ('admin' if session.get('admin') else None)
    except Exception:
        actor = None

    # read old status for audit
    cur = db.execute('SELECT status FROM campaigns WHERE id = ?', (campaign_id,))
    row = cur.fetchone()
    old_status = row['status'] if row else None

    # Prefer updating `status`; if missing, fall back to `active` integer flag.
    try:
        db.execute('UPDATE campaigns SET status = ? WHERE id = ?', (status, campaign_id))
        # if setting active, update meta; if unsetting active and meta points to this, clear it
        if status == 'active':
            db.execute('INSERT INTO meta(key,value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('active_campaign_id', campaign_id))
        else:
            cur = db.execute("SELECT value FROM meta WHERE key='active_campaign_id'")
            row = cur.fetchone()
            if row and row['value'] == campaign_id:
                db.execute("INSERT INTO meta(key,value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", ('active_campaign_id', ''))
    except sqlite3.OperationalError:
        # fallback to active flag
        if status == 'active':
            db.execute("UPDATE campaigns SET active = 0 WHERE active = 1")
            db.execute("UPDATE campaigns SET active = 1 WHERE id = ?", (campaign_id,))
            db.execute('INSERT INTO meta(key,value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('active_campaign_id', campaign_id))
        else:
            # set active=0 for this campaign; if meta points to it, clear
            db.execute("UPDATE campaigns SET active = 0 WHERE id = ?", (campaign_id,))
            cur = db.execute("SELECT value FROM meta WHERE key='active_campaign_id'")
            row = cur.fetchone()
            if row and row['value'] == campaign_id:
                db.execute("INSERT INTO meta(key,value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", ('active_campaign_id', ''))
    db.commit()

    # audit: record status change
    try:
        add_audit(campaign_id, actor or 'system', 'status_change', old_status, status)
    except Exception:
        pass


def add_audit(campaign_id, actor, action, old_status, new_status, timestamp=None):
    db = get_db()
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat() + 'Z'
    db.execute('INSERT INTO audits(id, campaign_id, actor, action, old_status, new_status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)',
               (str(uuid.uuid4()), campaign_id, actor, action, old_status, new_status, timestamp))
    db.commit()


def get_audits(limit=100):
    db = get_db()
    cur = db.execute('SELECT id, campaign_id, actor, action, old_status, new_status, timestamp FROM audits ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_campaign(campaign_id):
    db = get_db()
    try:
        cur = db.execute('SELECT id, title, description, target_amount, created_at, status FROM campaigns WHERE id = ?', (campaign_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        cur = db.execute('SELECT id, title, description, target_amount, created_at, active FROM campaigns WHERE id = ?', (campaign_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d['status'] = 'active' if d.get('active') else 'inactive'
        return d


def get_active_campaign():
    db = get_db()
    cur = db.execute("SELECT value FROM meta WHERE key='active_campaign_id'")
    r = cur.fetchone()
    cid = r['value'] if r else None
    if cid:
        try:
            ccur = db.execute('SELECT id, title, description, target_amount, created_at, status FROM campaigns WHERE id = ?', (cid,))
            crow = ccur.fetchone()
            return dict(crow) if crow else None
        except sqlite3.OperationalError:
            ccur = db.execute('SELECT id, title, description, target_amount, created_at, active FROM campaigns WHERE id = ?', (cid,))
            crow = ccur.fetchone()
            if not crow:
                return None
            d = dict(crow)
            d['status'] = 'active' if d.get('active') else 'inactive'
            return d
    # fallback: find first active
    try:
        ccur = db.execute("SELECT id, title, description, target_amount, created_at, status FROM campaigns WHERE status = 'active' LIMIT 1")
        crow = ccur.fetchone()
        return dict(crow) if crow else None
    except sqlite3.OperationalError:
        ccur = db.execute("SELECT id, title, description, target_amount, created_at, active FROM campaigns WHERE active = 1 LIMIT 1")
        crow = ccur.fetchone()
        if not crow:
            return None
        d = dict(crow)
        d['status'] = 'active' if d.get('active') else 'inactive'
        return d


def get_payments(limit=100):
    db = get_db()
    cur = db.execute('SELECT id, from_name, amount, timestamp, method, campaign_id FROM contributions ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_summary(campaign_id=None):
    db = get_db()
    if campaign_id:
        cur = db.execute('SELECT SUM(amount) AS total FROM contributions WHERE campaign_id = ?', (campaign_id,))
    else:
        cur = db.execute('SELECT SUM(amount) AS total FROM contributions')
    row = cur.fetchone()
    total = row['total'] or 0.0
    if campaign_id:
        # campaign-specific target
        cur2 = db.execute('SELECT target_amount FROM campaigns WHERE id = ?', (campaign_id,))
        r2 = cur2.fetchone()
        try:
            target = float(r2['target_amount']) if r2 and r2['target_amount'] is not None else 0.0
        except Exception:
            target = 0.0
    else:
        cur2 = db.execute("SELECT value FROM meta WHERE key='target_amount'")
        r2 = cur2.fetchone()
        try:
            target = float(r2['value']) if r2 and r2['value'] is not None else 0.0
        except Exception:
            target = 0.0
    remaining = max(0.0, target - total)
    percent = round((total / target) * 100.0, 2) if target > 0 else 0.0
    return {'target_amount': target, 'total_contributed': total, 'remaining': remaining, 'percent': percent}


def set_target_amount(amount):
    db = get_db()
    db.execute('INSERT INTO meta(key,value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('target_amount', str(amount)))
    db.commit()
