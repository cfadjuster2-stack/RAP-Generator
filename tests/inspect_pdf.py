"""
PDF Inspector - Shows raw text and structure from PDF
Use this to understand the format of your Xactimate estimates
"""

import fitz  # PyMuPDF
import pdfplumber
from pathlib import Path
import sys

def inspect_with_pymupdf(pdf_path):
    """Extract and display text using PyMuPDF"""
    print("\n" + "="*80)
    print("PYMUPDF EXTRACTION")
    print("="*80)
    
    try:
        doc = fitz.open(pdf_path)
        print(f"\nTotal pages: {len(doc)}")
        
        for page_num, page in enumerate(doc, 1):
            print(f"\n--- PAGE {page_num} ---")
            text = page.get_text()
            
            # Show first 2000 characters of each page
            if len(text) > 2000:
                print(text[:2000])
                print(f"\n... (showing first 2000 of {len(text)} characters)")
            else:
                print(text)
            
            if page_num >= 2:  # Only show first 2 pages
                if len(doc) > 2:
                    print(f"\n... ({len(doc) - 2} more pages not shown)")
                break
        
        doc.close()
        
    except Exception as e:
        print(f"Error with PyMuPDF: {str(e)}")

def inspect_with_pdfplumber(pdf_path):
    """Extract and display text/tables using pdfplumber"""
    print("\n" + "="*80)
    print("PDFPLUMBER EXTRACTION")
    print("="*80)
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"\nTotal pages: {len(pdf.pages)}")
            
            for page_num, page in enumerate(pdf.pages, 1):
                print(f"\n--- PAGE {page_num} ---")
                
                # Extract text
                text = page.extract_text()
                if text:
                    if len(text) > 2000:
                        print(text[:2000])
                        print(f"\n... (showing first 2000 of {len(text)} characters)")
                    else:
                        print(text)
                
                # Try to extract tables
                tables = page.extract_tables()
                if tables:
                    print(f"\n📊 Found {len(tables)} table(s) on this page")
                    for i, table in enumerate(tables, 1):
                        print(f"\nTable {i}:")
                        # Show first 5 rows
                        for row in table[:5]:
                            print(row)
                        if len(table) > 5:
                            print(f"... ({len(table) - 5} more rows)")
                
                if page_num >= 2:  # Only show first 2 pages
                    if len(pdf.pages) > 2:
                        print(f"\n... ({len(pdf.pages) - 2} more pages not shown)")
                    break
                    
    except Exception as e:
        print(f"Error with pdfplumber: {str(e)}")

def save_full_text(pdf_path):
    """Save complete text extraction to a file"""
    output_file = pdf_path.stem + "_extracted.txt"
    
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        
        for page in doc:
            full_text += f"\n{'='*80}\n"
            full_text += f"PAGE {page.number + 1}\n"
            full_text += f"{'='*80}\n"
            full_text += page.get_text()
        
        doc.close()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_text)
        
        print(f"\n✓ Full text saved to: {output_file}")
        print(f"  You can open this file to see the complete extracted text")
        
    except Exception as e:
        print(f"Error saving text: {str(e)}")

def main():
    """Main inspection function"""
    print("\n" + "="*80)
    print("PDF INSPECTOR - Analyze Xactimate Estimate Format")
    print("="*80)
    
    # Get PDF files from sample_pdfs folder
    sample_folder = Path("sample_pdfs")
    
    if not sample_folder.exists():
        print(f"\n✗ Folder 'sample_pdfs' not found!")
        print("  Make sure you're running this from the 'tests' folder")
        return
    
    pdf_files = list(sample_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"\n✗ No PDF files found in 'sample_pdfs'")
        return
    
    # If multiple PDFs, let user choose
    if len(pdf_files) > 1:
        print(f"\nFound {len(pdf_files)} PDF files:")
        for i, pdf in enumerate(pdf_files, 1):
            print(f"  {i}. {pdf.name}")
        
        try:
            choice = input("\nEnter number to inspect (or press Enter for first file): ").strip()
            if choice:
                pdf_path = pdf_files[int(choice) - 1]
            else:
                pdf_path = pdf_files[0]
        except (ValueError, IndexError):
            print("Invalid choice, using first file")
            pdf_path = pdf_files[0]
    else:
        pdf_path = pdf_files[0]
    
    print(f"\n📄 Inspecting: {pdf_path.name}")
    print(f"   File size: {pdf_path.stat().st_size:,} bytes")
    
    # Run inspections
    inspect_with_pymupdf(pdf_path)
    inspect_with_pdfplumber(pdf_path)
    save_full_text(pdf_path)
    
    print("\n" + "="*80)
    print("INSPECTION COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. Review the extracted text above")
    print("2. Open the .txt file to see the complete extraction")
    print("3. Look for patterns in how line items are formatted")
    print("4. Share the output with Claude to improve the parser")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInspection cancelled by user")
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")