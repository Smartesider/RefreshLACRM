#!/usr/bin/env python3
"""
Comprehensive LACRM API Test
Test all available LACRM API functions to identify permissions and capabilities
"""

import requests
import json
from typing import Dict, Any, List

# Your LACRM credentials
USER_CODE = "1101F8"
API_TOKEN = "1114616-4041135154939083599611185486179-EYWOhssSyM3ZfarQ8a03UHWmB6hq4gsM6pcE7N80SChL5RNWRU"
LACRM_URL = "https://api.lessannoyingcrm.com"

def make_api_call(function_name: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
    """Make a standardized API call to LACRM"""
    data = {
        'UserCode': USER_CODE,
        'APIToken': API_TOKEN,
        'Function': function_name
    }
    
    if parameters:
        data['Parameters'] = json.dumps(parameters)
    
    try:
        response = requests.post(LACRM_URL, data=data, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Success: {result.get('Success')}")
            if result.get('Success'):
                return result
            else:
                print(f"   ❌ API Error: {result.get('Result')}")
                return result
        else:
            print(f"   ❌ HTTP Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return {"Success": False, "Error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")
        return {"Success": False, "Error": str(e)}

def test_all_api_functions():
    """Test all known LACRM API functions"""
    print("🔧 COMPREHENSIVE LACRM API TEST")
    print("=" * 80)
    
    # List of all known LACRM API functions
    api_functions = [
        # Basic Info Functions
        ("GetAccount", None),
        ("GetUser", None),
        
        # Contact Functions
        ("GetContacts", {"NumRows": 5}),
        ("SearchContacts", {"SearchText": "test"}),
        ("GetContact", None),  # Will need ContactId
        
        # Custom Fields
        ("GetCustomFields", None),
        
        # Pipeline Functions
        ("GetPipelines", None),
        ("GetPipelineItems", None),
        ("GetPipelineReports", None),
        
        # Calendar/Event Functions
        ("GetEvents", None),
        ("GetCalendarItems", None),
        
        # Task Functions
        ("GetTasks", None),
        
        # Group Functions
        ("GetGroups", None),
        
        # File Functions
        ("GetFiles", None),
        
        # Note Functions
        ("GetNotes", None),
        
        # Lead Source Functions
        ("GetLeadSources", None),
        
        # Activity Functions
        ("GetActivities", None),
        
        # Report Functions
        ("GetReports", None),
        
        # Create/Edit Functions (read-only test)
        ("CreateContact", None),  # Will test without parameters to see error
        ("EditContact", None),
        ("CreatePipeline", None),
        ("CreatePipelineItem", None),
        ("CreateEvent", None),
        ("CreateTask", None),
        ("CreateNote", None),
    ]
    
    results = {}
    
    for function_name, params in api_functions:
        print(f"\n📋 Testing: {function_name}")
        print("-" * 40)
        
        result = make_api_call(function_name, params)
        results[function_name] = result
        
        if result.get('Success'):
            data = result.get('Result', [])
            if isinstance(data, list):
                print(f"   ✅ Success: Found {len(data)} items")
                if data and len(data) > 0:
                    # Show structure of first item
                    first_item = data[0]
                    if isinstance(first_item, dict):
                        print(f"   📊 Sample keys: {list(first_item.keys())[:5]}...")
            elif isinstance(data, dict):
                print(f"   ✅ Success: Returned object with keys: {list(data.keys())[:5]}...")
            else:
                print(f"   ✅ Success: Returned data type: {type(data)}")
        else:
            error_msg = result.get('Result', result.get('Error', 'Unknown error'))
            if "permission" in str(error_msg).lower():
                print(f"   🔒 Permission Error: {error_msg}")
            elif "not exist" in str(error_msg).lower():
                print(f"   ❓ Function doesn't exist: {error_msg}")
            else:
                print(f"   ⚠️  Other Error: {error_msg}")
    
    # Summary Report
    print("\n" + "=" * 80)
    print("📊 SUMMARY REPORT")
    print("=" * 80)
    
    successful = []
    permission_errors = []
    not_exist = []
    other_errors = []
    
    for func, result in results.items():
        if result.get('Success'):
            successful.append(func)
        else:
            error_msg = str(result.get('Result', result.get('Error', ''))).lower()
            if "permission" in error_msg:
                permission_errors.append(func)
            elif "not exist" in error_msg or "does not exist" in error_msg:
                not_exist.append(func)
            else:
                other_errors.append(func)
    
    print(f"\n✅ WORKING FUNCTIONS ({len(successful)}):")
    for func in successful:
        print(f"   - {func}")
    
    print(f"\n🔒 PERMISSION DENIED ({len(permission_errors)}):")
    for func in permission_errors:
        print(f"   - {func}")
    
    print(f"\n❓ FUNCTIONS DON'T EXIST ({len(not_exist)}):")
    for func in not_exist:
        print(f"   - {func}")
    
    print(f"\n⚠️  OTHER ERRORS ({len(other_errors)}):")
    for func in other_errors:
        print(f"   - {func}")
    
    # Test Custom Fields in detail if it worked
    if "GetCustomFields" in successful:
        print(f"\n📋 DETAILED CUSTOM FIELDS ANALYSIS")
        print("-" * 40)
        fields_result = results["GetCustomFields"]
        fields = fields_result.get('Result', [])
        
        contact_fields = []
        company_fields = []
        pipeline_fields = []
        
        for field in fields:
            applies_to = field.get('AppliesTo', 'Unknown')
            field_name = field.get('Name', 'Unknown')
            field_id = field.get('FieldId', 'N/A')
            field_type = field.get('Type', 'Unknown')
            
            field_info = {
                'name': field_name,
                'id': field_id,
                'type': field_type,
                'applies_to': applies_to
            }
            
            if applies_to == 'Contact':
                contact_fields.append(field_info)
            elif applies_to == 'Company':
                company_fields.append(field_info)
            elif applies_to == 'Pipeline':
                pipeline_fields.append(field_info)
        
        print(f"📞 Contact Fields ({len(contact_fields)}):")
        for field in contact_fields:
            print(f"   - {field['name']} (ID: {field['id']}, Type: {field['type']})")
        
        print(f"\n🏢 Company Fields ({len(company_fields)}):")
        for field in company_fields:
            print(f"   - {field['name']} (ID: {field['id']}, Type: {field['type']})")
        
        print(f"\n📊 Pipeline Fields ({len(pipeline_fields)}):")
        for field in pipeline_fields:
            print(f"   - {field['name']} (ID: {field['id']}, Type: {field['type']})")
    
    # Test Contacts in detail if it worked
    if "GetContacts" in successful:
        print(f"\n👥 DETAILED CONTACTS ANALYSIS")
        print("-" * 40)
        contacts_result = results["GetContacts"]
        contacts = contacts_result.get('Result', [])
        
        if contacts:
            sample_contact = contacts[0]
            print(f"📋 Sample Contact Structure:")
            for key, value in sample_contact.items():
                if isinstance(value, list) and value:
                    print(f"   - {key}: [{len(value)} items] - Sample: {value[0] if value else 'Empty'}")
                else:
                    print(f"   - {key}: {type(value).__name__} = {str(value)[:50]}...")

if __name__ == "__main__":
    test_all_api_functions()
