#!/usr/bin/env python3
"""
Test script for C2B webhook. Run this to simulate a C2B callback.
Usage: python test_c2b.py
"""

import requests
import json
import hmac
import hashlib
import base64
import os
from dotenv import load_dotenv

# Load env
load_dotenv()

# Sample C2B payload (validation/confirmation)
sample_payload = {
    "TransactionType": "Pay Bill",
    "TransID": "TEST123456791",  # Changed again
    "TransTime": "20240325120000",
    "TransAmount": "50000.00",
    "BusinessShortCode": "174379",
    "BillRefNumber": "WELFARE",  # Account reference for categorization
    "InvoiceNumber": "",
    "OrgAccountBalance": "10000.00",
    "ThirdPartyTransID": "thirdparty123",
    "MSISDN": "254712345678",
    "FirstName": "John",
    "MiddleName": "Doe",
    "LastName": "Smith"
}

# Webhook URL (local)
WEBHOOK_URL = "http://localhost:5000/contributions/webhook"

# Secret for HMAC
SECRET = os.getenv('MPESA_WEBHOOK_SECRET', 'testsecret')

def compute_signature(payload, secret):
    data = json.dumps(payload).encode('utf-8')
    mac = hmac.new(secret.encode('utf-8'), data, hashlib.sha256).digest()
    return base64.b64encode(mac).decode()

def test_webhook():
    headers = {
        'Content-Type': 'application/json'
    }

    if SECRET:
        sig = compute_signature(sample_payload, SECRET)
        headers['X-Mpesa-Signature'] = sig
        print(f"Using signature: {sig}")

    print("Sending C2B payload to webhook...")
    print(json.dumps(sample_payload, indent=2))

    try:
        response = requests.post(WEBHOOK_URL, json=sample_payload, headers=headers, timeout=10)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_webhook()