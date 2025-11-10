#!/usr/bin/env python3
"""
Fix TAP demo code to use correct BITE structure path
"""

import json

# Read the notebook
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'r') as f:
    notebook = json.load(f)

# Find and fix the TAP demo cell
for i, cell in enumerate(notebook['cells']):
    source_str = ''.join(cell.get('source', []))
    
    if "ndvi_stats = bite_satellite['Body']['sirup_data']['data']['ndvi_stats']" in source_str:
        print(f"Found TAP demo at cell {i}")
        
        # Fix the path - remove the extra 'data' level
        # The structure is: Body.sirup_data.ndvi_stats (not Body.sirup_data.data.ndvi_stats)
        source_str = source_str.replace(
            "ndvi_stats = bite_satellite['Body']['sirup_data']['data']['ndvi_stats']",
            "ndvi_stats = bite_satellite['Body']['sirup_data']['ndvi_stats']"
        )
        
        # Also fix soil data access if present
        if "'data']['num_properties']" in source_str:
            source_str = source_str.replace(
                "profile_data = bite_soil['Body']['sirup_data']['data']",
                "profile_data = bite_soil['Body']['sirup_data']"
            )
        
        cell['source'] = [source_str]
        print("Fixed BITE structure paths")
        break

# Write back
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ TAP demo fixed")



