"""
Document information extractor optimized for Indian government documents.
Patterns based on actual document samples:
- Aadhaar Card (UIDAI format - both physical and e-Aadhaar)
- PAN Card (Income Tax Department)
- Passport (Republic of India)
- Voter ID (Election Commission)
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

# Passport: exactly 8 characters (1 letter + 7 digits, e.g., Z0000000)
PASSPORT_PATTERN = re.compile(r'\b([A-Z][0-9]{7})\b')

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
                            name = potential_name.upper()
                            break
            
            # Extract Hindi name from the line
            hindi_part = extract_hindi_only(line)
            if hindi_part and looks_like_hindi_name(hindi_part) and not name_hindi:
                skip_hindi = ['नाम', 'आयकर', 'विभाग', 'भारत', 'सरकार', 'स्थायी', 'लेखा', 'संख्या', 'कार्ड']
                cleaned_hindi = ' '.join(w for w in hindi_part.split() if w not in skip_hindi)
                if cleaned_hindi and len(cleaned_hindi) > 2:
                    name_hindi = cleaned_hindi
            
            # If not found inline, check next line
            if not name and i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and looks_like_name(next_line):
                    if 'father' not in next_line.lower():
                        name = next_line.upper()
        
        # Look for Father's Name - multiple patterns
        # Handle: "पिता APPLICANTS FATHER NAME का नाम Father's Name" 
        # or "Father's Name: VALUE"
        elif ('father' in line_lower or 'पिता' in line):
            # Extract all English words that could be the name
            # The actual father's name usually comes BEFORE "का नाम" or "Father's Name" label
            
            # Pattern 1: Value before the Hindi label "का नाम" or "का नामः"
            before_hindi_match = re.search(r'(?:पिता|father)[\'s]*\s+([A-Z][A-Z\s]+?)(?:\s*का\s*नाम[ः:]?|father|$)', line, re.IGNORECASE)
            if before_hindi_match:
                potential = before_hindi_match.group(1).strip()
                if potential and len(potential) > 2:
                    # Clean up - remove trailing "S" from "Father's" if captured
                    potential = re.sub(r"^'?S\s+", '', potential)
                    if looks_like_name(potential):
                        father_name = potential.upper()
            
            # Pattern 2: Standard "Father's Name: VALUE" format
            if not father_name:
                father_patterns = [
                    r"father'?s?\s*name\s*[:/]?\s*([A-Z][A-Z\s]+)",
                ]
                for pattern in father_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        potential = match.group(1).strip()
                        if potential and len(potential) > 2:
                            if not any(x in potential.lower() for x in ['signature', 'card', 'date', 'birth']):
                                father_name = potential.upper()
                                break
            
            # Extract Hindi father's name
            hindi_part = extract_hindi_only(line)
            if hindi_part and not father_name_hindi:
                skip_hindi = ['पिता', 'का', 'नाम', 'भारत', 'सरकार']
                cleaned_hindi = ' '.join(w for w in hindi_part.split() if w not in skip_hindi)
                if cleaned_hindi and looks_like_hindi_name(cleaned_hindi):
                    father_name_hindi = cleaned_hindi
            
            # Pattern 3: If we see the label, check next line
            if not father_name and i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and looks_like_name(next_line):
                    if 'date' not in next_line.lower() and 'birth' not in next_line.lower():
                        father_name = next_line.upper()
        
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


# ==================== PASSPORT EXTRACTION ====================

def extract_passport(text: str, lines: List[str]) -> Dict[str, Optional[str]]:
    """
    Extract information from Indian Passport.
    
    Sample format:
    - Type: P, Code: IND, Nationality: INDIAN
    - Passport No.: Z0000000
    - Surname: SPECIMEN
    - Given Name: KUMAR G
    - DOB: 24/05/1985, Sex: M
    - Place of Birth, Place of Issue
    - Date of Issue, Date of Expiry
    - MRZ at bottom
    """
    info = {}
    text_upper = text.upper()
    text_clean = clean_text_for_matching(text)
    
    # Extract Passport Number
    passport_match = PASSPORT_PATTERN.search(text_upper)
    if passport_match:
        info['document_id'] = passport_match.group(1)
        info['passport_number'] = passport_match.group(1)
    
    # Try to extract from MRZ (Machine Readable Zone)
    mrz_pattern = re.compile(r'P<<([A-Z]+)<<([A-Z\s]+)<+')
    mrz_match = mrz_pattern.search(text_upper)
    if mrz_match:
        surname = mrz_match.group(1).replace('<', ' ').strip()
        given_name = mrz_match.group(2).replace('<', ' ').strip()
        info['name'] = f"{given_name} {surname}".strip()
        info['surname'] = surname
        info['given_name'] = given_name
    
    # Extract fields from text
    surname = None
    given_name = None
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        line_clean = clean_text_for_matching(line)
        
        # Passport Number
        if 'passport no' in line_lower:
            match = PASSPORT_PATTERN.search(line.upper())
            if match:
                info['document_id'] = match.group(1)
                info['passport_number'] = match.group(1)
        
        # Surname
        elif 'surname' in line_lower:
            # Try inline extraction first
            surname_match = re.search(r'surname\s*[:/]?\s*([A-Z][A-Z\s]*)', line, re.IGNORECASE)
            if surname_match:
                surname = surname_match.group(1).strip().upper()
            elif i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and looks_like_name(next_line):
                    surname = next_line.upper()
        
        # Given Name
        elif 'given name' in line_lower:
            given_match = re.search(r'given\s*name[s]?\s*[:/]?\s*([A-Z][A-Z\s]*)', line, re.IGNORECASE)
            if given_match:
                given_name = given_match.group(1).strip().upper()
            elif i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line and looks_like_name(next_line):
                    given_name = next_line.upper()
        
        # Date of Birth
        elif 'date of birth' in line_lower or '/date of birth' in line_lower:
            date = extract_date(line_clean)
            if date:
                info['date_of_birth'] = date
        
        # Sex/Gender
        elif 'sex' in line_lower:
            sex_match = re.search(r'\b([MF])\b', line.upper())
            if sex_match:
                info['gender'] = 'Male' if sex_match.group(1) == 'M' else 'Female'
        
        # Place of Birth
        elif 'place of birth' in line_lower:
            pob_match = re.search(r'place\s*of\s*birth\s*[:/]?\s*([A-Z][A-Z\s,]+)', line, re.IGNORECASE)
            if pob_match:
                info['place_of_birth'] = pob_match.group(1).strip().upper()
            elif i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line:
                    info['place_of_birth'] = next_line.upper()
        
        # Place of Issue
        elif 'place of issue' in line_lower:
            poi_match = re.search(r'place\s*of\s*issue\s*[:/]?\s*([A-Z][A-Z\s,]+)', line, re.IGNORECASE)
            if poi_match:
                info['place_of_issue'] = poi_match.group(1).strip().upper()
            elif i + 1 < len(lines):
                next_line = extract_english_only(lines[i + 1]).strip()
                if next_line:
                    info['place_of_issue'] = next_line.upper()
        
        # Date of Issue
        elif 'date of issue' in line_lower:
            date = extract_date(line_clean)
            if date:
                info['date_of_issue'] = date
        
        # Date of Expiry
        elif 'date of expiry' in line_lower or 'expiry' in line_lower:
            date = extract_date(line_clean)
            if date:
                info['date_of_expiry'] = date
    
    # Build full name if not from MRZ
    if not info.get('name'):
        if surname and given_name:
            info['name'] = f"{given_name} {surname}"
        elif surname:
            info['name'] = surname
        elif given_name:
            info['name'] = given_name
    
    if surname:
        info['surname'] = surname
    if given_name:
        info['given_name'] = given_name
    
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


# ==================== MAIN EXTRACTION FUNCTION ====================

def extract_document_info(text: str, doc_type: str) -> Dict[str, Optional[str]]:
    """
    Extract structured information from document text.
    
    Args:
        text: OCR extracted text
        doc_type: Document type (AADHAAR, PAN, PASSPORT, etc.)
    
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
    elif doc_type == "PASSPORT":
        return extract_passport(text, lines)
    elif doc_type == "VOTER_ID":
        return extract_voter_id(text, lines)
    else:
        # Generic extraction for other document types
        info = {}
        text_clean = clean_text_for_matching(text)
        
        # Try to find any ID patterns
        pan_match = PAN_PATTERN.search(text.upper())
        if pan_match:
            info['document_id'] = pan_match.group(1)
        
        passport_match = PASSPORT_PATTERN.search(text.upper())
        if passport_match:
            info['document_id'] = passport_match.group(1)
        
        aadhaar_match = AADHAAR_PATTERN.search(text_clean)
        if aadhaar_match:
            info['document_id'] = aadhaar_match.group(1).replace(' ', '')
        
        # Find dates
        date = extract_date(text_clean)
        if date:
            info['date_of_birth'] = date
        
        return info
