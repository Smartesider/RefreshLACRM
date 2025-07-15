#!/usr/bin/env python3
"""
LACRM Company Detection via Contacts API
Since direct company API access is limited, this script identifies companies through contacts
"""

import requests
import json
import configparser
from typing import Dict, Any, List, Set
from collections import defaultdict

def load_config() -> configparser.ConfigParser:
    """Load configuration from config.ini"""
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config

def get_all_contacts_and_companies():
    """Get all contacts and identify company records and relationships"""
    config = load_config()
    
    print("🏢 ANALYZING LACRM CONTACTS AND COMPANIES")
    print("="*60)
    
    # Get all contacts
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
            return
        
        contacts = result.get('Result', [])
        print(f"📊 Total contacts found: {len(contacts)}")
        
        # Separate contacts and companies
        companies = []
        individuals = []
        company_names = set()
        company_ids = set()
        
        for contact in contacts:
            is_company = contact.get('IsCompany') == "1"
            company_name = contact.get('CompanyName')
            company_id = contact.get('CompanyId')
            
            if is_company:
                companies.append(contact)
                print(f"🏢 Found company record: {contact.get('FirstName', 'N/A')} (ContactId: {contact.get('ContactId')})")
            else:
                individuals.append(contact)
                
            if company_name:
                company_names.add(company_name)
            if company_id:
                company_ids.add(company_id)
        
        print(f"\n📈 BREAKDOWN:")
        print(f"   🏢 Company records (IsCompany=1): {len(companies)}")
        print(f"   👤 Individual records (IsCompany=0): {len(individuals)}")
        print(f"   🏷️ Unique company names: {len(company_names)}")
        print(f"   🆔 Unique company IDs: {len(company_ids)}")
        
        print(f"\n🏢 COMPANY NAMES FOUND:")
        for name in sorted(company_names):
            print(f"   - {name}")
        
        print(f"\n🆔 COMPANY IDS FOUND:")
        for cid in sorted(company_ids):
            print(f"   - {cid}")
        
        # Analyze relationships
        print(f"\n🔗 ANALYZING RELATIONSHIPS:")
        company_relationships = defaultdict(list)
        
        for contact in individuals:
            company_name = contact.get('CompanyName')
            company_id = contact.get('CompanyId')
            
            if company_name:
                contact_info = f"{contact.get('FirstName', '')} {contact.get('LastName', '')}".strip()
                if not contact_info:
                    contact_info = contact.get('Email', [{}])[0].get('Text', 'No name') if contact.get('Email') else 'No name'
                company_relationships[company_name].append(contact_info)
        
        for company_name, contacts_list in company_relationships.items():
            print(f"   🏢 {company_name}: {len(contacts_list)} contacts")
            for contact_name in contacts_list[:3]:  # Show first 3
                print(f"      - {contact_name}")
            if len(contacts_list) > 3:
                print(f"      ... and {len(contacts_list) - 3} more")
        
        # Look for companies with organization numbers
        print(f"\n🔍 SEARCHING FOR ORGANIZATION NUMBERS:")
        orgnr_field_id = config['LACRM'].get('OrgNrFieldId', '')
        companies_with_orgnr = []
        
        for contact in contacts:
            # Check custom fields for orgnr
            custom_fields = contact.get('CustomFields', [])
            orgnr = None
            
            if isinstance(custom_fields, list):
                for field in custom_fields:
                    if isinstance(field, dict) and field.get('FieldId') == orgnr_field_id:
                        orgnr = field.get('Value')
                        break
            
            if orgnr:
                company_name = contact.get('CompanyName') or f"{contact.get('FirstName', '')} {contact.get('LastName', '')}".strip()
                companies_with_orgnr.append({
                    'ContactId': contact.get('ContactId'),
                    'CompanyName': company_name,
                    'OrganizationNumber': orgnr,
                    'IsCompany': contact.get('IsCompany') == "1"
                })
        
        print(f"   📋 Companies with organization numbers: {len(companies_with_orgnr)}")
        for company in companies_with_orgnr:
            print(f"   🏢 {company['CompanyName']} (OrgnNr: {company['OrganizationNumber']}, IsCompany: {company['IsCompany']})")
        
        return {
            'total_contacts': len(contacts),
            'companies': companies,
            'individuals': individuals,
            'company_names': company_names,
            'company_ids': company_ids,
            'companies_with_orgnr': companies_with_orgnr,
            'company_relationships': dict(company_relationships)
        }
        
    except Exception as e:
        print(f"🚨 Error: {e}")
        return None

if __name__ == "__main__":
    result = get_all_contacts_and_companies()
    
    if result:
        print(f"\n{'='*60}")
        print("🎯 KEY FINDINGS")
        print(f"{'='*60}")
        
        print(f"1. Your LACRM contains {result['total_contacts']} total contact records")
        print(f"2. Found {len(result['companies'])} records marked as companies (IsCompany=1)")
        print(f"3. Found {len(result['company_names'])} unique company names referenced")
        print(f"4. Found {len(result['companies_with_orgnr'])} companies with organization numbers")
        
        print(f"\n📋 SCRIPT UPDATE NEEDED:")
        print("The script should process BOTH:")
        print("   - Company records (IsCompany=1)")
        print("   - Individual contacts that belong to companies (CompanyName field)")
        
        print(f"\n🔧 RECOMMENDED CHANGES:")
        print("1. Filter for contacts with CompanyName OR IsCompany=1")
        print("2. Use CompanyName for company identification when available")
        print("3. Check both IsCompany field and CompanyName field")
        print("4. Process organization numbers from custom fields correctly")
