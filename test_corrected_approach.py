#!/usr/bin/env python3
"""
Test the corrected LACRM company processing approach
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

def get_lacrm_companies(config: configparser.ConfigParser) -> List[Dict[str, Any]]:
    """Fetches company records from LACRM using SearchContacts with IsCompany=1 filter."""
    print("🏢 Fetching company records from LACRM...")
    
    # First get all contacts
    data = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": "SearchContacts",
        "Parameters": json.dumps({"SearchText": ""})
    }
    
    try:
        response = requests.post("https://api.lessannoyingcrm.com", data=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if not result.get('Success'):
            print(f"❌ API Error: {result.get('Result')}")
            return []
        
        all_contacts = result.get('Result', [])
        print(f"📊 Total contacts fetched: {len(all_contacts)}")
        
        # Filter for company records and contacts with company names
        companies = []
        for contact in all_contacts:
            is_company_record = contact.get('IsCompany') == "1"
            has_company_name = bool(contact.get('CompanyName'))
            
            if is_company_record or has_company_name:
                companies.append(contact)
        
        print(f"✅ Found {len(companies)} company-related records out of {len(all_contacts)} total contacts.")
        return companies
        
    except Exception as e:
        print(f"🚨 Error: {e}")
        return []

def test_company_processing():
    """Test the updated company processing logic"""
    config = load_config()
    
    print("🚀 TESTING CORRECTED LACRM COMPANY PROCESSING")
    print("="*60)
    
    companies = get_lacrm_companies(config)
    
    if not companies:
        print("❌ No company records found.")
        return
    
    print(f"\n📋 PROCESSING {len(companies)} COMPANY RECORDS:")
    print("-" * 60)
    
    orgnr_field_id = config['LACRM']['OrgNrFieldId']
    
    for i, contact in enumerate(companies, 1):
        contact_id = contact.get('ContactId')
        is_company_record = contact.get('IsCompany') == "1"
        
        # Determine company name using the new logic
        if is_company_record:
            company_name = (contact.get('CompanyName') or 
                          contact.get('FirstName') or 
                          'Unknown Company')
        else:
            company_name = contact.get('CompanyName')
        
        print(f"\n{i}. Company: {company_name}")
        print(f"   ContactId: {contact_id}")
        print(f"   IsCompany: {is_company_record}")
        print(f"   CompanyName field: {contact.get('CompanyName')}")
        print(f"   FirstName field: {contact.get('FirstName')}")
        
        # Check for organization number
        orgnr = None
        custom_fields = contact.get('CustomFields', [])
        if isinstance(custom_fields, list):
            for field in custom_fields:
                if isinstance(field, dict) and field.get('FieldId') == orgnr_field_id:
                    orgnr = field.get('Value')
                    break
        
        print(f"   Organization Number: {orgnr or 'Not found'}")
        
        # Determine processing status
        if company_name and company_name != 'Unknown Company':
            if orgnr:
                print(f"   ✅ Ready for processing (has name and orgnr)")
            else:
                print(f"   ⚠️  Ready for orgnr lookup (has name, missing orgnr)")
        else:
            print(f"   ❌ Skipped (no valid company name)")
    
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    
    # Count by type
    company_records = sum(1 for c in companies if c.get('IsCompany') == "1")
    contact_records = len(companies) - company_records
    
    with_orgnr = 0
    without_orgnr = 0
    processable = 0
    
    for contact in companies:
        is_company_record = contact.get('IsCompany') == "1"
        
        if is_company_record:
            company_name = (contact.get('CompanyName') or 
                          contact.get('FirstName') or 
                          'Unknown Company')
        else:
            company_name = contact.get('CompanyName')
        
        # Check for orgnr
        orgnr = None
        custom_fields = contact.get('CustomFields', [])
        if isinstance(custom_fields, list):
            for field in custom_fields:
                if isinstance(field, dict) and field.get('FieldId') == orgnr_field_id:
                    orgnr = field.get('Value')
                    break
        
        if company_name and company_name != 'Unknown Company':
            processable += 1
            if orgnr:
                with_orgnr += 1
            else:
                without_orgnr += 1
    
    print(f"🏢 Company records (IsCompany=1): {company_records}")
    print(f"👤 Contact records with CompanyName: {contact_records}")
    print(f"✅ Processable companies: {processable}")
    print(f"📋 With organization numbers: {with_orgnr}")
    print(f"🔍 Need orgnr lookup: {without_orgnr}")
    
    if processable > 0:
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. Script can now process {processable} company records")
        print(f"2. {without_orgnr} companies need organization number lookup")
        print(f"3. Updated sync_all_lacrm_contacts() function will handle both types")
    else:
        print(f"\n⚠️  No processable companies found. Check data structure.")

if __name__ == "__main__":
    test_company_processing()
