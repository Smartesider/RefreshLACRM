#!/usr/bin/env python3
"""
Test script to diagnose Proff.no scraping issues
"""

import requests
from bs4 import BeautifulSoup
import json

def test_proff_scraping(orgnr: str):
    """Test the Proff.no scraping for a specific organization number."""
    print(f"Testing Proff.no scraping for orgnr: {orgnr}")
    print("=" * 60)
    
    try:
        url = f"https://www.proff.no/selskap/{orgnr}"
        print(f"URL: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print("Making request...")
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"❌ Non-200 status code: {response.status_code}")
            print(f"Response text (first 500 chars): {response.text[:500]}")
            return None
            
        print("✅ Request successful, parsing HTML...")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Print page title to verify we got the right page
        title = soup.find('title')
        print(f"Page title: {title.get_text() if title else 'No title found'}")
        
        # Look for various possible class names and structures
        print("\n🔍 Searching for financial data sections...")
        
        # Try different selectors for key figures
        selectors_to_try = [
            'div.key-figures',
            'table.table-key-figures',
            'div.financial-data',
            'div.nokkeltal',
            'table.nokkeltal',
            'div.company-info',
            'div.company-data',
            'section.financial',
            'div.financial-info',
            'table.financial'
        ]
        
        found_sections = []
        for selector in selectors_to_try:
            elements = soup.select(selector)
            if elements:
                found_sections.append({
                    'selector': selector,
                    'count': len(elements),
                    'sample_text': elements[0].get_text()[:200] if elements else ''
                })
        
        print(f"Found {len(found_sections)} potential financial sections:")
        for section in found_sections:
            print(f"  - {section['selector']}: {section['count']} elements")
            print(f"    Sample: {section['sample_text']}")
        
        # Look for tables in general
        print("\n📊 Looking for all tables...")
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables total")
        
        for i, table in enumerate(tables[:5]):  # Show first 5 tables
            print(f"\nTable {i+1}:")
            print(f"  Classes: {table.get('class', [])}")
            print(f"  Rows: {len(table.find_all('tr'))}")
            if table.find_all('tr'):
                first_row = table.find_all('tr')[0]
                print(f"  First row text: {first_row.get_text()[:100]}")
        
        # Look for divs with financial-sounding content
        print("\n💰 Looking for divs with financial keywords...")
        financial_keywords = ['omsetning', 'resultat', 'driftsinntekter', 'egenkapital', 'gjeld']
        for keyword in financial_keywords:
            elements = soup.find_all(text=lambda text: text and keyword.lower() in text.lower())
            if elements:
                print(f"  Found '{keyword}' in {len(elements)} elements")
                for elem in elements[:2]:  # Show first 2 matches
                    parent = elem.parent if elem.parent else None
                    if parent:
                        print(f"    Parent tag: {parent.name}, classes: {parent.get('class', [])}")
                        print(f"    Text: {elem.strip()[:100]}")
        
        # Try to find any structured data
        print("\n🏗️  Looking for structured data...")
        
        # Look for JSON-LD structured data
        json_scripts = soup.find_all('script', type='application/ld+json')
        if json_scripts:
            print(f"Found {len(json_scripts)} JSON-LD scripts")
            for i, script in enumerate(json_scripts):
                try:
                    data = json.loads(script.string)
                    print(f"  Script {i+1}: {type(data)} with keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
                except:
                    print(f"  Script {i+1}: Could not parse JSON")
        
        # Save a sample of the HTML for manual inspection
        with open(f'proff_sample_{orgnr}.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"\n📁 Saved full HTML to proff_sample_{orgnr}.html for manual inspection")
        
        return {
            'status_code': response.status_code,
            'title': title.get_text() if title else None,
            'tables_found': len(tables),
            'potential_sections': found_sections
        }
        
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Test with a few different organization numbers
    test_orgnrs = [
        "931122541",  # User's company
        "923609016",  # DNB (large company)
        "974760673"   # Equinor (another large company)
    ]
    
    print("🧪 PROFF.NO SCRAPING DIAGNOSTIC TOOL")
    print("=" * 60)
    
    for orgnr in test_orgnrs:
        print(f"\n\n{'='*20} Testing {orgnr} {'='*20}")
        result = test_proff_scraping(orgnr)
        if result:
            print(f"✅ Test completed for {orgnr}")
        else:
            print(f"❌ Test failed for {orgnr}")
        print("-" * 60)
