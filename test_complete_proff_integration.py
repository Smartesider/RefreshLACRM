#!/usr/bin/env python3
"""
Test both companies to validate the complete Proff.no integration
"""

import sys
import os
import json

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import both test datasets
try:
    with open('proff_scrape_test_931122541.json', 'r', encoding='utf-8') as f:
        company1_data = json.load(f)
    
    with open('proff_scrape_test_923609016.json', 'r', encoding='utf-8') as f:
        company2_data = json.load(f)
except FileNotFoundError as e:
    print(f"Error: {e}")
    print("Please run the scraping tests first to generate test data.")
    sys.exit(1)

# Now test the actual functions from lacrm_sync.py
try:
    from lacrm_sync import scrape_proff, get_financial_health
    print("✅ Successfully imported functions from lacrm_sync.py")
except ImportError as e:
    print(f"❌ Could not import from lacrm_sync.py: {e}")
    sys.exit(1)

def test_complete_flow():
    """Test the complete Proff.no integration flow"""
    print("🧪 TESTING COMPLETE PROFF.NO INTEGRATION")
    print("=" * 50)
    
    test_companies = [
        ("931122541", "Husselskapet A/S"),
        ("923609016", "Skafteløkka Betong AS")
    ]
    
    results = {}
    
    for orgnr, company_name in test_companies:
        print(f"\n🏢 Testing company: {company_name} ({orgnr})")
        print("-" * 40)
        
        try:
            # Test the actual scraping function
            print("1. Running scrape_proff()...")
            proff_data = scrape_proff(orgnr)
            
            if proff_data:
                print("   ✅ Scraping successful!")
                print(f"   📊 Revenue: {proff_data.get('key_figures', {}).get('Sum driftsinntekter', 'N/A')}")
                print(f"   💰 Profit: {proff_data.get('key_figures', {}).get('Resultat før skatt', 'N/A')}")
                
                # Test financial health analysis
                print("2. Running get_financial_health()...")
                health_analysis = get_financial_health(proff_data)
                
                print("   🩺 Health Analysis:")
                for key, value in health_analysis.items():
                    print(f"     - {key}: {value}")
                
                results[orgnr] = {
                    "company_name": company_name,
                    "scraping_success": True,
                    "proff_data": proff_data,
                    "health_analysis": health_analysis
                }
                
            else:
                print("   ❌ Scraping failed!")
                results[orgnr] = {
                    "company_name": company_name,
                    "scraping_success": False,
                    "error": "No data returned from scrape_proff"
                }
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results[orgnr] = {
                "company_name": company_name,
                "scraping_success": False,
                "error": str(e)
            }
    
    # Save comprehensive results
    with open('complete_proff_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📝 Saved complete test results to complete_proff_test_results.json")
    
    # Summary
    print(f"\n📋 SUMMARY")
    print("=" * 20)
    success_count = sum(1 for r in results.values() if r.get('scraping_success'))
    total_count = len(results)
    print(f"✅ Successful tests: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("🎉 All Proff.no integration tests passed!")
        print("🚀 System ready for production use!")
    else:
        print("⚠️  Some tests failed - review the results above.")

if __name__ == "__main__":
    test_complete_flow()
