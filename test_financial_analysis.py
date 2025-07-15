#!/usr/bin/env python3
"""
Test the complete flow with the updated Proff.no functions
"""

import sys
import os
import json

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the test data we just created
with open('proff_scrape_test_931122541.json', 'r', encoding='utf-8') as f:
    test_proff_data = json.load(f)

# Constants for testing (from lacrm_sync.py)
PROFITABILITY_CONCERN = "Profitability Concern"
REVENUE_CONCERN = "Revenue Concern"

def get_financial_health(proff_data):
    """Test version of the financial health function"""
    health = {}
    key_figures = proff_data.get('key_figures')

    if not isinstance(key_figures, dict):
        return {"status": "No key figures available."}

    # Updated for new Proff.no structure
    try:
        # Try different possible revenue field names from the new structure
        revenue_val = (key_figures.get("Sum driftsinntekter") or 
                      key_figures.get("Driftsinntekter") or 
                      key_figures.get("Omsetning") or "0")
        
        # Sanitize and validate the input (handle thousands separators)
        revenue_str = str(revenue_val).replace(" ", "").replace(",", "").replace("NOK", "").strip()
        
        # Handle negative values and validate
        if revenue_str.startswith('-'):
            revenue_int = 0  # Negative revenue treated as 0
        elif revenue_str.isdigit():
            revenue_int = int(revenue_str)
        else:
            raise ValueError(f"Invalid revenue format: {revenue_str}")
            
        # Convert from thousands (Proff shows values in thousands)
        revenue_int = revenue_int * 1000
        
        print(f"Revenue analysis: {revenue_val} -> {revenue_int} NOK")
        
        if revenue_int < 1000000:  # Less than 1M NOK
            health[REVENUE_CONCERN] = f"Low revenue ({revenue_int/1000000:.1f}M NOK)."

        # Check profitability using "Resultat før skatt"
        result_val = (key_figures.get("Resultat før skatt") or 
                     key_figures.get("Årsresultat") or "0")
        
        result_str = str(result_val).replace(" ", "").replace(",", "").replace("NOK", "").strip()
        
        # Handle negative values properly
        is_negative = result_str.startswith('-')
        result_clean = result_str.lstrip('-')
        
        if not result_clean.isdigit():
            raise ValueError(f"Invalid result format: {result_str}")
        
        result_int = int(result_clean) * 1000  # Convert from thousands
        if is_negative:
            result_int = -result_int
        
        print(f"Profit analysis: {result_val} -> {result_int} NOK")
            
        if result_int < 0:
            health[PROFITABILITY_CONCERN] = (
                f"Company is not currently profitable ({result_int/1000000:.1f}M NOK loss)."
            )

    except (ValueError, TypeError) as e:
        print(f"Error parsing financial figures: {e}")
        health["Data Quality"] = "Could not parse financial figures."

    if not health:
        health["status"] = "Appears stable based on available data."

    return health

def test_financial_analysis():
    """Test the financial analysis with real data"""
    print("🧪 TESTING FINANCIAL HEALTH ANALYSIS")
    print("=" * 50)
    
    print("📊 Test data (Proff.no scraping result):")
    print(json.dumps(test_proff_data, indent=2, ensure_ascii=False))
    
    print("\n🔍 Financial Health Analysis:")
    print("-" * 30)
    
    health_result = get_financial_health(test_proff_data)
    
    print("Results:")
    for key, value in health_result.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Test completed!")
    
    # Save result
    with open('financial_health_test.json', 'w', encoding='utf-8') as f:
        json.dump(health_result, f, indent=2, ensure_ascii=False)
    print("Saved result to financial_health_test.json")

if __name__ == "__main__":
    test_financial_analysis()
