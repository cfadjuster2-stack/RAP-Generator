"""
Test Script for RAP Estimate Parser
Automatically tests all PDFs in sample_pdfs folder
"""

import requests
import os
import json
from pathlib import Path
from datetime import datetime

# Configuration
API_URL = "http://localhost:5001/api/parse-estimate"
SAMPLE_PDFS_FOLDER = "sample_pdfs"
RESULTS_FOLDER = "results"

# Colors for terminal output (Windows compatible)
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(message):
    """Print success message in green"""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def print_error(message):
    """Print error message in red"""
    print(f"{Colors.RED}✗ {message}{Colors.END}")

def print_info(message):
    """Print info message in blue"""
    print(f"{Colors.BLUE}ℹ {message}{Colors.END}")

def print_warning(message):
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")

def check_server():
    """Check if API server is running"""
    try:
        response = requests.get("http://localhost:5001/health", timeout=2)
        if response.status_code == 200:
            print_success("API server is running")
            return True
        else:
            print_error("API server responded but not healthy")
            return False
    except requests.exceptions.RequestException:
        print_error("API server is not running!")
        print_info("Start the server with: python api/app.py")
        return False

def get_pdf_files():
    """Get all PDF files from sample_pdfs folder"""
    pdf_folder = Path(SAMPLE_PDFS_FOLDER)
    
    if not pdf_folder.exists():
        print_error(f"Folder '{SAMPLE_PDFS_FOLDER}' not found!")
        return []
    
    pdf_files = list(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        print_warning(f"No PDF files found in '{SAMPLE_PDFS_FOLDER}'")
        return []
    
    print_success(f"Found {len(pdf_files)} PDF file(s)")
    return pdf_files

def parse_pdf(pdf_path):
    """Send PDF to API for parsing"""
    print(f"\n{'='*60}")
    print_info(f"Testing: {pdf_path.name}")
    print(f"{'='*60}")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (pdf_path.name, f, 'application/pdf')}
            
            print("Uploading and parsing...")
            response = requests.post(API_URL, files=files, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                print_success("PDF parsed successfully!")
                display_results(result)
                save_results(pdf_path.stem, result)
                return True
            else:
                print_error(f"Parsing failed: {result.get('error')}")
                return False
        else:
            print_error(f"Server error: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def display_results(result):
    """Display parsed results in a readable format"""
    
    # Header Information
    if 'header' in result and result['header']:
        print("\n📋 HEADER INFORMATION:")
        header = result['header']
        for key, value in header.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
    
    # Line Items Summary
    if 'line_items' in result:
        line_items = result['line_items']
        print(f"\n📝 LINE ITEMS: {len(line_items)} items found")
        
        # Show first 3 line items as examples
        print("\n  Sample line items:")
        for i, item in enumerate(line_items[:3], 1):
            print(f"\n  Item #{i}:")
            print(f"    Room: {item.get('room', 'N/A')}")
            print(f"    Description: {item.get('description', 'N/A')}")
            print(f"    Quantity: {item.get('quantity', 0)} {item.get('unit', '')}")
            print(f"    RCV: ${item.get('rcv', 0):,.2f}")
            print(f"    Category: {item.get('category', 'N/A')}")
        
        if len(line_items) > 3:
            print(f"\n  ... and {len(line_items) - 3} more items")
    
    # Categories Summary
    if 'categories' in result and result['categories']:
        print(f"\n📊 CATEGORIES: {len(result['categories'])} categories")
        print(f"\n  {'Category':<20} {'RCV':>12} {'Deprec':>12} {'ACV':>12}")
        print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12}")
        
        for cat in result['categories']:
            name = cat['name'][:20]
            rcv = cat.get('rcv', 0)
            dep = cat.get('depreciation', 0)
            acv = cat.get('acv', 0)
            print(f"  {name:<20} ${rcv:>11,.2f} ${dep:>11,.2f} ${acv:>11,.2f}")
    
    # Totals
    if 'totals' in result:
        totals = result['totals']
        print(f"\n💰 TOTALS:")
        print(f"  RCV:        ${totals.get('rcv', 0):>12,.2f}")
        print(f"  Deprec:     ${totals.get('depreciation', 0):>12,.2f}")
        print(f"  ACV:        ${totals.get('acv', 0):>12,.2f}")
        print(f"  Deductible: ${totals.get('deductible', 0):>12,.2f}")
        print(f"  Net Claim:  ${totals.get('net_claim', 0):>12,.2f}")
    
    # Metadata
    if 'metadata' in result:
        meta = result['metadata']
        print(f"\n📈 METADATA:")
        print(f"  Total Line Items: {meta.get('total_line_items', 0)}")
        print(f"  Total Categories: {meta.get('total_categories', 0)}")
        if 'rooms' in meta and meta['rooms']:
            print(f"  Rooms Found: {', '.join(meta['rooms'][:5])}")
            if len(meta['rooms']) > 5:
                print(f"               ... and {len(meta['rooms']) - 5} more")

def save_results(filename, result):
    """Save results to JSON file"""
    results_folder = Path(RESULTS_FOLDER)
    results_folder.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_folder / f"{filename}_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print_success(f"Results saved to: {output_file}")

def main():
    """Main test function"""
    print("\n" + "="*60)
    print("  RAP ESTIMATE PARSER - TEST SCRIPT")
    print("="*60)
    
    # Check if server is running
    if not check_server():
        return
    
    # Get PDF files
    pdf_files = get_pdf_files()
    if not pdf_files:
        return
    
    # Test each PDF
    successful = 0
    failed = 0
    
    for pdf_path in pdf_files:
        if parse_pdf(pdf_path):
            successful += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    print(f"  Total PDFs tested: {len(pdf_files)}")
    print_success(f"Successful: {successful}")
    if failed > 0:
        print_error(f"Failed: {failed}")
    print("\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")