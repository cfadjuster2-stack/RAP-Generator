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
            self._remove_duplicate_line_items()
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
            self._remove_duplicate_line_items()
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
        """
        Determine NFIP category with priority-based matching.
        Priority is important to avoid mis-categorization (e.g., "exterior door" shouldn't match "insulation")
        """
        desc_upper = description.upper()

        # Skip deduction notes and similar non-item entries
        skip_patterns = ['DEDUCTION', 'DEDUCT FOR', 'LESS ', 'SUBTRACT', 'CREDIT FOR']
        if any(pattern in desc_upper for pattern in skip_patterns):
            return 'GENERAL'

        # PRIORITY 1: High-priority categories (specific matches first)
        # These should be checked first to prevent mis-categorization

        # Water extraction and remediation (check before cleaning)
        if any(kw in desc_upper for kw in ['WATER EXTRACTION', 'STRUCTURAL DRYING', 'MOISTURE', 'DEHUMID', 'AIR MOVER', 'WATER MITIGATION']):
            return 'WATER EXTRACTION & REMEDIATION'

        # Cleaning (comprehensive - anything with "clean" goes here)
        if any(kw in desc_upper for kw in ['CLEAN', 'MUCK OUT', 'SANITIZE', 'DISINFECT', 'ANTI-MICROBIAL', 'ANTIMICROBIAL', 'DEODOR']):
            return 'CLEANING'

        # General demolition (check before other categories)
        if any(kw in desc_upper for kw in ['DEMO', 'DEMOLITION', 'TEAR OUT', 'REMOVE ', 'DISPOSAL', 'DUMPSTER', 'HAUL', 'DEBRIS']):
            return 'GENERAL DEMOLITION'

        # Temporary repairs
        if any(kw in desc_upper for kw in ['TEMPORARY', 'TARP', 'BOARD UP', 'EMERGENCY']):
            return 'TEMPORARY REPAIRS'

        # PRIORITY 2: Specific trade categories

        # Doors (check before insulation to catch "insulated door")
        # Door hardware goes with doors
        if any(kw in desc_upper for kw in ['DOOR', 'THRESHOLD', 'DOOR HARDWARE', 'DOOR KNOB', 'DOOR HANDLE', 'LOCKSET', 'DEADBOLT']):
            return 'DOORS'

        # Windows
        if any(kw in desc_upper for kw in ['PATIO DOOR', 'SLIDING DOOR', 'SLIDING GLASS']):
            return 'WINDOWS - SLIDING PATIO DOORS'
        if any(kw in desc_upper for kw in ['WINDOW', 'GLASS', 'GLAZING']):
            return 'WINDOWS - ALUMINUM'
        if any(kw in desc_upper for kw in ['WINDOW TREATMENT', 'BLINDS', 'SHADE', 'CURTAIN']):
            return 'WINDOW TREATMENT'

        # Mirrors and shower doors
        if any(kw in desc_upper for kw in ['MIRROR', 'SHOWER DOOR', 'TUB DOOR', 'GLASS DOOR']):
            return 'MIRRORS & SHOWER DOORS'

        # Appliances (add garbage disposal)
        if any(kw in desc_upper for kw in ['APPLIANCE', 'DISHWASHER', 'RANGE', 'REFRIGERATOR', 'WASHER', 'DRYER', 'GARBAGE DISPOSAL', 'DISPOSAL', 'MICROWAVE', 'STOVE', 'OVEN']):
            return 'APPLIANCES'

        # Plumbing (specific items)
        if any(kw in desc_upper for kw in ['PLUMB', 'FAUCET', 'VALVE', 'PIPE', 'DRAIN', 'TRAP', 'SUPPLY LINE', 'WATER LINE', 'SHOWER HEAD', 'TUB', 'BATHTUB']):
            return 'PLUMBING'

        # Fixtures that aren't in other categories
        if 'SINK' in desc_upper and 'CABINET' not in desc_upper:
            return 'PLUMBING'
        if 'TOILET' in desc_upper and 'ACCESSORY' not in desc_upper:
            return 'PLUMBING'

        # Electrical
        if any(kw in desc_upper for kw in ['ELECTRIC', 'OUTLET', 'SWITCH', 'RECEPTACLE', 'WIRE', 'WIRING', 'BREAKER', 'PANEL', 'GFI', 'GFCI']):
            return 'ELECTRICAL'

        # Light fixtures (separate from electrical)
        if any(kw in desc_upper for kw in ['LIGHT FIXTURE', 'LIGHTING', 'CHANDELIER', 'CEILING FAN']):
            return 'LIGHT FIXTURES'

        # HVAC (but not structural drying)
        if any(kw in desc_upper for kw in ['HVAC', 'AIR CONDITION', 'FURNACE', 'DUCT', 'AC UNIT', 'HEAT PUMP', 'CONDENSER', 'THERMOSTAT']):
            if 'STRUCTURAL DRYING' not in desc_upper and 'WATER' not in desc_upper:
                return 'HEAT, VENT & AIR CONDITIONING'

        # PRIORITY 3: Finish materials

        # Cabinetry (skip if it's a deduction note)
        if any(kw in desc_upper for kw in ['CABINET', 'COUNTER TOP', 'COUNTERTOP', 'VANITY']):
            return 'CABINETRY'

        # Drywall and texture (texture walls go to drywall)
        if any(kw in desc_upper for kw in ['DRYWALL', 'SHEETROCK', 'GYPSUM', 'TEXTURE WALL', 'TEXTURE CEILING']):
            return 'DRYWALL'

        # Interior plaster (separate from drywall)
        if any(kw in desc_upper for kw in ['PLASTER', 'LATH']):
            return 'INTERIOR LATH & PLASTER'

        # Stucco
        if any(kw in desc_upper for kw in ['STUCCO', 'EXTERIOR PLASTER']):
            return 'STUCCO & EXTERIOR PLASTER'

        # Finish carpentry and trim (includes baseboard)
        if any(kw in desc_upper for kw in ['BASEBOARD', 'BASE BOARD', 'TRIM', 'MOLDING', 'CASING', 'CROWN', 'WAINSCOT', 'CHAIR RAIL']):
            return 'FINISH CARPENTRY / TRIMWORK'

        # Finish hardware
        if any(kw in desc_upper for kw in ['FINISH HARDWARE', 'KNOB', 'HANDLE', 'HINGE', 'PULL']):
            return 'FINISH HARDWARE'

        # Painting (but not floor perimeter which is walls)
        if any(kw in desc_upper for kw in ['PAINT', 'PRIMER', 'STAIN', 'WOOD FINISH', 'SEAL']):
            return 'PAINTING & WOOD WALL FINISHES'

        # Paneling
        if any(kw in desc_upper for kw in ['PANEL', 'WOOD PANEL', 'WAINSCOTING']):
            return 'PANELING & WOOD WALL FINISHES'

        # Wallpaper
        if 'WALLPAPER' in desc_upper:
            return 'WALLPAPER'

        # PRIORITY 4: Flooring (but not floor perimeter which is a wall calculation)

        # Floor perimeter is a WALL calculation, not flooring
        if 'FLOOR PERIMETER' in desc_upper or 'PERIMETER' in desc_upper:
            return 'PAINTING & WOOD WALL FINISHES'

        # Specific floor types (most specific first)
        if any(kw in desc_upper for kw in ['CERAMIC TILE', 'PORCELAIN TILE']):
            return 'FLOOR COVERING - CERAMIC TILE'
        if any(kw in desc_upper for kw in ['CARPET', 'PAD']):
            return 'FLOOR COVERING - CARPET'
        if any(kw in desc_upper for kw in ['STONE FLOOR', 'MARBLE FLOOR', 'GRANITE FLOOR', 'TRAVERTINE']):
            return 'FLOOR COVERING - STONE'
        if any(kw in desc_upper for kw in ['HARDWOOD', 'WOOD FLOOR', 'OAK FLOOR', 'ENGINEERED WOOD']):
            return 'FLOOR COVERING - WOOD'
        if any(kw in desc_upper for kw in ['VINYL', 'LVP', 'LVT', 'LUXURY VINYL']):
            return 'FLOOR COVERING - VINYL'
        if any(kw in desc_upper for kw in ['LAMINATE']):
            return 'FLOOR COVERING - LAMINATE'

        # Generic tile (wall or floor)
        if any(kw in desc_upper for kw in ['TILE', 'REGROUT']):
            return 'TILE'

        # Generic flooring (last resort for floor items)
        if any(kw in desc_upper for kw in ['FLOOR', 'FLOORING']):
            return 'FLOOR COVERING'

        # PRIORITY 5: Exterior and other

        # Soffit, fascia, gutter
        if any(kw in desc_upper for kw in ['SOFFIT', 'FASCIA', 'GUTTER', 'DOWNSPOUT']):
            return 'SOFFIT, FASCIA, & GUTTER'

        # Insulation (check last to avoid catching "insulated door")
        if any(kw in desc_upper for kw in ['INSULATION', 'INSULATE', 'BATT', 'BLOWN-IN']):
            return 'INSULATION'

        # Toilet and bath accessories
        if any(kw in desc_upper for kw in ['TOILET ACCESSORY', 'BATH ACCESSORY', 'TOWEL BAR', 'PAPER HOLDER', 'GRAB BAR']):
            return 'TOILET & BATH ACCESSORIES'

        # Default category
        return 'GENERAL'
    
    def _remove_duplicate_line_items(self) -> None:
        """
        Remove duplicate line items based on description and quantity.
        Keeps the first occurrence of each unique item.
        """
        seen = set()
        unique_items = []

        for item in self.line_items:
            # Create a unique key based on description, quantity, and unit
            key = (
                item.get('description', '').strip().upper(),
                item.get('quantity', 0),
                item.get('unit', '').upper()
            )

            if key not in seen:
                seen.add(key)
                unique_items.append(item)
            else:
                logger.debug(f"Removing duplicate: {item.get('description', '')[:50]}")

        removed_count = len(self.line_items) - len(unique_items)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate line items")

        self.line_items = unique_items

    def _build_categories_from_items(self) -> None:
        """Build category summary with unique items"""
        for item in self.line_items:
            category = item.get('category', 'GENERAL')

            if category not in self.categories:
                self.categories[category] = {
                    'name': category,
                    'rcv': 0.0,
                    'depreciation': 0.0,
                    'acv': 0.0,
                    'item_count': 0,
                    'unique_items': []
                }

            self.categories[category]['rcv'] += item['rcv']
            self.categories[category]['depreciation'] += item['depreciation']
            self.categories[category]['acv'] += item['acv']
            self.categories[category]['item_count'] += 1

            # Store unique item descriptions for the category
            item_desc = item.get('description', '').strip()
            if item_desc not in self.categories[category]['unique_items']:
                self.categories[category]['unique_items'].append(item_desc)
    
    def _get_category_priority_order(self) -> List[str]:
        """
        Define priority order for categories.
        Cleaning, demolition, and water extraction should appear first.
        """
        return [
            'CLEANING',
            'GENERAL DEMOLITION',
            'WATER EXTRACTION & REMEDIATION',
            'TEMPORARY REPAIRS',
            # Then all other categories alphabetically
        ]

    def _sort_categories(self, categories: List[Dict]) -> List[Dict]:
        """Sort categories by priority order, then alphabetically"""
        priority_order = self._get_category_priority_order()

        def get_sort_key(category: Dict) -> tuple:
            name = category.get('name', '')
            try:
                # Priority categories come first
                priority_index = priority_order.index(name)
                return (0, priority_index, name)
            except ValueError:
                # Non-priority categories come after, sorted alphabetically
                return (1, 0, name)

        return sorted(categories, key=get_sort_key)

    def _build_response(self) -> Dict:
        """Build final response with sorted categories"""

        if not self.line_items:
            return {
                'success': False,
                'error': 'No line items found in estimate'
            }

        total_rcv = sum(item['rcv'] for item in self.line_items)
        total_depreciation = sum(item['depreciation'] for item in self.line_items)
        total_acv = sum(item['acv'] for item in self.line_items)

        # Sort categories with priority order
        sorted_categories = self._sort_categories(list(self.categories.values()))

        return {
            'success': True,
            'header': self.header_data,
            'line_items': self.line_items,
            'categories': sorted_categories,
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
                'rooms': list(set(item['room'] for item in self.line_items if item.get('room'))),
                'duplicates_removed': getattr(self, '_duplicates_removed', 0)
            }
        }