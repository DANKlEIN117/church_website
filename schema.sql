-- Schema for contributions
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

-- Campaigns table: create named contribution targets that can be activated by admin
CREATE TABLE IF NOT EXISTS campaigns (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  target_amount REAL,
  created_at TEXT,
  active INTEGER DEFAULT 0
);

-- store active campaign id if desired
INSERT OR IGNORE INTO meta(key, value) VALUES('active_campaign_id', '');

-- Audit log for campaign status changes and admin actions
CREATE TABLE IF NOT EXISTS audits (
  id TEXT PRIMARY KEY,
  campaign_id TEXT,
  actor TEXT,
  action TEXT,
  old_status TEXT,
  new_status TEXT,
  timestamp TEXT
);
