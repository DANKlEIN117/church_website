from app import app
from db import get_campaigns, get_active_campaign

with app.app_context():
    campaigns = get_campaigns()
    print('Campaign list:')
    for c in campaigns:
        print(c)
    active = get_active_campaign()
    print('Active campaign:', active)
