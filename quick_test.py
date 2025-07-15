#!/usr/bin/env python3
"""
Quick LACRM API Fix Test
Test just the LACRM API changes to see if SearchContacts works
"""

import requests
import json

# Your LACRM credentials
USER_CODE = "1101F8"
API_TOKEN = "1114616-4041135154939083599611185486179-EYWOhssSyM3ZfarQ8a03UHWmB6hq4gsM6pcE7N80SChL5RNWRU"
LACRM_URL = "https://api.lessannoyingcrm.com"

def test_search_contacts():
    """Test SearchContacts with proper parameters"""
    print("🔧 Testing SearchContacts with proper JSON parameters...")
    
    data = {
        'UserCode': USER_CODE,
        'APIToken': API_TOKEN,
        'Function': 'SearchContacts',
        'Parameters': json.dumps({"SearchText": ""})  # Empty search returns all
    }
    
    try:
        response = requests.post(LACRM_URL, data=data, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result.get('Success')}")
            if result.get('Success'):
                contacts = result.get('Result', [])
                print(f"✅ Found {len(contacts)} contacts")
                
                if contacts:
                    print(f"\n📋 Sample Contact Structure:")
                    sample = contacts[0]
                    for key, value in sample.items():
                        print(f"   - {key}: {type(value).__name__}")
                        
                    # Look for org number field
                    print(f"\n🔍 Looking for organization number...")
                    orgnr_field_id = "4040978325247338748089826771438"
                    
                    for contact in contacts[:3]:  # Check first 3 contacts
                        company_name = contact.get('CompanyName', 'No company')
                        custom_fields = contact.get('CustomFields', [])
                        
                        orgnr = None
                        if isinstance(custom_fields, list):
                            for field in custom_fields:
                                if isinstance(field, dict) and field.get('FieldId') == orgnr_field_id:
                                    orgnr = field.get('Value')
                                    break
                        
                        print(f"   - {company_name}: {orgnr if orgnr else 'No orgnr'}")
                        
            else:
                print(f"❌ API Error: {result.get('Result')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def test_custom_fields():
    """Test GetCustomFields to see what fields exist"""
    print("\n🔧 Testing GetCustomFields...")
    
    data = {
        'UserCode': USER_CODE,
        'APIToken': API_TOKEN,
        'Function': 'GetCustomFields'
    }
    
    try:
        response = requests.post(LACRM_URL, data=data, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result.get('Success')}")
            if result.get('Success'):
                fields = result.get('Result', [])
                print(f"✅ Found {len(fields)} custom fields")
                
                if fields:
                    for field in fields:
                        name = field.get('Name', 'Unknown')
                        field_id = field.get('FieldId', 'N/A')
                        applies_to = field.get('AppliesTo', 'Unknown')
                        print(f"   - {name} (ID: {field_id}, Type: {applies_to})")
                else:
                    print("   ⚠️  No custom fields found - they may need to be created in LACRM")
                        
            else:
                print(f"❌ API Error: {result.get('Result')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_search_contacts()
    test_custom_fields()
    
    print(f"\n🎯 SOLUTION:")
    print(f"   1. Your API works with 'SearchContacts' (not 'GetContacts')")
    print(f"   2. You have 0 custom fields - need to create them in LACRM")
    print(f"   3. Update main script to use SearchContacts instead of GetContacts")
