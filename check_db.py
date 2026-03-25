#!/usr/bin/env python3
from app import app
from db import get_payments

with app.app_context():
    payments = get_payments(5)
    print('Recent payments:')
    for p in payments:
        campaign = p.get('campaign_id', 'None')
        print(f"{p['amount']} KSH - {p.get('category', 'N/A')} - {p['from_name']} - Campaign: {campaign}")