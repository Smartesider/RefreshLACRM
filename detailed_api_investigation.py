#!/usr/bin/env python3
"""
Detailed LACRM API Investigation Script
Purpose: Investigate why we're not seeing companies in LACRM API responses
"""

import requests
import json
import configparser
from typing import Dict, Any, List, Optional

def load_config() -> configparser.ConfigParser:
    """Load configuration from config.ini"""
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config

def test_lacrm_api_function(config: configparser.ConfigParser, function_name: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
    """Test a specific LACRM API function with detailed logging"""
    print(f"\n{'='*60}")
    print(f"🔍 Testing LACRM API Function: {function_name}")
    print(f"{'='*60}")
    
    data = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": function_name
    }
    
    if parameters:
        data["Parameters"] = json.dumps(parameters)
        print(f"📋 Parameters: {json.dumps(parameters, indent=2)}")
    
    try:
        print(f"🌐 Sending request to: https://api.lessannoyingcrm.com")
        print(f"📦 Request data: {json.dumps({k: v if k != 'APIToken' else '[HIDDEN]' for k, v in data.items()}, indent=2)}")
        
        response = requests.post("https://api.lessannoyingcrm.com", data=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Response Status: {response.status_code}")
        print(f"📊 Response Success: {result.get('Success', 'Unknown')}")
        
        if result.get('Success'):
            result_data = result.get('Result', [])
            if isinstance(result_data, list):
                print(f"📈 Results Count: {len(result_data)}")
                if result_data:
                    print(f"🔎 First Result Keys: {list(result_data[0].keys()) if result_data[0] else 'Empty'}")
                    print(f"📝 First Result Sample:")
                    print(json.dumps(result_data[0], indent=2, default=str))
            else:
                print(f"📈 Result Type: {type(result_data)}")
                print(f"📝 Result Content:")
                print(json.dumps(result_data, indent=2, default=str))
        else:
            print(f"❌ API Error: {result.get('Result', 'Unknown error')}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"🚨 Request Error: {e}")
        return {"Success": False, "Error": str(e)}
    except json.JSONDecodeError as e:
        print(f"🚨 JSON Decode Error: {e}")
        return {"Success": False, "Error": f"JSON decode error: {e}"}

def investigate_companies_vs_contacts():
    """Detailed investigation of companies vs contacts in LACRM"""
    config = load_config()
    
    print("🏢 LACRM API COMPANIES VS CONTACTS INVESTIGATION")
    print("="*70)
    
    # Test different ways to get companies
    company_functions = [
        ("GetCompanies", None),
        ("SearchCompanies", {"SearchText": ""}),
        ("SearchCompanies", {"SearchText": "*"}),
        ("GetContacts", None),
        ("SearchContacts", {"SearchText": ""}),
        ("SearchContacts", {"SearchText": "*"}),
    ]
    
    results = {}
    
    for func_name, params in company_functions:
        result = test_lacrm_api_function(config, func_name, params)
        results[f"{func_name}_{params}"] = result
        
        # If successful, analyze the structure
        if result.get('Success') and result.get('Result'):
            data = result.get('Result', [])
            if isinstance(data, list) and data:
                sample = data[0]
                print(f"\n📋 STRUCTURE ANALYSIS for {func_name}:")
                print(f"   - Total records: {len(data)}")
                print(f"   - Sample record keys: {list(sample.keys())}")
                
                # Look for company-specific fields
                company_indicators = ['CompanyId', 'CompanyName', 'Company']
                contact_indicators = ['ContactId', 'FirstName', 'LastName', 'Email']
                
                has_company_fields = any(key in sample for key in company_indicators)
                has_contact_fields = any(key in sample for key in contact_indicators)
                
                print(f"   - Has company fields: {has_company_fields}")
                print(f"   - Has contact fields: {has_contact_fields}")
                
                # Check for relationships
                if 'CompanyId' in sample:
                    company_ids = [record.get('CompanyId') for record in data if record.get('CompanyId')]
                    unique_company_ids = set(company_ids)
                    print(f"   - Unique CompanyIds found: {len(unique_company_ids)}")
                    print(f"   - Sample CompanyIds: {list(unique_company_ids)[:5]}")
                
                if 'CompanyName' in sample:
                    company_names = [record.get('CompanyName') for record in data if record.get('CompanyName')]
                    unique_company_names = set(company_names)
                    print(f"   - Unique CompanyNames found: {len(unique_company_names)}")
                    print(f"   - Sample CompanyNames: {list(unique_company_names)[:5]}")
    
    # Test GetCustomFields to understand field structure
    print(f"\n{'='*70}")
    print("🏷️ CUSTOM FIELDS INVESTIGATION")
    print(f"{'='*70}")
    
    custom_fields_result = test_lacrm_api_function(config, "GetCustomFields", None)
    if custom_fields_result.get('Success'):
        fields = custom_fields_result.get('Result', [])
        if fields:
            print(f"\n📊 CUSTOM FIELDS BREAKDOWN:")
            applies_to_counts = {}
            for field in fields:
                applies_to = field.get('AppliesTo', 'Unknown')
                applies_to_counts[applies_to] = applies_to_counts.get(applies_to, 0) + 1
                
                if applies_to == 'Company':
                    print(f"   🏢 Company Field: {field.get('Name')} (ID: {field.get('FieldId')})")
            
            print(f"\n📈 Fields by type: {applies_to_counts}")
    
    return results

def test_specific_company_access():
    """Test accessing specific companies if we can find CompanyIds"""
    config = load_config()
    
    print(f"\n{'='*70}")
    print("🎯 SPECIFIC COMPANY ACCESS TEST")
    print(f"{'='*70}")
    
    # First, try to get contacts and extract CompanyIds
    contacts_result = test_lacrm_api_function(config, "SearchContacts", {"SearchText": ""})
    
    if contacts_result.get('Success'):
        contacts = contacts_result.get('Result', [])
        company_ids = set()
        
        for contact in contacts:
            company_id = contact.get('CompanyId')
            if company_id and company_id != 'NoneType':
                company_ids.add(company_id)
        
        print(f"🔍 Found {len(company_ids)} unique CompanyIds from contacts")
        
        if company_ids:
            # Test GetCompany with a specific ID
            sample_company_id = list(company_ids)[0]
            print(f"🎯 Testing GetCompany with CompanyId: {sample_company_id}")
            
            company_result = test_lacrm_api_function(config, "GetCompany", {"CompanyId": sample_company_id})
            
            if company_result.get('Success'):
                company_data = company_result.get('Result')
                print(f"✅ Successfully retrieved company data!")
                print(f"📋 Company data keys: {list(company_data.keys()) if isinstance(company_data, dict) else 'Not a dict'}")
            else:
                print(f"❌ Failed to get company: {company_result.get('Result')}")
        else:
            print("⚠️ No valid CompanyIds found in contacts")

if __name__ == "__main__":
    print("🚀 Starting LACRM API Investigation...")
    
    # Run the investigation
    results = investigate_companies_vs_contacts()
    
    # Test specific company access
    test_specific_company_access()
    
    print(f"\n{'='*70}")
    print("📋 INVESTIGATION SUMMARY")
    print(f"{'='*70}")
    
    working_functions = []
    failed_functions = []
    
    for func_key, result in results.items():
        if result.get('Success'):
            working_functions.append(func_key)
        else:
            failed_functions.append(func_key)
    
    print(f"✅ Working functions: {len(working_functions)}")
    for func in working_functions:
        print(f"   - {func}")
    
    print(f"\n❌ Failed functions: {len(failed_functions)}")
    for func in failed_functions:
        print(f"   - {func}")
    
    print(f"\n{'='*70}")
    print("🎯 RECOMMENDATIONS")
    print(f"{'='*70}")
    print("1. Check if your LACRM account has companies set up properly")
    print("2. Verify the API permissions for company access")
    print("3. Test with GetCompany using valid CompanyIds")
    print("4. Consider that contacts might be linked to companies via CompanyId")
    print("="*70)
