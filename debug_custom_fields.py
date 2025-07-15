#!/usr/bin/env python3
"""
Debug Custom Fields API Call
Purpose: Investigate why GetCustomFields returns 0 fields when fields exist in LACRM
"""

import requests
import json
import configparser
from typing import Dict, Any, List

def load_config() -> configparser.ConfigParser:
    """Load configuration from config.ini"""
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config

def debug_custom_fields_api():
    """Debug the GetCustomFields API call with detailed logging"""
    config = load_config()
    
    print("🔍 DEBUGGING LACRM CUSTOM FIELDS API CALL")
    print("="*60)
    
    # Test the exact API call
    data = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": "GetCustomFields"
    }
    
    print(f"📦 Request Data:")
    print(f"   UserCode: {data['UserCode']}")
    print(f"   APIToken: {data['APIToken'][:20]}...")
    print(f"   Function: {data['Function']}")
    print(f"   URL: https://api.lessannoyingcrm.com")
    
    try:
        print(f"\n🌐 Sending request...")
        response = requests.post("https://api.lessannoyingcrm.com", data=data, timeout=30)
        
        print(f"✅ Response Status: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"\n📊 JSON Response Structure:")
                print(f"   Success: {result.get('Success')}")
                print(f"   Result Type: {type(result.get('Result'))}")
                
                if result.get('Success'):
                    custom_fields = result.get('Result', [])
                    print(f"   Fields Count: {len(custom_fields) if isinstance(custom_fields, list) else 'Not a list'}")
                    
                    if isinstance(custom_fields, list):
                        print(f"\n📝 Full Response Content:")
                        print(json.dumps(result, indent=2))
                        
                        if len(custom_fields) > 0:
                            print(f"\n🎯 First Field Structure:")
                            first_field = custom_fields[0]
                            for key, value in first_field.items():
                                print(f"   {key}: {value}")
                        else:
                            print(f"\n⚠️ ISSUE IDENTIFIED: API returns empty list but you say fields exist!")
                            print(f"   This suggests one of these issues:")
                            print(f"   1. API permissions don't include custom field access")
                            print(f"   2. Custom fields are not properly configured in LACRM")
                            print(f"   3. Custom fields exist but are not 'active' or 'published'")
                            print(f"   4. Different API endpoint needed for custom fields")
                    else:
                        print(f"\n❌ Result is not a list: {result.get('Result')}")
                else:
                    print(f"\n❌ API returned Success=False")
                    print(f"   Error: {result.get('Result')}")
                    
            except json.JSONDecodeError as e:
                print(f"\n❌ JSON Decode Error: {e}")
                print(f"Raw response: {response.text[:500]}...")
        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
            print(f"Response text: {response.text[:500]}...")
            
    except requests.exceptions.RequestException as e:
        print(f"\n🚨 Request Error: {e}")

def test_alternative_api_calls():
    """Test alternative ways to get custom fields"""
    config = load_config()
    
    print(f"\n{'='*60}")
    print("🔄 TESTING ALTERNATIVE API APPROACHES")
    print("="*60)
    
    # Test different function names that might return custom fields
    alternative_functions = [
        "GetCustomFields",
        "GetFields", 
        "GetContactFields",
        "GetCompanyFields",
        "GetContactCustomFields",
        "GetCompanyCustomFields",
        "ListCustomFields",
        "DescribeFields"
    ]
    
    for func_name in alternative_functions:
        print(f"\n🧪 Testing Function: {func_name}")
        
        data = {
            "UserCode": config['LACRM']['UserCode'],
            "APIToken": config['LACRM']['APIToken'],
            "Function": func_name
        }
        
        try:
            response = requests.post("https://api.lessannoyingcrm.com", data=data, timeout=10)
            result = response.json()
            
            if result.get('Success'):
                fields = result.get('Result', [])
                if isinstance(fields, list) and len(fields) > 0:
                    print(f"   ✅ SUCCESS! Found {len(fields)} fields")
                    print(f"   📋 First field: {fields[0] if fields else 'None'}")
                else:
                    print(f"   ⚠️ Success but no fields: {fields}")
            else:
                print(f"   ❌ Failed: {result.get('Result', 'Unknown error')}")
                
        except Exception as e:
            print(f"   🚨 Error: {e}")

def test_with_parameters():
    """Test GetCustomFields with different parameters"""
    config = load_config()
    
    print(f"\n{'='*60}")
    print("🎛️ TESTING WITH DIFFERENT PARAMETERS")
    print("="*60)
    
    # Test different parameter combinations
    parameter_sets = [
        {},  # No parameters
        {"AppliesTo": "Contact"},
        {"AppliesTo": "Company"},
        {"AppliesTo": "Pipeline"},
        {"IncludeInactive": "true"},
        {"IncludeInactive": "false"},
        {"Type": "Text"},
        {"Type": "Number"},
        {"ActiveOnly": "true"},
        {"ActiveOnly": "false"}
    ]
    
    for i, params in enumerate(parameter_sets):
        print(f"\n🧪 Test {i+1}: Parameters = {params}")
        
        data = {
            "UserCode": config['LACRM']['UserCode'],
            "APIToken": config['LACRM']['APIToken'],
            "Function": "GetCustomFields"
        }
        
        if params:
            data["Parameters"] = json.dumps(params)
        
        try:
            response = requests.post("https://api.lessannoyingcrm.com", data=data, timeout=10)
            result = response.json()
            
            if result.get('Success'):
                fields = result.get('Result', [])
                if isinstance(fields, list) and len(fields) > 0:
                    print(f"   ✅ SUCCESS! Found {len(fields)} fields")
                    for field in fields[:2]:  # Show first 2 fields
                        print(f"      - {field.get('Name', 'No Name')} (ID: {field.get('FieldId', 'No ID')})")
                else:
                    print(f"   ⚠️ Success but no fields returned")
            else:
                print(f"   ❌ Failed: {result.get('Result', 'Unknown error')}")
                
        except Exception as e:
            print(f"   🚨 Error: {e}")

def check_existing_contact_fields():
    """Check if we can see custom fields in actual contact data"""
    config = load_config()
    
    print(f"\n{'='*60}")
    print("👁️ CHECKING CUSTOM FIELDS IN ACTUAL CONTACTS")
    print("="*60)
    
    # Get a sample contact to see if it has custom fields
    data = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": "SearchContacts",
        "Parameters": json.dumps({"SearchText": ""})
    }
    
    try:
        response = requests.post("https://api.lessannoyingcrm.com", data=data, timeout=30)
        result = response.json()
        
        if result.get('Success'):
            contacts = result.get('Result', [])
            print(f"📊 Found {len(contacts)} contacts")
            
            if contacts:
                # Check first few contacts for custom fields
                for i, contact in enumerate(contacts[:3]):
                    print(f"\n🔍 Contact {i+1}: {contact.get('FirstName', 'No Name')}")
                    
                    custom_fields = contact.get('CustomFields', [])
                    print(f"   CustomFields Type: {type(custom_fields)}")
                    print(f"   CustomFields Length: {len(custom_fields) if isinstance(custom_fields, list) else 'Not a list'}")
                    
                    if isinstance(custom_fields, list) and custom_fields:
                        print(f"   📋 Custom Fields Found:")
                        for field in custom_fields:
                            if isinstance(field, dict):
                                field_id = field.get('FieldId', 'No ID')
                                field_value = field.get('Value', 'No Value')
                                print(f"      - FieldId: {field_id}, Value: {field_value}")
                    else:
                        print(f"   ⚠️ No custom fields in this contact")
                        
                    # Also check ContactCustomFields
                    contact_custom_fields = contact.get('ContactCustomFields')
                    if contact_custom_fields:
                        print(f"   📋 ContactCustomFields: {contact_custom_fields}")
            else:
                print(f"❌ No contacts found")
        else:
            print(f"❌ Failed to get contacts: {result.get('Result')}")
            
    except Exception as e:
        print(f"🚨 Error: {e}")

if __name__ == "__main__":
    print("🚀 Starting Custom Fields Debug Investigation...")
    
    # Run all debug tests
    debug_custom_fields_api()
    test_alternative_api_calls() 
    test_with_parameters()
    check_existing_contact_fields()
    
    print(f"\n{'='*60}")
    print("📋 SUMMARY & RECOMMENDATIONS")
    print("="*60)
    print("1. Check the API response details above")
    print("2. Look for any successful alternative function calls")
    print("3. Check if custom fields appear in actual contact data")
    print("4. Verify custom field configuration in LACRM web interface")
    print("="*60)
