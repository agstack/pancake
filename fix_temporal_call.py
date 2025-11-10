#!/usr/bin/env python3
"""
Fix temporal_similarity call to include current timestamp
"""

import json

# Read the notebook
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'r') as f:
    notebook = json.load(f)

# Find the ask_pancake_enhanced function
for i, cell in enumerate(notebook['cells']):
    if cell['cell_type'] == 'code' and 'def ask_pancake_enhanced' in ''.join(cell['source']):
        print(f"Found ask_pancake_enhanced at cell index {i}")
        
        # Get current source as string
        source_str = ''.join(cell['source'])
        
        # Fix the temporal_similarity call - needs two timestamps
        old_call = "temp_sim = temporal_similarity(bite['Header']['timestamp'])"
        new_call = "temp_sim = temporal_similarity(bite['Header']['timestamp'], datetime.utcnow().isoformat() + 'Z')"
        
        if old_call in source_str:
            source_str = source_str.replace(old_call, new_call)
            cell['source'] = [source_str]
            print("Fixed: Added current timestamp to temporal_similarity call")
        else:
            print("Warning: Could not find exact pattern")
        
        break

# Write back
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Notebook updated")



