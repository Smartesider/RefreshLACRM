#!/usr/bin/env python3
"""
Debug script to investigate the 400 Bad Request errors when updating LACRM contacts.
This will help us understand the correct API call format.
"""

import configparser
import json
import requests
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Load config
config = configparser.ConfigParser()
config.read('config.ini')

LACRM_API_URL = "https://api.lessannoyingcrm.com"

def test_simple_update():
    """Test a very simple update with minimal data to isolate the issue"""
    print("🧪 Testing simple contact update...")
    
    # Use the first company we found: Trollhagen AS
    contact_id = "4036213232113780142605684247804"
    
    # Try a very simple custom field update
    simple_payload = {
        "4040961118050679815525241665363": "918124306"  # orgnr field with org number
    }
    
    data = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": "EditContact",
        "Parameters": json.dumps({
            "ContactId": contact_id,
            "CustomFields": simple_payload
        })
    }
    
    print(f"📦 Sending request:")
    print(f"   URL: {LACRM_API_URL}")
    print(f"   ContactId: {contact_id}")
    print(f"   Custom Fields: {simple_payload}")
    print(f"   Full Parameters: {data['Parameters']}")
    
    try:
        response = requests.post(LACRM_API_URL, data=data, timeout=15)
        print(f"📊 Response Status: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 400:
            print(f"❌ 400 Error - Response Text: {response.text}")
        
        result = response.json()
        print(f"📝 JSON Response: {json.dumps(result, indent=2)}")
        
        if result.get("Success"):
            print("✅ Update successful!")
        else:
            print(f"❌ LACRM API Error: {result}")
            
    except Exception as e:
        print(f"💥 Exception occurred: {e}")

def test_edit_contact_formats():
    """Test different EditContact API formats"""
    print("\n🧪 Testing different EditContact formats...")
    
    contact_id = "4036213232113780142605684247804"
    test_cases = [
        {
            "name": "Format 1: CustomFields as array",
            "parameters": {
                "ContactId": contact_id,
                "CustomFields": [
                    {
                        "CustomFieldId": "4040961118050679815525241665363",
                        "Value": "918124306"
                    }
                ]
            }
        },
        {
            "name": "Format 2: CustomFields as object",
            "parameters": {
                "ContactId": contact_id,
                "CustomFields": {
                    "4040961118050679815525241665363": "918124306"
                }
            }
        },
        {
            "name": "Format 3: Direct field assignment",
            "parameters": {
                "ContactId": contact_id,
                "4040961118050679815525241665363": "918124306"
            }
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n📋 Test Case {i}: {case['name']}")
        data = {
            "UserCode": config['LACRM']['UserCode'],
            "APIToken": config['LACRM']['APIToken'],
            "Function": "EditContact",
            "Parameters": json.dumps(case['parameters'])
        }
        
        try:
            response = requests.post(LACRM_API_URL, data=data, timeout=15)
            print(f"   Status: {response.status_code}")
            
            result = response.json()
            if result.get("Success"):
                print(f"   ✅ Success: {case['name']} works!")
                return case['name']  # Return the working format
            else:
                print(f"   ❌ Failed: {result.get('Result', 'Unknown error')}")
                
        except Exception as e:
            print(f"   💥 Exception: {e}")
    
    return None

def get_contact_details():
    """Get the current contact details to understand the structure"""
    print("\n🔍 Getting current contact details...")
    
    contact_id = "4036213232113780142605684247804"
    data = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": "GetContact",
        "Parameters": json.dumps({"ContactId": contact_id})
    }
    
    try:
        response = requests.post(LACRM_API_URL, data=data, timeout=15)
        result = response.json()
        
        if result.get("Success"):
            contact = result.get('Result', {})
            print(f"📄 Contact Name: {contact.get('Name', 'Unknown')}")
            print(f"📄 Contact Type: {contact.get('ContactType', 'Unknown')}")
            
            custom_fields = contact.get('CustomFields', [])
            print(f"📄 Current Custom Fields ({len(custom_fields)}):")
            for field in custom_fields:
                field_id = field.get('CustomFieldId', 'N/A')
                field_name = field.get('Name', 'Unknown')
                field_value = field.get('Value', 'Empty')
                print(f"   - {field_name} (ID: {field_id}): {field_value}")
        else:
            print(f"❌ Failed to get contact: {result}")
            
    except Exception as e:
        print(f"💥 Exception: {e}")

if __name__ == "__main__":
    print("🚀 Starting LACRM API Debug Investigation...")
    print("=" * 80)
    
    # First, get current contact details
    get_contact_details()
    
    # Test simple update
    test_simple_update()
    
    # Test different formats
    working_format = test_edit_contact_formats()
    
    if working_format:
        print(f"\n✅ SUCCESS: {working_format} is the correct format!")
    else:
        print("\n❌ No format worked. There may be a deeper API issue.")
    
    print("\n" + "=" * 80)
    print("🏁 Debug investigation complete!")
