#!/usr/bin/env python3
"""
Test script to diagnose Wappalyzer import issues
Run this on your server to determine the correct import method
"""

import sys
print('Python version:', sys.version)
print('=' * 50)

# Test 1: Basic wappalyzer module
try:
    import wappalyzer
    print('✓ wappalyzer module imported successfully')
    print('  Module path:', wappalyzer.__file__)
    print('  Module contents:', dir(wappalyzer))
except Exception as e:
    print('✗ Error importing wappalyzer:', e)

print('=' * 50)

# Test 2: Try different import patterns
import_attempts = [
    "from wappalyzer import Wappalyzer",
    "from wappalyzer import WebPage", 
    "from wappalyzer.wappalyzer import Wappalyzer",
    "from wappalyzer.core import Wappalyzer",
    "from python_Wappalyzer import Wappalyzer",
    "from python_Wappalyzer import WebPage",
]

successful_imports = []

for import_statement in import_attempts:
    try:
        exec(import_statement)
        print(f'✓ SUCCESS: {import_statement}')
        successful_imports.append(import_statement)
    except Exception as e:
        print(f'✗ FAILED: {import_statement} - {e}')

print('=' * 50)
print('Successful imports:')
for imp in successful_imports:
    print(f'  {imp}')

# Test 3: Check if we can actually use Wappalyzer
if successful_imports:
    try:
        # Try to create Wappalyzer instance
        if 'from wappalyzer import Wappalyzer' in successful_imports:
            from wappalyzer import Wappalyzer
        elif 'from wappalyzer.wappalyzer import Wappalyzer' in successful_imports:
            from wappalyzer.wappalyzer import Wappalyzer
        elif 'from python_Wappalyzer import Wappalyzer' in successful_imports:
            from python_Wappalyzer import Wappalyzer
        
        wapp = Wappalyzer.latest()
        print('✓ Wappalyzer.latest() works')
        
    except Exception as e:
        print(f'✗ Error creating Wappalyzer instance: {e}')

print('=' * 50)
print('Recommended fix based on results above will be provided.')
