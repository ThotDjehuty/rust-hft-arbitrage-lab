#!/usr/bin/env python3
"""
Script to add Finnhub API key setup cell to all notebooks.
"""

import json
import sys
from pathlib import Path

# Markdown cell to insert at the beginning
FINNHUB_SETUP_CELL = {
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "## Setup: Finnhub API Key\n",
        "\n",
        "This notebook uses real market data from [Finnhub](https://finnhub.io/) (free tier: 60 API calls/min).\n",
        "\n",
        "**To use real data:**\n",
        "1. Get a free API key at https://finnhub.io/register\n",
        "2. Set environment variable: `export FINNHUB_API_KEY=your_key_here`\n",
        "3. Or enter the key when prompted\n",
        "\n",
        "**Without a key:** The notebook falls back to synthetic data generation."
    ]
}

# Import statement to add to first code cell
FINNHUB_IMPORT = """
# Import Finnhub helper for real market data
try:
    from python.finnhub_helper import fetch_historical_simulation, get_finnhub_api_key, create_orderbook_from_quote
    FINNHUB_AVAILABLE = True
except Exception as e:
    print(f"Finnhub helper not available: {e}")
    FINNHUB_AVAILABLE = False
"""

def update_notebook(notebook_path):
    """Add Finnhub setup cell if not already present."""
    print(f"Processing {notebook_path.name}...")
    
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
    except Exception as e:
        print(f"  ✗ Failed to read: {e}")
        return False
    
    # Check if setup cell already exists
    cells = nb.get('cells', [])
    if not cells:
        print("  ✗ No cells found")
        return False
    
    # Check first few cells for Finnhub content
    has_setup = False
    for cell in cells[:3]:
        cell_source = ''.join(cell.get('source', []))
        if 'Finnhub API Key' in cell_source or 'FINNHUB_API_KEY' in cell_source:
            has_setup = True
            break
    
    if has_setup:
        print("  ✓ Already has Finnhub setup")
        return True
    
    # Insert setup cell at beginning
    nb['cells'].insert(0, FINNHUB_SETUP_CELL)
    
    # Add import to first code cell
    for i, cell in enumerate(nb['cells'][1:], 1):  # Skip the setup cell we just added
        if cell.get('cell_type') == 'code':
            source = cell.get('source', [])
            if isinstance(source, list):
                source = ''.join(source)
            
            # Add import if not already present
            if 'finnhub_helper' not in source:
                # Insert after existing imports
                lines = source.split('\n')
                import_end = 0
                for j, line in enumerate(lines):
                    if line.strip().startswith('import ') or line.strip().startswith('from '):
                        import_end = j + 1
                
                lines.insert(import_end, FINNHUB_IMPORT)
                cell['source'] = '\n'.join(lines)
            
            break
    
    # Write back
    try:
        with open(notebook_path, 'w', encoding='utf-8') as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)
        print("  ✓ Updated successfully")
        return True
    except Exception as e:
        print(f"  ✗ Failed to write: {e}")
        return False

def main():
    """Update all notebooks in examples/notebooks/"""
    script_dir = Path(__file__).parent
    notebooks_dir = script_dir.parent / 'examples' / 'notebooks'
    
    if not notebooks_dir.exists():
        print(f"Error: {notebooks_dir} not found")
        sys.exit(1)
    
    notebooks = sorted(notebooks_dir.glob('*.ipynb'))
    
    if not notebooks:
        print(f"No notebooks found in {notebooks_dir}")
        sys.exit(1)
    
    print(f"Found {len(notebooks)} notebooks\n")
    
    success = 0
    for nb_path in notebooks:
        if update_notebook(nb_path):
            success += 1
    
    print(f"\n{'='*60}")
    print(f"Updated {success}/{len(notebooks)} notebooks")
    
    if success < len(notebooks):
        sys.exit(1)

if __name__ == '__main__':
    main()
