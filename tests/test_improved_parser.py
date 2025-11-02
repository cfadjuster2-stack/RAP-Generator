"""
Test the improved parser with category fixes
"""

import sys
import os
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.parsers.xactimate_parser import XactimateParser

def test_parse(pdf_path):
    """Test parser and display results"""

    print("\n" + "="*80)
    print(f"Testing Parser on: {pdf_path.name}")
    print("="*80)

    parser = XactimateParser()
    result = parser.parse_pdf(str(pdf_path))

    if not result['success']:
        print(f"\nERROR: {result.get('error', 'Unknown error')}")
        return

    print(f"\n*** SUCCESS! ***")
    print(f"\nHeader Information:")
    print(f"  Insured: {result['header'].get('insured_name', 'N/A')}")
    print(f"  Property: {result['header'].get('property_address', 'N/A')}")
    print(f"  Claim #: {result['header'].get('claim_number', 'N/A')}")
    print(f"  Date of Loss: {result['header'].get('date_of_loss', 'N/A')}")

    print(f"\nParsing Statistics:")
    print(f"  Total Line Items: {result['metadata']['total_line_items']}")
    print(f"  Duplicates Removed: {result['metadata'].get('duplicates_removed', 0)}")
    print(f"  Total Categories: {result['metadata']['total_categories']}")

    print(f"\nTotals:")
    print(f"  RCV: ${result['totals']['rcv']:,.2f}")
    print(f"  Depreciation: ${result['totals']['depreciation']:,.2f}")
    print(f"  ACV: ${result['totals']['acv']:,.2f}")

    print(f"\n{'='*80}")
    print(f"CATEGORIES (in priority order)")
    print(f"{'='*80}")

    for i, cat in enumerate(result['categories'], 1):
        print(f"\n{i}. {cat['name']}")
        print(f"   Items: {cat.get('item_count', 0)}")
        print(f"   RCV: ${cat['rcv']:,.2f}")
        print(f"   ACV: ${cat['acv']:,.2f}")

        # Show first few unique items
        unique_items = cat.get('unique_items', [])
        if unique_items:
            print(f"   Sample items:")
            for item_desc in unique_items[:3]:
                print(f"     - {item_desc[:70]}")
            if len(unique_items) > 3:
                print(f"     ... and {len(unique_items) - 3} more")

    # Show some example line items with their categories
    print(f"\n{'='*80}")
    print(f"SAMPLE LINE ITEMS (first 10)")
    print(f"{'='*80}")

    for item in result['line_items'][:10]:
        print(f"\n  {item['line_number']}. {item['description'][:60]}")
        print(f"     Room: {item.get('room', 'N/A')}")
        print(f"     Qty: {item['quantity']} {item['unit']}")
        print(f"     Category: {item['category']}")
        print(f"     RCV: ${item['rcv']:,.2f}")

    # Save full results to JSON for review
    output_file = Path(__file__).parent / f"test_output_{pdf_path.stem}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'='*80}")
    print(f"Full results saved to: {output_file.name}")
    print(f"{'='*80}\n")

def main():
    """Main test function"""
    sample_folder = Path(__file__).parent / "sample_pdfs"

    if not sample_folder.exists():
        print("ERROR: sample_pdfs folder not found!")
        return

    pdf_files = list(sample_folder.glob("*.pdf"))

    if not pdf_files:
        print("ERROR: No PDF files found!")
        return

    print("\nAvailable PDFs:")
    for i, pdf in enumerate(pdf_files):
        print(f"  {i}: {pdf.name}")

    # Test the first PDF
    print("\n\nTesting first PDF...\n")
    test_parse(pdf_files[0])

if __name__ == "__main__":
    main()
