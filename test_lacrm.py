#!/usr/bin/env python3
"""
Simple LACRM API Test
Test LACRM connectivity without complex dependencies
"""

import requests
import json

# Your LACRM credentials
USER_CODE = "1101F8"
API_TOKEN = "1114616-4041135154939083599611185486179-EYWOhssSyM3ZfarQ8a03UHWmB6hq4gsM6pcE7N80SChL5RNWRU"
LACRM_URL = "https://api.lessannoyingcrm.com"

def test_lacrm_connection():
    """Test basic LACRM API connection"""
    print("🔧 Testing LACRM API Connection...")
    
    # Test 1: GetContacts
    print("\n1️⃣ Testing GetContacts...")
    contacts_data = {
        'UserCode': USER_CODE,
        'APIToken': API_TOKEN,
        'Function': 'GetContacts',
        'NumRows': 1
    }
    
    try:
        response = requests.post(LACRM_URL, data=contacts_data, timeout=30)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Success: {result.get('Success')}")
            if result.get('Success'):
                contacts = result.get('Result', [])
                print(f"   ✅ Found {len(contacts)} contacts")
                if contacts:
                    print(f"   First contact: {contacts[0].get('CompanyName', 'No company name')}")
            else:
                print(f"   ❌ API Error: {result.get('Result')}")
        else:
            print(f"   ❌ HTTP Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")
    
    # Test 2: GetCustomFields
    print("\n2️⃣ Testing GetCustomFields...")
    fields_data = {
        'UserCode': USER_CODE,
        'APIToken': API_TOKEN,
        'Function': 'GetCustomFields'
    }
    
    try:
        response = requests.post(LACRM_URL, data=fields_data, timeout=30)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Success: {result.get('Success')}")
            if result.get('Success'):
                fields = result.get('Result', [])
                print(f"   ✅ Found {len(fields)} custom fields")
                for field in fields[:3]:  # Show first 3
                    print(f"     - {field.get('Name', 'Unknown')} (ID: {field.get('FieldId', 'N/A')})")
            else:
                print(f"   ❌ API Error: {result.get('Result')}")
        else:
            print(f"   ❌ HTTP Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")

if __name__ == "__main__":
    test_lacrm_connection()
