#!/usr/bin/env python3
"""
Find and completely rewrite ask_pancake_enhanced function
"""

import json

# Read the notebook
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'r') as f:
    notebook = json.load(f)

# Find the ask_pancake_enhanced function
for i, cell in enumerate(notebook['cells']):
    source_str = ''.join(cell.get('source', []))
    if 'def ask_pancake_enhanced(' in source_str:
        print(f"Found ask_pancake_enhanced at cell index {i}")
        print(f"Current length: {len(source_str)} chars")
        print("\nFirst 500 chars:")
        print(source_str[:500])
        print("\n...")
        break

print("\nDone")



