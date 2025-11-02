"""
Debug Parser - Test the parser directly and show what it finds
"""

import sys
import os
from pathlib import Path

# Add parent directory to path so we can import from api
sys.path.insert(0, str(Path(__file__).parent.parent / 'api'))

from parsers.xactimate_parser import XactimateParser
import re

def debug_parse(pdf_path):
    """Run parser with detailed debugging output"""
    
    print("\n" + "="*80)
    print(f"DEBUGGING PARSER FOR: {pdf_path.name}")
    print("="*80)
    
    parser = XactimateParser()
    
    # Load and extract text
    print("\n1. EXTRACTING TEXT FROM PDF...")
    import fitz
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    
    print(f"   ✓ Extracted {len(full_text)} characters")
    
    # Test header extraction
    print("\n2. TESTING HEADER EXTRACTION...")
    parser._extract_header_data(full_text)
    print(f"   Found header data: {parser.header_data}")
    
    # Test line item extraction - with detailed output
    print("\n3. TESTING LINE ITEM EXTRACTION...")
    print("   Looking for patterns like: '1. Description'")
    print("   Followed by: 'Quantity Unit Price Tax O&P RCV <Deprec> ACV'")
    
    lines = full_text.split('\n')
    
    # Find lines that start with number and period
    numbered_lines = []
    for i, line in enumerate(lines):
        item_match = re.match(r'^(\d+)\.\s+(.+)', line.strip())
        if item_match:
            numbered_lines.append((i, line.strip(), item_match.group(1), item_match.group(2)))
    
    print(f"\n   Found {len(numbered_lines)} numbered lines")
    
    if numbered_lines:
        print("\n   First 5 numbered lines found:")
        for i, (line_idx, full_line, num, desc) in enumerate(numbered_lines[:5], 1):
            print(f"\n   Line {line_idx}:")
            print(f"      Number: {num}")
            print(f"      Description: {desc[:60]}...")
            
            # Check next line for financial data
            if line_idx + 1 < len(lines):
                next_line = lines[line_idx + 1].strip()
                print(f"      Next line: {next_line[:80]}...")
                
                # Try to match financial pattern
                financial_pattern = r'([\d,.]+)\s+([A-Z]{2,3})\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+<([\d,.]+)>\s+([\d,.]+)'
                financial_match = re.search(financial_pattern, next_line)
                
                if financial_match:
                    print(f"      ✓ MATCHED financial pattern!")
                    print(f"         Quantity: {financial_match.group(1)}")
                    print(f"         Unit: {financial_match.group(2)}")
                    print(f"         RCV: {financial_match.group(6)}")
                else:
                    print(f"      ✗ NO MATCH for financial pattern")
                    print(f"      Let's analyze this line:")
                    print(f"         Raw: '{next_line}'")
                    print(f"         Length: {len(next_line)}")
                    
                    # Try to find what looks like numbers
                    numbers = re.findall(r'[\d,.]+', next_line)
                    print(f"         Numbers found: {numbers}")
                    
                    # Try to find what looks like units
                    units = re.findall(r'\b[A-Z]{2,3}\b', next_line)
                    print(f"         Potential units: {units}")
    else:
        print("\n   ✗ No numbered lines found!")
        print("\n   Let's check what the text looks like:")
        print("\n   First 50 lines of extracted text:")
        for i, line in enumerate(lines[:50], 1):
            if line.strip():
                print(f"   {i}: {line[:80]}")
    
    # Now run the actual parser with detailed debugging
    print("\n4. RUNNING FULL PARSER...")
    print("   Testing the actual parsing logic on first item...")
    
    # Manually test the first numbered line
    if numbered_lines:
        line_idx, full_line, num, desc = numbered_lines[0]
        print(f"\n   Testing line {line_idx}: '{desc[:50]}...'")
        
        # Get next 15 lines
        data_lines = []
        for j in range(line_idx + 1, min(line_idx + 16, len(lines))):
            next_line = lines[j].strip()
            if next_line and not re.match(r'^\d+\.', next_line):
                data_lines.append(next_line)
            else:
                break
        
        print(f"   Collected {len(data_lines)} data lines:")
        for i, dl in enumerate(data_lines[:10], 0):
            print(f"      [{i}] {dl}")
        
        # Test quantity/unit match
        if len(data_lines) >= 7:
            qty_unit_pattern = r'([\d,.]+)\s+([A-Z]{2,3})'
            match = re.match(qty_unit_pattern, data_lines[0])
            if match:
                print(f"\n   ✓ MATCHED quantity/unit pattern!")
                print(f"      Quantity: {match.group(1)}")
                print(f"      Unit: {match.group(2)}")
                
                # Show what the parsed values would be
                print(f"\n   Would parse as:")
                print(f"      Quantity: {match.group(1)}")
                print(f"      Unit: {match.group(2)}")
                print(f"      Unit Price: {data_lines[1] if len(data_lines) > 1 else 'N/A'}")
                print(f"      Tax: {data_lines[2] if len(data_lines) > 2 else 'N/A'}")
                print(f"      O&P: {data_lines[3] if len(data_lines) > 3 else 'N/A'}")
                print(f"      RCV: {data_lines[4] if len(data_lines) > 4 else 'N/A'}")
                print(f"      Deprec: {data_lines[5] if len(data_lines) > 5 else 'N/A'}")
                print(f"      ACV: {data_lines[6] if len(data_lines) > 6 else 'N/A'}")
            else:
                print(f"\n   ✗ DID NOT match quantity/unit pattern on: '{data_lines[0]}'")
        else:
            print(f"\n   ✗ Not enough data lines (need 7, got {len(data_lines)})")
    
    # Run the actual parser
    print("\n   Now running actual parser method...")
    parser._extract_line_items_gps_format(full_text)
    
    print(f"\n   Parser found {len(parser.line_items)} line items")
    
    if parser.line_items:
        print("\n   First 3 parsed items:")
        for item in parser.line_items[:3]:
            print(f"\n   Item #{item['line_number']}:")
            print(f"      Room: {item.get('room', 'N/A')}")
            print(f"      Description: {item['description'][:60]}...")
            print(f"      Quantity: {item['quantity']} {item['unit']}")
            print(f"      RCV: ${item['rcv']:,.2f}")
            print(f"      Category: {item['category']}")
    else:
        print("\n   ✗ Parser found NO line items")
        print("\n   This means the regex patterns aren't matching.")
        print("   Review the output above to see why.")
    
    print("\n" + "="*80)
    print("DEBUG COMPLETE")
    print("="*80 + "\n")

def main():
    """Main debug function"""
    # Get PDF files
    sample_folder = Path("sample_pdfs")
    
    if not sample_folder.exists():
        print("✗ Folder 'sample_pdfs' not found!")
        return
    
    pdf_files = list(sample_folder.glob("*.pdf"))
    
    if not pdf_files:
        print("✗ No PDF files found")
        return
    
    # List all PDFs first
    print("\nAvailable PDFs:")
    for i, pdf in enumerate(pdf_files):
        print(f"  {i}: {pdf.name}")
    
    # Debug estimate 4 - change index as needed
    pdf_path = pdf_files[2]  # Adjust this number based on the list above
    debug_parse(pdf_path)

if __name__ == "__main__":
    main()