"""
Xactimate PDF Parser
Extracts structured data from Xactimate estimate PDFs
Handles both single-line and multi-line formats
"""

import logging
import re
from typing import Dict, List, Optional, Any
import fitz
import pdfplumber
from decimal import Decimal

logger = logging.getLogger(__name__)


class XactimateParser:
    """Parser for Xactimate estimate PDFs"""
    
    def __init__(self):
        self.current_room = None
        self.line_items = []
        self.categories = {}
        self.header_data = {}
        
    def parse_pdf(self, filepath: str, options: Dict = None) -> Dict:
        """Main entry point for parsing Xactimate PDF"""
        options = options or {}
        
        try:
            logger.info("Attempting PyMuPDF parsing...")
            result = self._parse_with_pymupdf(filepath)
            
            if result['success']:
                return result
            
            logger.info("PyMuPDF failed, trying pdfplumber...")
            result = self._parse_with_pdfplumber(filepath)
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing PDF: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _parse_with_pymupdf(self, filepath: str) -> Dict:
        """Parse PDF using PyMuPDF (fitz)"""
        try:
            doc = fitz.open(filepath)
            full_text = ""
            
            for page in doc:
                full_text += page.get_text()
            
            doc.close()
            
            self._extract_header_data(full_text)
            self._extract_line_items_gps_format(full_text)
            self._build_categories_from_items()
            
            return self._build_response()
            
        except Exception as e:
            logger.error(f"PyMuPDF parsing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _parse_with_pdfplumber(self, filepath: str) -> Dict:
        """Parse PDF using pdfplumber (backup method)"""
        try:
            with pdfplumber.open(filepath) as pdf:
                full_text = ""
                
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
            
            self._extract_header_data(full_text)
            self._extract_line_items_gps_format(full_text)
            self._build_categories_from_items()
            
            return self._build_response()
            
        except Exception as e:
            logger.error(f"pdfplumber parsing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _extract_header_data(self, text: str) -> None:
        """Extract header information from estimate"""
        
        name_pattern = r"Insured:\s*([A-Z][A-Z\s&,.\-']+?)(?:\s+Home:|\s+E-mail:|\n)"
        name_match = re.search(name_pattern, text, re.IGNORECASE)
        if name_match:
            self.header_data['insured_name'] = name_match.group(1).strip()
        
        address_match = re.search(r"Property:\s*(.+?)(?:\n|\s{2,})", text, re.IGNORECASE)
        if address_match:
            address_start = address_match.start()
            address_section = text[address_start:address_start + 200]
            lines = address_section.split('\n')
            address_parts = []
            for i, line in enumerate(lines[:4]):
                if i == 0:
                    address_parts.append(line.replace('Property:', '').strip())
                elif line.strip() and not any(x in line.lower() for x in ['claim rep', 'business:', 'position:', 'company:']):
                    address_parts.append(line.strip())
                else:
                    break
            self.header_data['property_address'] = ' '.join(address_parts)
        
        claim_match = re.search(r"Claim Number:\s*(\d+)", text, re.IGNORECASE)
        if claim_match:
            self.header_data['claim_number'] = claim_match.group(1)
        
        policy_match = re.search(r"Policy Number:\s*([\d-]+)", text, re.IGNORECASE)
        if policy_match:
            self.header_data['policy_number'] = policy_match.group(1)
        
        dol_match = re.search(r"Date of Loss:\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.IGNORECASE)
        if dol_match:
            self.header_data['date_of_loss'] = dol_match.group(1)
        
        logger.info(f"Extracted header data: {self.header_data}")
    
    def _extract_line_items_gps_format(self, text: str) -> None:
        """Extract line items - handles both single-line and multi-line formats"""
        
        lines = text.split('\n')
        i = 0
        current_room = None
        
        while i < len(lines):
            line = lines[i].strip()
            
            if self._is_room_header_gps(line):
                current_room = line
                logger.debug(f"Found room: {current_room}")
            
            item_pattern = r'^(\d+[a-z]?)\.\s+(.+)'
            item_match = re.match(item_pattern, line)
            
            if item_match:
                line_num = item_match.group(1)
                description = item_match.group(2).strip()
                
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    
                    single_pattern = r'^\d+\s+[\d,.]+\s+[A-Z]{2,3}\s+[\d,.]+\s+[\d,.]+\s+\([\d,.]+\)\s+[\d,.]+$'
                    
                    if re.search(single_pattern, next_line):
                        try:
                            self._parse_single_line_format(line_num, description, next_line, current_room)
                        except Exception as e:
                            logger.error(f"Error parsing single-line format: {str(e)}")
                    else:
                        try:
                            result = self._parse_multi_line_format(i, line_num, description, lines, current_room)
                            if result:
                                self.line_items.append(result)
                        except Exception as e:
                            logger.error(f"Error parsing multi-line format: {str(e)}")
            
            i += 1
        
        logger.info(f"Extracted {len(self.line_items)} line items")
    
    def _parse_single_line_format(self, line_num: str, description: str, data_line: str, room: str) -> None:
        """Parse single-line format"""
        parts = data_line.split()
        
        if len(parts) >= 6:
            unit_idx = None
            unit_pattern = r'^[A-Z]{2,3}$'
            for i, part in enumerate(parts):
                if re.match(unit_pattern, part):
                    unit_idx = i
                    break
            
            if unit_idx is not None and unit_idx > 0:
                quantity = self._parse_number(parts[unit_idx - 1])
                unit = parts[unit_idx]
                
                remaining = parts[unit_idx + 1:]
                
                if len(remaining) >= 4:
                    unit_price = self._parse_currency(remaining[0])
                    rcv = self._parse_currency(remaining[1])
                    depreciation = self._parse_currency(remaining[2])
                    acv = self._parse_currency(remaining[3])
                    
                    item = {
                        'line_number': len(self.line_items) + 1,
                        'room': room,
                        'description': description,
                        'quantity': quantity,
                        'unit': unit,
                        'unit_price': unit_price,
                        'tax': 0.0,
                        'o_and_p': 0.0,
                        'rcv': rcv,
                        'depreciation': depreciation,
                        'acv': acv,
                        'category': self._determine_category(description)
                    }
                    
                    self.line_items.append(item)
                    logger.debug(f"Parsed single-line item: {description[:50]}")
    
    def _parse_multi_line_format(self, line_idx: int, line_num: str, description: str, lines: list, room: str) -> dict:
        """Parse multi-line format"""
        j = line_idx + 1
        data_lines = []
        
        stop_pattern = r'^\d+[a-z]?\.\s+\S'
        while j < len(lines) and j < line_idx + 15:
            next_line = lines[j].strip()
            if next_line and not re.match(stop_pattern, next_line):
                data_lines.append(next_line)
                j += 1
            else:
                break
        
        if len(data_lines) >= 7:
            qty_pattern = r'([\d,.]+)\s+([A-Z]{2,3})'
            qty_unit_match = re.match(qty_pattern, data_lines[0])
            
            if qty_unit_match:
                quantity = self._parse_number(qty_unit_match.group(1))
                unit = qty_unit_match.group(2)
                
                unit_price = self._parse_currency(data_lines[1]) if len(data_lines) > 1 else 0.0
                tax = self._parse_currency(data_lines[2]) if len(data_lines) > 2 else 0.0
                o_and_p = self._parse_currency(data_lines[3]) if len(data_lines) > 3 else 0.0
                rcv = self._parse_currency(data_lines[4]) if len(data_lines) > 4 else 0.0
                depreciation = self._parse_currency(data_lines[5]) if len(data_lines) > 5 else 0.0
                acv = self._parse_currency(data_lines[6]) if len(data_lines) > 6 else 0.0
                
                full_description = description
                desc_continuation_idx = 7
                while desc_continuation_idx < len(data_lines) and desc_continuation_idx < 10:
                    next_desc = data_lines[desc_continuation_idx]
                    num_pattern = r'^[\d,.<>]+$'
                    if next_desc and not re.match(num_pattern, next_desc) and len(next_desc) > 3:
                        skip_words = ['TOTAL', 'DESCRIPTION', 'QUANTITY', 'CONTINUED']
                        if not any(kw in next_desc.upper() for kw in skip_words):
                            full_description += " " + next_desc
                    desc_continuation_idx += 1
                
                return {
                    'line_number': len(self.line_items) + 1,
                    'room': room,
                    'description': full_description,
                    'quantity': quantity,
                    'unit': unit,
                    'unit_price': unit_price,
                    'tax': tax,
                    'o_and_p': o_and_p,
                    'rcv': rcv,
                    'depreciation': depreciation,
                    'acv': acv,
                    'category': self._determine_category(full_description)
                }
        
        return None
    
    def _is_room_header_gps(self, line: str) -> bool:
        """Determine if line is a room header"""
        if not line or len(line) > 50:
            return False
        
        room_keywords = [
            'EXTERIOR', 'ENTRY', 'FOYER', 'KITCHEN', 'BATHROOM', 'BEDROOM',
            'LIVING', 'DINING', 'GARAGE', 'LAUNDRY', 'MAIN LEVEL', 'BASEMENT',
            'HALLWAY', 'OFFICE', 'DEN', 'CLOSET', 'UTILITY', 'PANTRY',
            'MASTER', 'GUEST', 'FAMILY ROOM'
        ]
        
        line_upper = line.upper()
        
        if any(keyword in line_upper for keyword in room_keywords):
            exclude = ['DESCRIPTION', 'QUANTITY', 'UNIT', 'PRICE', 'HEIGHT:']
            if not any(x in line_upper for x in exclude):
                return True
        
        return False
    
    def _parse_number(self, value: str) -> float:
        """Parse number string to float"""
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = value.replace(',', '').strip()
        return float(cleaned) if cleaned else 0.0
    
    def _parse_currency(self, value: str) -> float:
        """Parse currency string to float"""
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = value.replace('$', '').replace(',', '').replace('<', '').replace('>', '').replace('(', '').replace(')', '').strip()
        return float(cleaned) if cleaned else 0.0
    
    def _determine_category(self, description: str) -> str:
        """Determine NFIP category"""
        desc_upper = description.upper()
        
        category_keywords = {
            'INSULATION': ['INSULATION', 'INSULATE', 'BATT'],
            'CABINETRY': ['CABINET', 'COUNTER', 'VANITY'],
            'FINISH CARPENTRY / TRIMWORK': ['FINISH CARPENTRY', 'TRIMWORK', 'CROWN', 'WAINSCOT'],
            'FINISH HARDWARE': ['FINISH HARDWARE', 'KNOB', 'HANDLE', 'HINGE'],
            'DOORS': ['DOOR', 'THRESHOLD'],
            'WINDOWS - SLIDING PATIO DOORS': ['PATIO DOOR', 'SLIDING DOOR'],
            'WINDOWS - ALUMINUM': ['WINDOW', 'GLASS', 'GLAZING'],
            'WINDOW TREATMENT': ['WINDOW TREATMENT', 'BLINDS', 'SHADE'],
            'MIRRORS & SHOWER DOORS': ['MIRROR', 'SHOWER DOOR'],
            'DRYWALL': ['DRYWALL', 'SHEETROCK', 'GYPSUM'],
            'STUCCO & EXTERIOR PLASTER': ['STUCCO', 'EXTERIOR PLASTER'],
            'SOFFIT, FASCIA, & GUTTER': ['SOFFIT', 'FASCIA', 'GUTTER', 'DOWNSPOUT'],
            'WALLPAPER': ['WALLPAPER'],
            'FLOOR COVERING - CERAMIC TILE': ['CERAMIC TILE', 'PORCELAIN TILE'],
            'FLOOR COVERING - CARPET': ['CARPET'],
            'FLOOR COVERING - STONE': ['STONE FLOOR', 'MARBLE FLOOR', 'GRANITE FLOOR', 'TRAVERTINE'],
            'FLOOR COVERING - WOOD': ['HARDWOOD', 'WOOD FLOOR', 'OAK FLOOR', 'ENGINEERED WOOD'],
            'FLOOR COVERING - VINYL': ['VINYL', 'LVP', 'LVT', 'LUXURY VINYL'],
            'FLOOR COVERING - LAMINATE': ['LAMINATE'],
            'FLOOR COVERING': ['FLOOR', 'FLOORING'],
            'TILE': ['TILE', 'REGROUT'],
            'PAINTING & WOOD WALL FINISHES': ['PAINT', 'PRIMER', 'STAIN', 'WOOD FINISH'],
            'PANELING & WOOD WALL FINISHES': ['PANEL', 'WOOD PANEL'],
            'TEXTURE': ['TEXTURE'],
            'PLUMBING': ['PLUMB', 'WATER', 'DRAIN', 'PIPE', 'FAUCET', 'TOILET', 'SINK'],
            'ELECTRICAL': ['ELECTRIC', 'OUTLET', 'SWITCH', 'WIRE', 'FIXTURE', 'BREAKER', 'PANEL'],
            'HVAC': ['HVAC'],
            'HEAT, VENT & AIR CONDITIONING': ['AIR CONDITION', 'FURNACE', 'DUCT', 'AC UNIT', 'HEAT PUMP', 'CONDENSER'],
            'APPLIANCES': ['APPLIANCE', 'DISHWASHER', 'RANGE', 'REFRIGERATOR', 'WASHER', 'DRYER'],
            'LIGHT FIXTURES': ['LIGHT FIXTURE', 'LIGHTING'],
            'TOILET & BATH ACCESSORIES': ['TOILET ACCESSORY', 'BATH ACCESSORY', 'TOWEL BAR', 'PAPER HOLDER'],
            'INTERIOR LATH & PLASTER': ['LATH', 'PLASTER'],
            'TRIM': ['BASEBOARD', 'TRIM', 'MOLDING', 'CASING'],
            'CLEANING': ['CLEAN', 'MUCK', 'SANITIZE', 'DISINFECT', 'ANTI-MICROBIAL'],
            'WATER EXTRACTION & REMEDIATION': ['WATER EXTRACTION', 'REMEDIATION', 'STRUCTURAL DRYING'],
            'GENERAL DEMOLITION': ['DEMO', 'DEMOLITION', 'TEAR OUT', 'DISPOSAL', 'DUMPSTER', 'HAUL'],
            'TEMPORARY REPAIRS': ['TEMPORARY', 'TARP', 'BOARD UP'],
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in desc_upper for keyword in keywords):
                return category
        
        return 'GENERAL'
    
    def _build_categories_from_items(self) -> None:
        """Build category summary"""
        for item in self.line_items:
            category = item.get('category', 'GENERAL')
            
            if category not in self.categories:
                self.categories[category] = {
                    'name': category,
                    'rcv': 0.0,
                    'depreciation': 0.0,
                    'acv': 0.0
                }
            
            self.categories[category]['rcv'] += item['rcv']
            self.categories[category]['depreciation'] += item['depreciation']
            self.categories[category]['acv'] += item['acv']
    
    def _build_response(self) -> Dict:
        """Build final response"""
        
        if not self.line_items:
            return {
                'success': False,
                'error': 'No line items found in estimate'
            }
        
        total_rcv = sum(item['rcv'] for item in self.line_items)
        total_depreciation = sum(item['depreciation'] for item in self.line_items)
        total_acv = sum(item['acv'] for item in self.line_items)
        
        return {
            'success': True,
            'header': self.header_data,
            'line_items': self.line_items,
            'categories': list(self.categories.values()),
            'totals': {
                'rcv': round(total_rcv, 2),
                'depreciation': round(total_depreciation, 2),
                'acv': round(total_acv, 2),
                'deductible': self.header_data.get('deductible', 0),
                'net_claim': round(total_acv - self.header_data.get('deductible', 0), 2)
            },
            'metadata': {
                'total_line_items': len(self.line_items),
                'total_categories': len(self.categories),
                'rooms': list(set(item['room'] for item in self.line_items if item.get('room')))
            }
        }