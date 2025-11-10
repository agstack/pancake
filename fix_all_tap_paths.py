#!/usr/bin/env python3
"""
Fix all remaining ['data'] accesses in TAP demo
"""

import json

# Read the notebook
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'r') as f:
    notebook = json.load(f)

# Find and fix the TAP demo cell
for i, cell in enumerate(notebook['cells']):
    source_str = ''.join(cell.get('source', []))
    
    if "MULTI-VENDOR DATA FETCHING DEMO" in source_str:
        print(f"Found TAP demo at cell {i}")
        
        # Fix soil data access
        source_str = source_str.replace(
            "profile_data = bite_soil['Body']['sirup_data']['data']",
            "profile_data = bite_soil['Body']['sirup_data']"
        )
        
        # Fix weather data access  
        source_str = source_str.replace(
            "forecast_data = bite_weather['Body']['sirup_data']['data']",
            "forecast_data = bite_weather['Body']['sirup_data']"
        )
        
        cell['source'] = [source_str]
        print("Fixed all BITE structure paths in TAP demo")
        break

# Write back
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ All TAP demo paths fixed")



