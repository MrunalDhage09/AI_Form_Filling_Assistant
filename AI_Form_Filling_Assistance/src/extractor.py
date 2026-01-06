"""
Document information extractor optimized for Indian government documents.
Patterns based on actual document samples:
- Aadhaar Card (UIDAI format - both physical and e-Aadhaar)
- PAN Card (Income Tax Department)
- Voter ID (Election Commission)
- Driving License (State RTOs)
- Handwritten Forms (Name, DOB, Address, etc.)
"""

import re
from typing import Dict, Optional, List


# ==================== HELPER FUNCTIONS ====================

# Hindi (Devanagari) to Arabic numeral mapping
HINDI_TO_ARABIC = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

# Colon OR Visarga pattern for regex
# ः = Devanagari Visarga (U+0903) - commonly used in Hindi documents
# : = Regular colon (U+003A)
# Usage in regex: [ः:] matches either character
COLON_OR_VISARGA = r'[ः:]'


def convert_hindi_numerals(text: str) -> str:
    """Convert Hindi/Devanagari numerals to Arabic numerals."""
    result = text
    for hindi, arabic in HINDI_TO_ARABIC.items():
        result = result.replace(hindi, arabic)
    return result


def clean_text_for_matching(text: str) -> str:
    """Clean text for pattern matching - convert Hindi numerals and normalize spaces."""
    text = convert_hindi_numerals(text)
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    return text


def is_hindi_text(text: str) -> bool:
    """Check if text contains predominantly Hindi/Devanagari characters."""
    hindi_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    alpha_chars = sum(1 for c in text if c.isalpha())
    if alpha_chars == 0:
        return False
    return hindi_chars / alpha_chars > 0.5


def extract_english_only(text: str) -> str:
    """Extract only English text from a mixed string."""
    # Remove Hindi characters and keep English + spaces + punctuation
    result = ''.join(c for c in text if not ('\u0900' <= c <= '\u097F'))
    return ' '.join(result.split())  # Normalize spaces


def extract_hindi_only(text: str) -> str:
    """Extract only Hindi/Devanagari text from a mixed string."""
    # Keep Hindi characters and spaces
    result = ''.join(c for c in text if '\u0900' <= c <= '\u097F' or c.isspace())
    return ' '.join(result.split())  # Normalize spaces


def looks_like_hindi_name(text: str) -> bool:
    """Check if text looks like a Hindi name."""
    text = extract_hindi_only(text).strip()
    if not text or len(text) < 2:
        return False
    words = text.split()
    if not (1 <= len(words) <= 6):
        return False
    return True


def looks_like_name(text: str) -> bool:
    """Check if text looks like a person's name (mostly alphabetic, 2-5 words)."""
    text = extract_english_only(text).strip()
    if not text or len(text) < 3:
        return False
    words = text.split()
    if not (1 <= len(words) <= 6):
        return False
    # Check if mostly alphabetic
    alpha_chars = sum(c.isalpha() or c.isspace() for c in text)
    return alpha_chars / max(len(text), 1) > 0.85


# ==================== REGEX PATTERNS ====================

# Date patterns (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY) - with optional spaces
DATE_PATTERN = re.compile(r'\b(\d{1,2})\s*[-/\.]\s*(\d{1,2})\s*[-/\.]\s*(\d{4})\b')

# Aadhaar: exactly 12 digits (may be spaced as XXXX XXXX XXXX)
AADHAAR_PATTERN = re.compile(r'\b(\d{4}\s?\d{4}\s?\d{4})\b')

# VID: exactly 16 digits (may be spaced as XXXX XXXX XXXX XXXX)
VID_PATTERN = re.compile(r'\b(\d{4}\s?\d{4}\s?\d{4}\s?\d{4})\b')

# PAN: exactly 10 characters (5 letters + 4 digits + 1 letter)
PAN_PATTERN = re.compile(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b')

# Voter ID: exactly 10 characters (3 letters + 7 digits, e.g., KKD1933993)
VOTER_ID_PATTERN = re.compile(r'\b([A-Z]{3}[0-9]{7})\b')

# Enrollment number: XXXX/XXXXX/XXXXX
ENROLLMENT_PATTERN = re.compile(r'\b(\d{4}[/]\d{5}[/]\d{5})\b')

# PIN Code: 6 digits
PIN_PATTERN = re.compile(r'\b(\d{6})\b')

# Mobile: 10 digits starting with 6-9
MOBILE_PATTERN = re.compile(r'\b([6-9]\d{9})\b')


def extract_date(text: str) -> Optional[str]:
    """Extract date from text, converting Hindi numerals if needed."""
    cleaned = clean_text_for_matching(text)
    match = DATE_PATTERN.search(cleaned)
    if match:
        return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
    return None


# ==================== AADHAAR EXTRACTION ====================

def extract_aadhaar(text: str, lines: List[str]) -> Dict[str, Optional[str]]:
    """
    Extract information from Aadhaar card (physical or e-Aadhaar).
    
    Sample format (e-Aadhaar):
    - Enrolment No.: 0636/00520/07859
    - To section with name and address
    - Your Aadhaar No.: 6713 3842 5045
    - VID: 9120 3595 3405 8780
    - DOB: 13/07/2001
    - Gender: MALE
    """
    info = {}
    text_lower = text.lower()
    
    # Convert Hindi numerals for pattern matching
    text_clean = clean_text_for_matching(text)
    
    # ===== Extract Aadhaar Number =====
    # Priority 1: Look for "Your Aadhaar No" or similar label
    aadhaar_labels = [
        r'your\s+aadhaar\s+no\.?\s*:?\s*',
        r'aadhaar\s+no\.?\s*:?\s*',
        r'आधार\s+क्रमांक\s*:?\s*',
        r'आपला\s+आधार\s+क्रमांक\s*:?\s*'
    ]
    
    aadhaar_number = None
    for label_pattern in aadhaar_labels:
        match = re.search(label_pattern + r'(\d{4}\s?\d{4}\s?\d{4})', text_clean, re.IGNORECASE)
        if match:
            aadhaar_number = match.group(1).replace(' ', '')
            break
    
    # Priority 2: Find 12-digit number that's NOT a VID (VID is 16 digits)
    if not aadhaar_number:
        # Find all potential Aadhaar numbers
        all_12digit = AADHAAR_PATTERN.findall(text_clean)
        # Find all VIDs (16 digits)
        all_16digit = VID_PATTERN.findall(text_clean)
        vid_numbers = set(v.replace(' ', '') for v in all_16digit)
        
        for num in all_12digit:
            clean_num = num.replace(' ', '')
            # Check it's exactly 12 digits and not part of a VID
            if len(clean_num) == 12:
                # Check context - should not be labeled as VID
                num_pos = text_clean.find(num)
                if num_pos != -1:
                    context_before = text_clean[max(0, num_pos-20):num_pos].lower()
                    if 'vid' not in context_before:
                        aadhaar_number = clean_num
                        break
    
    if aadhaar_number:
        info['document_id'] = aadhaar_number
        info['aadhaar_number'] = aadhaar_number
    
    # ===== Extract VID =====
    vid_match = re.search(r'vid\s*:?\s*(\d{4}\s?\d{4}\s?\d{4}\s?\d{4})', text_clean, re.IGNORECASE)
    if vid_match:
        info['vid'] = vid_match.group(1).replace(' ', '')
    
    # ===== Extract Enrollment Number =====
    enroll_patterns = [
        r'enrol(?:ment)?\s+no\.?\s*:?\s*(\d{4}/\d{5}/\d{5})',
        r'नोंदणी\s+क्रमांक\s*:?\s*(\d{4}/\d{5}/\d{5})'
    ]
    for pattern in enroll_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            info['enrollment_no'] = match.group(1)
            break
    
    # ===== Extract Name (Both Hindi and English) =====
    name = None
    name_hindi = None
    address_lines = []
    address_hindi_lines = []
    mobile = None
    
    # Method 1: Look for explicit name labels
    for i, line in enumerate(lines):
        line_lower = line.lower()
        line_clean = clean_text_for_matching(line)
        
        # Check for "Name:" pattern (handles both English and mixed text)
        # Pattern: looks for "Name:" or "name" label followed by value
        name_match = re.search(r'(?:name|नाम)\s*[ः:]?\s*([A-Za-z][A-Za-z\s]+)', line, re.IGNORECASE)
        if name_match and not name:
            potential_name = name_match.group(1).strip()
            if looks_like_name(potential_name):
                name = potential_name.title()
        
        # Also check for Hindi name in the same or adjacent line
        hindi_part = extract_hindi_only(line)
        if hindi_part and looks_like_hindi_name(hindi_part) and not name_hindi:
            # Skip common Hindi labels
            skip_hindi = ['भारत', 'सरकार', 'आधार', 'क्रमांक', 'नोंदणी', 'विशिष्ट', 'ओळख', 'प्राधिकरण']
            if not any(w in hindi_part for w in skip_hindi):
                name_hindi = hindi_part
    
    # Method 2: Find "To" marker and extract name
    if not name:
        to_index = -1
        for i, line in enumerate(lines):
            line_stripped = line.strip().lower()
            if line_stripped == 'to' or line_stripped.startswith('to ') or re.match(r'^\d*\s*to\b', line_stripped):
                to_index = i
                break
        
        if to_index >= 0:
            # Process lines after "To"
            for j in range(to_index + 1, min(to_index + 15, len(lines))):
                line = lines[j].strip()
                if not line:
                    continue
                
                # Check if line contains Hindi
                has_hindi = is_hindi_text(line)
                
                # Skip common headers/labels
                skip_patterns = ['download', 'issue', 'generation', 'validity', 'aadhaar no', 
                               'vid', 'enrol', 'unique', 'government', 'authority', 'qr code',
                               'dob', 'date of birth', 'male', 'female']
                is_label = any(p in line.lower() for p in skip_patterns)
                
                if is_label:
                    continue
                
                # Check for mobile number
                mobile_match = MOBILE_PATTERN.search(line)
                if mobile_match:
                    mobile = mobile_match.group(1)
                    if line.strip() == mobile:
                        continue
                
                # Extract Hindi name if present
                if has_hindi and not name_hindi:
                    hindi_part = extract_hindi_only(line)
                    skip_hindi = ['भारत', 'सरकार', 'आधार', 'क्रमांक', 'नोंदणी', 'विशिष्ट', 'ओळख', 'प्राधिकरण', 'माझे', 'माझी']
                    if hindi_part and looks_like_hindi_name(hindi_part):
                        if not any(w in hindi_part for w in skip_hindi):
                            name_hindi = hindi_part
                
                # Extract English portion
                english_text = extract_english_only(line)
                if english_text and looks_like_name(english_text) and not name:
                    name = english_text.title()
    
    # Method 3: Look for English name near Hindi name in same line
    if not name:
        for line in lines:
            # Look for pattern where Hindi name is followed by English name
            # e.g., "राम चंद्रशेखर Ram Chandrashekhar"
            english_part = extract_english_only(line)
            hindi_part = extract_hindi_only(line)
            
            if english_part and looks_like_name(english_part):
                # Make sure this isn't a label or common text
                skip_words = ['government', 'india', 'authority', 'aadhaar', 'unique', 
                             'identification', 'enrolment', 'download', 'generation',
                             'validity', 'male', 'female', 'dob', 'date', 'birth']
                if not any(w in english_part.lower() for w in skip_words):
                    name = english_part.title()
            
            # Also capture Hindi name from same line
            if hindi_part and looks_like_hindi_name(hindi_part) and not name_hindi:
                skip_hindi = ['भारत', 'सरकार', 'आधार', 'क्रमांक', 'नोंदणी', 'विशिष्ट', 'ओळख', 'प्राधिकरण', 'माझे', 'माझी']
                if not any(w in hindi_part for w in skip_hindi):
                    name_hindi = hindi_part
            
            if name:
                break
    
    if name:
        # Clean up name - remove any trailing Hindi characters or garbage
        name = extract_english_only(name).strip()
        # Remove duplicate words (e.g., "Singh Singh" -> "Singh")
        words = name.split()
        cleaned_words = []
        for word in words:
            if not cleaned_words or word.lower() != cleaned_words[-1].lower():
                cleaned_words.append(word)
        name = ' '.join(cleaned_words)
        if name:
            info['name'] = name
    
    if name_hindi:
        info['name_hindi'] = name_hindi
    
    if mobile:
        info['mobile'] = mobile
    
    # ===== Build Address (Both Hindi and English) =====
    # Re-process to get address lines (after name was found)
    if name or name_hindi:
        found_name = False
        search_name = name.lower() if name else ''
        
        for j, line in enumerate(lines):
            if search_name and search_name in extract_english_only(line).lower():
                found_name = True
                continue
            # Also check if we passed the Hindi name
            if name_hindi and name_hindi in line:
                found_name = True
                continue
            
            if found_name:
                line_english = extract_english_only(line).strip()
                line_hindi = extract_hindi_only(line).strip()
                
                # Skip labels and empty lines
                skip_patterns = ['download', 'issue', 'generation', 'validity', 'aadhaar', 
                               'vid', 'unique', 'government', 'authority', 'qr code',
                               'dob', 'date of birth', 'male', 'female', 'enrol']
                skip_hindi_patterns = ['आधार', 'क्रमांक', 'माझे', 'माझी', 'ओळख', 'सरकार']
                
                if any(p in line.lower() for p in skip_patterns):
                    continue
                
                # Stop at certain markers
                if 'your aadhaar' in line.lower() or re.search(r'\d{4}\s*\d{4}\s*\d{4}', line):
                    break
                
                # Remove mobile numbers
                line_english = MOBILE_PATTERN.sub('', line_english).strip(' ,')
                
                # Collect English address
                if line_english and len(line_english) > 2:
                    address_lines.append(line_english)
                
                # Collect Hindi address (skip common labels)
                if line_hindi and len(line_hindi) > 2:
                    if not any(p in line_hindi for p in skip_hindi_patterns):
                        address_hindi_lines.append(line_hindi)
                
                # Stop after collecting enough address lines
                if len(address_lines) >= 6:
                    break
    
    if address_lines:
        full_address = ', '.join(address_lines)
        pin_match = PIN_PATTERN.search(full_address)
        if pin_match:
            info['pin_code'] = pin_match.group(1)
        info['address'] = full_address
    
    if address_hindi_lines:
        info['address_hindi'] = ', '.join(address_hindi_lines)
    
    # ===== Extract DOB =====
    # Convert Hindi numerals before DOB extraction
    for line in lines:
        line_clean = clean_text_for_matching(line)
        line_lower = line_clean.lower()
        
        # Check for DOB label
        if 'dob' in line_lower or 'date of birth' in line_lower or 'birth' in line_lower or 'जन्म' in line:
            date = extract_date(line_clean)
            if date:
                info['date_of_birth'] = date
                break
    
    # ===== Extract Gender (Both Hindi and English) =====
    gender_patterns = [
        (r'\bfemale\b', 'Female', 'महिला'),
        (r'\bmale\b', 'Male', 'पुरुष'),
        (r'पुरुष', 'Male', 'पुरुष'),
        (r'महिला', 'Female', 'महिला'),
        (r'\b[/]?\s*female\b', 'Female', 'महिला'),
        (r'\b[/]?\s*male\b', 'Male', 'पुरुष')
    ]
    
    # Check female first to avoid false match with male
    for pattern, gender, gender_hindi in gender_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            if gender == 'Male':
                # Make sure it's not actually "female"
                if not re.search(r'\bfemale\b', text, re.IGNORECASE):
                    info['gender'] = gender
                    info['gender_hindi'] = gender_hindi
                    break
            else:
                info['gender'] = gender
                info['gender_hindi'] = gender_hindi
                break
    
    return info


# ==================== PAN EXTRACTION ====================

def clean_name_from_numbers(name: str) -> str:
    """
    Remove date-like numbers and standalone digits from a name string.
    E.g., "CHANDRASHEKHAR MANIKRAO 09112019" -> "CHANDRASHEKHAR MANIKRAO"
    """
    if not name:
        return name
    # Remove standalone numbers (dates, etc.)
    cleaned = re.sub(r'\b\d+\b', '', name)
    # Normalize spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def extract_pan(text: str, lines: List[str]) -> Dict[str, Optional[str]]:
    """
    Extract information from PAN card.
    
    Sample format:
    - Income Tax Department / Govt. of India
    - Permanent Account Number Card
    - PAN: ABCDE1234F
    - Name
    - Father's Name
    - DOB
    """
    info = {}
    text_upper = text.upper()
    text_clean = clean_text_for_matching(text)
    
    # Extract PAN Number
    pan_match = PAN_PATTERN.search(text_upper)
    if pan_match:
        info['document_id'] = pan_match.group(1)
        info['pan_number'] = pan_match.group(1)
    
    # Extract Name and Father's Name (Both Hindi and English)
    name = None
    name_hindi = None
    father_name = None
    father_name_hindi = None
    dob = None
    
    # Track line indices for name and father's name labels
    name_label_index = -1
    father_label_index = -1
    dob_label_index = -1
    
    # First pass: find label positions
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Find "Name" label (not Father's Name)
        if ('name' in line_lower or 'नाम' in line) and 'father' not in line_lower and 'पिता' not in line:
            if name_label_index == -1:
                name_label_index = i
        
        # Find "Father's Name" label - handle OCR variations like "Father s Name"
        # Also handle: "पिता का नाम", "father's name", "father s name", "fathers name"
        if re.search(r"father'?s?\s+name|पिता\s*(का\s*)?नाम", line_lower):
            father_label_index = i
        
        # Find DOB label
        if 'date of birth' in line_lower or 'birth' in line_lower or 'जन्म' in line:
            if dob_label_index == -1:
                dob_label_index = i
    
    # Process lines to find name and father's name
    for i, line in enumerate(lines):
        line_lower = line.lower()
        line_stripped = line.strip()
        line_clean = clean_text_for_matching(line)
        
        # Skip headers and labels only lines
        if any(x in line_lower for x in ['income tax', 'permanent account', 'government', 'dept', 'signature', 'हस्ताक्षर']):
            continue
        
        # Look for Name field - multiple patterns
        # Pattern 1: "नाम / Name VALUE" or "Name: VALUE" inline
        if ('name' in line_lower or 'नाम' in line) and 'father' not in line_lower and 'पिता' not in line:
            # Try to extract inline value after "Name"
            # Handle formats like: "नाम / Name APPLICANT NAME" or "Name: John Doe"
            # Note: [ः:/] matches visarga (ः) OR colon (:) OR slash (/)
            name_patterns = [
                r'(?:नाम\s*/?\s*)?name\s*[ः:/]?\s*([A-Z][A-Z\s]+)',
                r'name\s*[ः:/]?\s*([A-Z][A-Z\s]+)',
            ]
            for pattern in name_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    potential_name = match.group(1).strip()
                    # Filter out common false positives
                    if potential_name and len(potential_name) > 2:
                        if not any(x in potential_name.lower() for x in ['father', 'signature', 'card', 'permanent', 'account']):
                            name = clean_name_from_numbers(potential_name.upper())
                            break
            
            # Extract Hindi name from the line
            hindi_part = extract_hindi_only(line)
            if hindi_part and looks_like_hindi_name(hindi_part) and not name_hindi:
                skip_hindi = ['नाम', 'आयकर', 'विभाग', 'भारत', 'सरकार', 'स्थायी', 'लेखा', 'संख्या', 'कार्ड']
                cleaned_hindi = ' '.join(w for w in hindi_part.split() if w not in skip_hindi)
                if cleaned_hindi and len(cleaned_hindi) > 2:
                    name_hindi = cleaned_hindi
            
            # If not found inline, check next line(s)
            if not name and i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                next_line = clean_name_from_numbers(next_line)
                if next_line and looks_like_name(next_line):
                    if 'father' not in next_line.lower():
                        name = next_line.upper()
        
        # Look for Father's Name - multiple patterns
        # Handle: "पिता का नाम/ Father s Name" (OCR often misses apostrophe)
        # The name is usually on the NEXT line(s)
        elif re.search(r"father'?s?\s+name|पिता\s*(का\s*)?नाम", line_lower):
            # Try to extract inline value after the label
            # Handle "Father s Name" (space instead of apostrophe)
            father_inline_patterns = [
                r"father'?s?\s+name\s*[:/]?\s*([A-Z][A-Z\s]+)",
                r"पिता\s*का\s*नाम[ः:/]?\s*([A-Z][A-Z\s]+)",
            ]
            for pattern in father_inline_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    potential = match.group(1).strip()
                    potential = clean_name_from_numbers(potential)
                    if potential and len(potential) > 2:
                        if not any(x in potential.lower() for x in ['signature', 'card', 'date', 'birth', 's name']):
                            father_name = potential.upper()
                            break
            
            # Extract Hindi father's name from the line
            hindi_part = extract_hindi_only(line)
            if hindi_part and not father_name_hindi:
                skip_hindi = ['पिता', 'का', 'नाम', 'भारत', 'सरकार']
                cleaned_hindi = ' '.join(w for w in hindi_part.split() if w not in skip_hindi)
                if cleaned_hindi and looks_like_hindi_name(cleaned_hindi):
                    father_name_hindi = cleaned_hindi
            
            # If not found inline, check next lines (name might be split across multiple lines)
            if not father_name:
                father_name_parts = []
                # Look at next 2-3 lines for the father's name
                for j in range(1, 4):
                    if i + j >= len(lines):
                        break
                    next_line = lines[i + j].strip()
                    next_line_lower = next_line.lower()
                    
                    # Stop if we hit another label or DOB
                    if any(x in next_line_lower for x in ['date', 'birth', 'जन्म', 'signature', 'हस्ताक्षर']):
                        break
                    
                    # Extract English portion
                    english_part = extract_english_only(next_line)
                    english_part = clean_name_from_numbers(english_part)
                    
                    if english_part and len(english_part) > 1:
                        # Check if it looks like a name part
                        if re.match(r'^[A-Z][A-Z\s]*$', english_part.upper()):
                            father_name_parts.append(english_part.upper())
                    
                    # Also check for Hindi father's name
                    if not father_name_hindi:
                        hindi_part = extract_hindi_only(next_line)
                        skip_hindi = ['पिता', 'का', 'नाम', 'भारत', 'सरकार', 'जन्म', 'तारीख']
                        if hindi_part:
                            cleaned_hindi = ' '.join(w for w in hindi_part.split() if w not in skip_hindi)
                            if cleaned_hindi and looks_like_hindi_name(cleaned_hindi):
                                father_name_hindi = cleaned_hindi
                
                if father_name_parts:
                    father_name = ' '.join(father_name_parts)
        
        # Look for DOB
        elif 'date of birth' in line_lower or 'dob' in line_lower or 'birth' in line_lower or 'जन्म' in line:
            date = extract_date(line_clean)
            if date:
                dob = date
            elif i + 1 < len(lines):
                date = extract_date(clean_text_for_matching(lines[i + 1]))
                if date:
                    dob = date
    
    if name:
        # Clean name - remove duplicates and extra characters
        name = re.sub(r'\s+', ' ', name).strip()
        info['name'] = name
    if name_hindi:
        info['name_hindi'] = name_hindi
    if father_name:
        father_name = re.sub(r'\s+', ' ', father_name).strip()
        info['father_name'] = father_name
    if father_name_hindi:
        info['father_name_hindi'] = father_name_hindi
    if dob:
        info['date_of_birth'] = dob
    
    return info


# ==================== VOTER ID EXTRACTION ====================

def extract_voter_id(text: str, lines: List[str]) -> Dict[str, Optional[str]]:
    """
    Extract information from Voter ID (EPIC) card.
    
    Sample format:
    - ELECTION COMMISSION OF INDIA
    - Elector Photo Identity Card
    - Voter ID: KKD1933993 (3 letters + 7 digits)
    - Name: Abhishek Kumar Singh
    - Father's Name: Lalababu Singh
    - Gender: Male
    - DOB: 11-08-1990
    """
    info = {}
    text_upper = text.upper()
    text_clean = clean_text_for_matching(text)
    
    # ===== Extract Voter ID Number =====
    voter_id_match = VOTER_ID_PATTERN.search(text_upper)
    if voter_id_match:
        info['document_id'] = voter_id_match.group(1)
        info['voter_id'] = voter_id_match.group(1)
    
    # ===== Extract Name and Father's Name (Both Hindi and English) =====
    name = None
    name_hindi = None
    father_name = None
    father_name_hindi = None
    
    # First pass: Extract all Hindi names and labels
    for i, line in enumerate(lines):
        line_lower = line.lower()
        line_clean = clean_text_for_matching(line)
        
        # Skip headers
        if any(x in line_lower for x in ['election commission', 'elector photo', 'identity card', 'भारत निर्वाचन']):
            continue
        
        # Extract Hindi name (नाम: or नामः but not पिता का नाम:)
        # Pattern: "नामः अभिषेक कुमार सिंह" or "नाम: अभिषेक कुमार सिंह"
        # Note: ः is visarga (Devanagari), : is regular colon
        if 'नाम' in line and 'पिता' not in line:
            # Try both visarga (ः) and regular colon (:)
            hindi_name_match = re.search(r'नाम\s*[ः:]\s*(.+)', line)
            if hindi_name_match and not name_hindi:
                # Get everything after नाम:/नामः
                after_label = hindi_name_match.group(1)
                hindi_part = extract_hindi_only(after_label)
                if hindi_part and looks_like_hindi_name(hindi_part):
                    name_hindi = hindi_part
        
        # Extract Hindi father's name (पिता का नामः लालबाबू सिंह or पिता का नाम:)
        if 'पिता' in line and 'नाम' in line:
            # Match पिता का नाम:/नामः or just after the colon/visarga
            hindi_father_match = re.search(r'पिता\s*(?:का\s*)?नाम\s*[ः:]\s*(.+)', line)
            if hindi_father_match and not father_name_hindi:
                after_label = hindi_father_match.group(1)
                hindi_part = extract_hindi_only(after_label)
                if hindi_part and looks_like_hindi_name(hindi_part):
                    father_name_hindi = hindi_part
    
    # Second pass: Extract English names
    for i, line in enumerate(lines):
        line_lower = line.lower()
        line_clean = clean_text_for_matching(line)
        
        # Skip headers
        if any(x in line_lower for x in ['election commission', 'elector photo', 'identity card', 'भारत निर्वाचन']):
            continue
        
        # Look for English Name field (not Father's Name)
        if ('name' in line_lower) and 'father' not in line_lower:
            name_match = re.search(r'name\s*:\s*([A-Za-z][A-Za-z\s]+)', line, re.IGNORECASE)
            if name_match and not name:
                potential = name_match.group(1).strip()
                potential = extract_english_only(potential)
                if potential and looks_like_name(potential):
                    name = potential.title()
        
        # Look for English Father's Name
        elif 'father' in line_lower and 'name' in line_lower:
            father_match = re.search(r"father'?s?\s*name\s*:\s*([A-Za-z][A-Za-z\s]+)", line, re.IGNORECASE)
            if father_match and not father_name:
                potential = father_match.group(1).strip()
                potential = extract_english_only(potential)
                if potential and looks_like_name(potential):
                    father_name = potential.title()
        
        # Look for DOB
        elif 'date of birth' in line_lower or 'dob' in line_lower or 'birth' in line_lower or 'age' in line_lower or 'जन्म' in line:
            date = extract_date(line_clean)
            if date:
                info['date_of_birth'] = date
        
        # Look for Gender
        elif 'gender' in line_lower or 'लिंग' in line or 'sex' in line_lower:
            # Check for female first (to avoid false positive with "male" in "female")
            if 'female' in line_lower or 'महिला' in line:
                info['gender'] = 'Female'
                info['gender_hindi'] = 'महिला'
            elif 'male' in line_lower or 'पुरुष' in line:
                info['gender'] = 'Male'
                info['gender_hindi'] = 'पुरुष'
    
    # Clean up names - remove duplicate words
    if name:
        words = name.split()
        cleaned_words = []
        for word in words:
            if not cleaned_words or word.lower() != cleaned_words[-1].lower():
                cleaned_words.append(word)
        name = ' '.join(cleaned_words)
        info['name'] = name
    
    if name_hindi:
        # Also clean Hindi names - remove duplicates
        words = name_hindi.split()
        cleaned_words = []
        for word in words:
            if not cleaned_words or word != cleaned_words[-1]:
                cleaned_words.append(word)
        name_hindi = ' '.join(cleaned_words)
        info['name_hindi'] = name_hindi
    
    if father_name:
        words = father_name.split()
        cleaned_words = []
        for word in words:
            if not cleaned_words or word.lower() != cleaned_words[-1].lower():
                cleaned_words.append(word)
        father_name = ' '.join(cleaned_words)
        info['father_name'] = father_name
    
    if father_name_hindi:
        words = father_name_hindi.split()
        cleaned_words = []
        for word in words:
            if not cleaned_words or word != cleaned_words[-1]:
                cleaned_words.append(word)
        father_name_hindi = ' '.join(cleaned_words)
        info['father_name_hindi'] = father_name_hindi
    
    return info


# ==================== DRIVING LICENSE EXTRACTION ====================

# Driving License pattern: State code (2 letters) + RTO code (2 digits) + Year (4 digits or 2 digits) + Number (7 digits)
# Examples: MH12 20010149313, KA01 20201234567, DL1420190012345
DRIVING_LICENSE_PATTERN = re.compile(r'\b([A-Z]{2}\s*\d{2}\s*\d{4,11})\b')


def extract_driving_license(text: str, lines: List[str]) -> Dict[str, Optional[str]]:
    """
    Extract information from Indian Driving Licence.
    
    Sample format:
    - State Motor Driving Licence
    - DL No: MH12 20010149313
    - Name: NIVRUTTI BODAKE
    - S/O or D/O: Father's name
    - Address: Village/Town
    - TAL: Taluka
    - DIST: District
    - DOB: Date of Birth
    - Valid Till: Expiry date
    """
    info = {}
    text_upper = text.upper()
    text_clean = clean_text_for_matching(text)
    
    # ===== Extract DL Number =====
    # Look for DL No pattern with various OCR variations
    dl_patterns = [
        r'DL[_\s]*(?:NO|N0)[.\s:]*([A-Z]{2}\s*\d{2}\s*\d{4,11})',
        r'(?:DRIVING\s*)?(?:LICENCE|LICENSE)[.\s:]*(?:NO|N0)?[.\s:]*([A-Z]{2}\s*\d{2}\s*\d{4,11})',
        r'\b([A-Z]{2}\s*\d{2}\s*\d{9,11})\b',  # Standard DL format
        r'\b(MH\d{2}\s*\d{8,11})\b',  # Maharashtra specific
        r'\b(KA\d{2}\s*\d{8,11})\b',  # Karnataka specific
        r'\b(DL\d{2}\s*\d{8,11})\b',  # Delhi specific
    ]
    
    dl_number = None
    for pattern in dl_patterns:
        match = re.search(pattern, text_upper)
        if match:
            dl_number = match.group(1).replace(' ', '')
            break
    
    if dl_number:
        info['document_id'] = dl_number
        info['dl_number'] = dl_number
    
    # ===== Extract Name and Father's Name =====
    name = None
    father_name = None
    
    # Process line by line for better accuracy
    for i, line in enumerate(lines):
        line_upper = line.upper().strip()
        line_lower = line.lower().strip()
        
        # Skip header lines without name field
        if any(x in line_lower for x in ['motor', 'driving', 'licence', 'license', 'union of india', 'maharashtra state', 'karnataka']):
            if 'name' not in line_lower:
                continue
        
        # === CASE 1: Line has BOTH "Name" and "S/O" pattern (merged OCR) ===
        has_name = 'name' in line_lower
        has_so = bool(re.search(r'sdan|s[/\s]*o\b|d[/\s]*o\b|son\s*of|daughter', line_lower))
        
        if has_name and has_so:
            # Extract name - between "Name:" and S/O pattern
            name_match = re.search(r'NAME\s*[:\s]+([A-Z][A-Z\s]+?)(?=SDAN|S\s*/?\s*O|D\s*/?\s*O|SON|DAUGHTER)', line_upper)
            if name_match and not name:
                potential = name_match.group(1).strip()
                potential = clean_name_from_numbers(potential)
                if potential and len(potential) > 2:
                    name = potential
            
            # Extract father's name - after S/O pattern
            father_match = re.search(r'(?:SDAN|S\s*/?\s*O|D\s*/?\s*O|SON|DAUGHTER)\s*(?:OF)?[:\s]*([A-Z][A-Z\s]+)', line_upper)
            if father_match and not father_name:
                potential = father_match.group(1).strip()
                potential = clean_name_from_numbers(potential)
                potential = re.sub(r'\s*(ADD|TAL|DIST|DOB|AP).*$', '', potential, flags=re.IGNORECASE).strip()
                if potential and len(potential) > 2:
                    father_name = potential
            continue
        
        # === CASE 2: Line has only "Name:" (standalone) ===
        if has_name and not has_so:
            # Multiple patterns to extract name (use IGNORECASE for flexibility)
            name_patterns = [
                r'NAME\s*[:\s]+([A-Z][A-Z\s]+)',
                r'NAME\s*[:]+\s*([A-Z][A-Z\s]+)',
                r'NAME\s*:\s*([A-Z][A-Z\s]+)',
            ]
            for pattern in name_patterns:
                name_match = re.search(pattern, line_upper)
                if name_match and not name:
                    potential = name_match.group(1).strip()
                    potential = clean_name_from_numbers(potential)
                    # Remove any trailing S/O text that might have been captured
                    potential = re.sub(r'(SDAN|S\s*/?\s*O|D\s*/?\s*O|SON|DAUGHTER).*$', '', potential, flags=re.IGNORECASE).strip()
                    if potential and len(potential) > 2:
                        name = potential
                        break
            
            # If still no name, check next line
            if not name and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                next_upper = next_line.upper()
                # Make sure next line doesn't start with S/O pattern
                if not re.search(r'^(SDAN|S\s*/?\s*O|D\s*/?\s*O|SON|DAUGHTER)', next_upper):
                    next_english = extract_english_only(next_line).strip().upper()
                    next_english = clean_name_from_numbers(next_english)
                    if next_english and len(next_english) > 2:
                        name = next_english
        
        # === CASE 3: Line has S/O pattern (father's name) ===
        elif has_so and not has_name:
            father_patterns = [
                r'(?:SDAN|S\s*/?\s*O|D\s*/?\s*O)\s*(?:OF|Of)?[:\s]*([A-Z][A-Z\s]+)',
                r'(?:SON|DAUGHTER)\s*(?:OF|Of)?[:\s]*([A-Z][A-Z\s]+)',
            ]
            for pattern in father_patterns:
                father_match = re.search(pattern, line_upper)
                if father_match and not father_name:
                    potential = father_match.group(1).strip()
                    potential = clean_name_from_numbers(potential)
                    potential = re.sub(r'\s*(ADD|TAL|DIST|DOB|AP|ADDRESS).*$', '', potential, flags=re.IGNORECASE).strip()
                    if potential and len(potential) > 2:
                        father_name = potential
                        break
            
            # If no father name found inline, check next line
            if not father_name and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                next_english = extract_english_only(next_line).strip().upper()
                next_english = clean_name_from_numbers(next_english)
                # Make sure it's not an address field
                if next_english and len(next_english) > 2 and not re.search(r'^(ADD|TAL|DIST|AP)', next_english):
                    father_name = next_english
        
        # Look for Address fields
        # Address pattern: "Add" or "Address"
        if re.search(r'\b(?:add|address)\b', line_lower):
            addr_match = re.search(r'(?:add(?:ress)?)[:\s]+(.+)', line, re.IGNORECASE)
            if addr_match:
                addr = addr_match.group(1).strip()
                addr = extract_english_only(addr)
                if addr and len(addr) > 2:
                    info['address'] = addr
        
        # Look for Taluka (TAL)
        if re.search(r'\btal\b', line_lower):
            tal_match = re.search(r'tal[:\s]+([A-Za-z]+)', line, re.IGNORECASE)
            if tal_match:
                info['taluka'] = tal_match.group(1).strip().upper()
        
        # Look for District (DIST)
        if re.search(r'\bdis(?:t|tr)?\b', line_lower):
            dist_match = re.search(r'dis(?:t|tr)?[:\s]+([A-Za-z]+)', line, re.IGNORECASE)
            if dist_match:
                info['district'] = dist_match.group(1).strip().upper()
        
        # Look for DOB (Date of Birth) - various OCR patterns
        if re.search(r'\b(?:dob|doe|d\.o\.b|date\s*of\s*birth|b\.?c)\b', line_lower):
            line_for_date = clean_text_for_matching(line)
            date = extract_date(line_for_date)
            if date:
                info['date_of_birth'] = date
        
        # Look for Valid Till / Expiry
        if re.search(r'\b(?:valid|expir|till)\b', line_lower):
            line_for_date = clean_text_for_matching(line)
            date = extract_date(line_for_date)
            if date:
                info['valid_till'] = date
        
        # Look for Issue Date
        if re.search(r'\b(?:issue|doi|dld)\b', line_lower):
            line_for_date = clean_text_for_matching(line)
            date = extract_date(line_for_date)
            if date:
                info['date_of_issue'] = date
    
    # Store extracted names
    if name:
        info['name'] = name
    if father_name:
        info['father_name'] = father_name
    
    # Build full address if we have components
    address_parts = []
    if info.get('address'):
        address_parts.append(info['address'])
    if info.get('taluka'):
        address_parts.append(f"Tal: {info['taluka']}")
    if info.get('district'):
        address_parts.append(f"Dist: {info['district']}")
    
    if len(address_parts) > 1:
        info['full_address'] = ', '.join(address_parts)
    
    return info


# ==================== HANDWRITTEN FORM EXTRACTION ====================

def extract_handwritten(text: str, lines: List[str]) -> Dict[str, Optional[str]]:
    """
    Extract information from handwritten forms.
    
    Looks for common form fields:
    - First Name, Middle Name, Surname/Last Name
    - Full Name
    - Father's Name, Mother's Name
    - Date of Birth / DOB
    - Address, City, State, PIN Code
    - Gender / Sex
    - Mobile / Phone
    - Email
    - Age, Occupation, etc.
    """
    info = {}
    text_lower = text.lower()
    text_clean = clean_text_for_matching(text)
    
    # Track found values to avoid duplicates
    first_name = None
    middle_name = None
    surname = None
    full_name = None
    father_name = None
    mother_name = None
    dob = None
    address_parts = []
    city = None
    state = None
    pin_code = None
    gender = None
    mobile = None
    email = None
    age = None
    occupation = None
    
    # Process line by line
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        line_upper = line.upper().strip()
        line_clean = clean_text_for_matching(line)
        
        # ===== Extract First Name =====
        if re.search(r'\b(?:first\s*name|fname)\b', line_lower):
            # Try to find value after the label
            patterns = [
                r'(?:first\s*name|fname)\s*[:\-]?\s*([A-Za-z]+)',
                r'(?:first\s*name|fname)\s*[:\-]?\s*$',  # Label only on this line
            ]
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match and match.lastindex and match.group(1):
                    potential = match.group(1).strip()
                    if potential and len(potential) > 1:
                        first_name = potential.upper()
                        break
            
            # Check next line if label is alone
            if not first_name and i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and len(next_line) > 1 and looks_like_name(next_line):
                    first_name = next_line.upper()
        
        # ===== Extract Middle Name =====
        elif re.search(r'\b(?:middle\s*name|mname)\b', line_lower):
            patterns = [
                r'(?:middle\s*name|mname)\s*[:\-]?\s*([A-Za-z]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match and match.lastindex and match.group(1):
                    potential = match.group(1).strip()
                    if potential and len(potential) > 1:
                        middle_name = potential.upper()
                        break
            
            if not middle_name and i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and len(next_line) > 1 and looks_like_name(next_line):
                    middle_name = next_line.upper()
        
        # ===== Extract Surname / Last Name =====
        elif re.search(r'\b(?:surname|sur\s*name|last\s*name|lname|family\s*name)\b', line_lower):
            patterns = [
                r'(?:surname|sur\s*name|last\s*name|lname|family\s*name)\s*[:\-]?\s*([A-Za-z]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match and match.lastindex and match.group(1):
                    potential = match.group(1).strip()
                    if potential and len(potential) > 1:
                        surname = potential.upper()
                        break
            
            if not surname and i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and len(next_line) > 1 and looks_like_name(next_line):
                    surname = next_line.upper()
        
        # ===== Extract Full Name (when not split into first/middle/last) =====
        elif re.search(r'\b(?:full\s*name|name|applicant\s*name)\b', line_lower) and not re.search(r'\b(?:first|middle|last|surname|father|mother)\b', line_lower):
            patterns = [
                r'(?:full\s*name|(?<!first\s)(?<!middle\s)(?<!last\s)name|applicant\s*name)\s*[:\-]?\s*([A-Za-z][A-Za-z\s]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match and match.group(1):
                    potential = match.group(1).strip()
                    potential = clean_name_from_numbers(potential)
                    if potential and len(potential) > 2 and looks_like_name(potential):
                        full_name = potential.upper()
                        break
            
            if not full_name and i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                next_line = clean_name_from_numbers(next_line)
                if next_line and len(next_line) > 2 and looks_like_name(next_line):
                    full_name = next_line.upper()
        
        # ===== Extract Father's Name =====
        elif re.search(r"\b(?:father'?s?\s*name|f/?name|father)\b", line_lower) and 'grand' not in line_lower:
            patterns = [
                r"(?:father'?s?\s*name|f/?name)\s*[:\-]?\s*([A-Za-z][A-Za-z\s]+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match and match.group(1):
                    potential = match.group(1).strip()
                    potential = clean_name_from_numbers(potential)
                    if potential and len(potential) > 2 and looks_like_name(potential):
                        father_name = potential.upper()
                        break
            
            if not father_name and i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                next_line = clean_name_from_numbers(next_line)
                if next_line and len(next_line) > 2 and looks_like_name(next_line):
                    father_name = next_line.upper()
        
        # ===== Extract Mother's Name =====
        elif re.search(r"\b(?:mother'?s?\s*name|m/?name|mother)\b", line_lower):
            patterns = [
                r"(?:mother'?s?\s*name|m/?name)\s*[:\-]?\s*([A-Za-z][A-Za-z\s]+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match and match.group(1):
                    potential = match.group(1).strip()
                    potential = clean_name_from_numbers(potential)
                    if potential and len(potential) > 2 and looks_like_name(potential):
                        mother_name = potential.upper()
                        break
            
            if not mother_name and i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                next_line = clean_name_from_numbers(next_line)
                if next_line and len(next_line) > 2 and looks_like_name(next_line):
                    mother_name = next_line.upper()
        
        # ===== Extract Date of Birth =====
        elif re.search(r'\b(?:d\.?o\.?b|date\s*of\s*birth|birth\s*date|dob)\b', line_lower):
            date = extract_date(line_clean)
            if date:
                dob = date
            elif i + 1 < len(lines):
                date = extract_date(clean_text_for_matching(lines[i + 1]))
                if date:
                    dob = date
        
        # ===== Extract Age =====
        elif re.search(r'\bage\b', line_lower):
            age_match = re.search(r'age\s*[:\-]?\s*(\d{1,3})', line, re.IGNORECASE)
            if age_match:
                potential_age = int(age_match.group(1))
                if 0 < potential_age < 150:
                    age = str(potential_age)
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                age_match = re.search(r'^(\d{1,3})$', next_line)
                if age_match:
                    potential_age = int(age_match.group(1))
                    if 0 < potential_age < 150:
                        age = str(potential_age)
        
        # ===== Extract Gender =====
        elif re.search(r'\b(?:gender|sex)\b', line_lower):
            if re.search(r'\bfemale\b', line_lower):
                gender = 'Female'
            elif re.search(r'\bmale\b', line_lower):
                gender = 'Male'
            elif re.search(r'\bother\b', line_lower):
                gender = 'Other'
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip().lower()
                if 'female' in next_line:
                    gender = 'Female'
                elif 'male' in next_line:
                    gender = 'Male'
                elif 'other' in next_line:
                    gender = 'Other'
        
        # ===== Extract Address =====
        elif re.search(r'\b(?:address|addr|residence)\b', line_lower) and 'email' not in line_lower:
            addr_match = re.search(r'(?:address|addr|residence)\s*[:\-]?\s*(.+)', line, re.IGNORECASE)
            if addr_match:
                addr_text = addr_match.group(1).strip()
                if addr_text and len(addr_text) > 2:
                    address_parts.append(addr_text)
            # Also check next few lines for address continuation
            for j in range(1, 4):
                if i + j < len(lines):
                    next_line = lines[i + j].strip()
                    # Stop if we hit another field label
                    if re.search(r'(?:city|state|pin|mobile|phone|email|gender|name|dob)', next_line.lower()):
                        break
                    if next_line and len(next_line) > 2:
                        address_parts.append(next_line)
        
        # ===== Extract City =====
        elif re.search(r'\b(?:city|town|village)\b', line_lower):
            city_match = re.search(r'(?:city|town|village)\s*[:\-]?\s*([A-Za-z\s]+)', line, re.IGNORECASE)
            if city_match:
                potential = city_match.group(1).strip()
                if potential and len(potential) > 1:
                    city = potential.upper()
            elif i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and len(next_line) > 1:
                    city = next_line.upper()
        
        # ===== Extract State =====
        elif re.search(r'\bstate\b', line_lower) and 'marital' not in line_lower:
            state_match = re.search(r'state\s*[:\-]?\s*([A-Za-z\s]+)', line, re.IGNORECASE)
            if state_match:
                potential = state_match.group(1).strip()
                if potential and len(potential) > 1:
                    state = potential.upper()
            elif i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and len(next_line) > 1:
                    state = next_line.upper()
        
        # ===== Extract PIN Code =====
        elif re.search(r'\b(?:pin\s*code|pincode|postal\s*code|zip)\b', line_lower):
            pin_match = re.search(r'(\d{6})', line)
            if pin_match:
                pin_code = pin_match.group(1)
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                pin_match = re.search(r'(\d{6})', next_line)
                if pin_match:
                    pin_code = pin_match.group(1)
        
        # ===== Extract Mobile/Phone =====
        elif re.search(r'\b(?:mobile|phone|contact|tel)\b', line_lower):
            mobile_match = MOBILE_PATTERN.search(line)
            if mobile_match:
                mobile = mobile_match.group(1)
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                mobile_match = MOBILE_PATTERN.search(next_line)
                if mobile_match:
                    mobile = mobile_match.group(1)
        
        # ===== Extract Email =====
        elif re.search(r'\bemail\b', line_lower):
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
            if email_match:
                email = email_match.group(0).lower()
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', next_line)
                if email_match:
                    email = email_match.group(0).lower()
        
        # ===== Extract Occupation =====
        elif re.search(r'\b(?:occupation|profession|job)\b', line_lower):
            occ_match = re.search(r'(?:occupation|profession|job)\s*[:\-]?\s*([A-Za-z\s]+)', line, re.IGNORECASE)
            if occ_match:
                potential = occ_match.group(1).strip()
                if potential and len(potential) > 1:
                    occupation = potential.upper()
            elif i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and len(next_line) > 1:
                    occupation = next_line.upper()
    
    # ===== Build output dictionary =====
    
    # Construct full name from parts if available
    if first_name or middle_name or surname:
        name_parts = []
        if first_name:
            name_parts.append(first_name)
            info['first_name'] = first_name
        if middle_name:
            name_parts.append(middle_name)
            info['middle_name'] = middle_name
        if surname:
            name_parts.append(surname)
            info['surname'] = surname
        
        # Create combined name
        if name_parts:
            info['name'] = ' '.join(name_parts)
    elif full_name:
        info['name'] = full_name
        # Try to split full name into parts
        name_words = full_name.split()
        if len(name_words) >= 3:
            info['first_name'] = name_words[0]
            info['middle_name'] = ' '.join(name_words[1:-1])
            info['surname'] = name_words[-1]
        elif len(name_words) == 2:
            info['first_name'] = name_words[0]
            info['surname'] = name_words[1]
        elif len(name_words) == 1:
            info['first_name'] = name_words[0]
    
    if father_name:
        info['father_name'] = father_name
    
    if mother_name:
        info['mother_name'] = mother_name
    
    if dob:
        info['date_of_birth'] = dob
    
    if age:
        info['age'] = age
    
    if gender:
        info['gender'] = gender
    
    # Build address
    if address_parts:
        full_address = ', '.join(address_parts)
        info['address'] = full_address
    
    if city:
        info['city'] = city
    
    if state:
        info['state'] = state
    
    if pin_code:
        info['pin_code'] = pin_code
    
    if mobile:
        info['mobile'] = mobile
    
    if email:
        info['email'] = email
    
    if occupation:
        info['occupation'] = occupation
    
    # Set document type indicator
    info['document_type'] = 'Handwritten Form'
    
    return info


# ==================== MAIN EXTRACTION FUNCTION ====================

def extract_document_info(text: str, doc_type: str) -> Dict[str, Optional[str]]:
    """
    Extract structured information from document text.
    
    Args:
        text: OCR extracted text
        doc_type: Document type (AADHAAR, PAN, VOTER_ID, etc.)
    
    Returns:
        Dictionary with extracted fields
    """
    # Clean and split text into lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Route to appropriate extractor
    if doc_type == "AADHAAR":
        return extract_aadhaar(text, lines)
    elif doc_type == "PAN":
        return extract_pan(text, lines)
    elif doc_type == "VOTER_ID":
        return extract_voter_id(text, lines)
    elif doc_type == "DRIVING_LICENSE":
        return extract_driving_license(text, lines)
    elif doc_type == "HANDWRITTEN":
        return extract_handwritten(text, lines)
    else:
        # Generic extraction for other document types
        info = {}
        text_clean = clean_text_for_matching(text)
        
        # Try to find any ID patterns
        pan_match = PAN_PATTERN.search(text.upper())
        if pan_match:
            info['document_id'] = pan_match.group(1)
        
        aadhaar_match = AADHAAR_PATTERN.search(text_clean)
        if aadhaar_match:
            info['document_id'] = aadhaar_match.group(1).replace(' ', '')
        
        voter_id_match = VOTER_ID_PATTERN.search(text.upper())
        if voter_id_match:
            info['document_id'] = voter_id_match.group(1)
        
        dl_match = DRIVING_LICENSE_PATTERN.search(text.upper())
        if dl_match:
            info['document_id'] = dl_match.group(1).replace(' ', '')
        
        # Find dates
        date = extract_date(text_clean)
        if date:
            info['date_of_birth'] = date
        
        return info
