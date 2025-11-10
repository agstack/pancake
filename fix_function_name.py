#!/usr/bin/env python3
"""
Fix cosine_similarity → semantic_similarity in ask_pancake_enhanced
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
        
        # Fix the function name
        if 'cosine_similarity(' in source_str:
            source_str = source_str.replace('cosine_similarity(', 'semantic_similarity(')
            cell['source'] = [source_str]
            print("Fixed: cosine_similarity → semantic_similarity")
        else:
            print("cosine_similarity not found")
        
        break

# Write back
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Notebook updated")



