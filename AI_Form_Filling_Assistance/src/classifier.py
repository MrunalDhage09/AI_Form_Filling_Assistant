"""
Document classifier for Indian government documents.
Identifies document type based on keywords and patterns.
"""

import re
from typing import Tuple

# Document type keywords
AADHAAR_KEYWORDS = [
    'aadhaar', 'आधार', 'uidai', 'unique identification',
    'enrolment no', 'enrollment no', 'your aadhaar no',
    'आपला आधार', 'भारतीय विशिष्ट', 'vtc:', 'pin code',
    'vid', 'नोंदणी क्रमांक', 'माझे आधार', 'मार्जी ओळख',
    'generation date', 'download date'
]

PAN_KEYWORDS = [
    'permanent account number', 'income tax department',
    'आयकर विभाग', 'pan card', 'govt. of india',
    "father's name", 'पिता का नाम'
]

VOTER_ID_KEYWORDS = [
    'election commission', 'voter', 'elector', 'epic',
    'निर्वाचन', 'मतदाता', 'elector photo identity',
    'भारत निर्वाचन आयोग', 'फोटो पहचान पत्र'
]

DRIVING_LICENSE_KEYWORDS = [
    'driving licence', 'driving license', 'transport',
    'motor vehicle', 'dl no', 'licence no', 'dl_no',
    'valid till', 'class of vehicle', 'authorisation to drive',
    'issuing authority', 'state motor', 'rto', 'mcwg', 'lmv',
    'tal:', 'dist:', 'dld', 'form 7'
]

# Handwritten form keywords - looking for common form field labels
HANDWRITTEN_KEYWORDS = [
    'first name', 'middle name', 'surname', 'last name',
    'father name', "father's name", 'mother name', "mother's name",
    'date of birth', 'dob', 'd.o.b', 'birth date',
    'address', 'city', 'state', 'pin code', 'pincode', 'postal code',
    'gender', 'sex', 'male', 'female',
    'mobile', 'phone', 'contact', 'email',
    'signature', 'applicant', 'full name',
    'age', 'occupation', 'qualification', 'education',
    'marital status', 'nationality', 'religion',
    'blood group', 'place of birth'
]


# Patterns for document IDs (strict formats)
# PAN: 10 characters (5 letters + 4 digits + 1 letter)
PAN_PATTERN = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
# Aadhaar: 12 digits
AADHAAR_PATTERN = re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b')
# Voter ID: 10 characters (3 letters + 7 digits)
VOTER_ID_PATTERN = re.compile(r'\b[A-Z]{3}[0-9]{7}\b')
# Driving License: State code (2 letters) + RTO code (2 digits) + Year/Number
DL_PATTERN = re.compile(r'\b[A-Z]{2}\s*\d{2}\s*\d{8,11}\b')


def classify_document(text: str) -> Tuple[str, float]:
    """
    Classify the document type based on text content.
    
    Args:
        text: OCR extracted text
        
    Returns:
        Tuple of (document_type, confidence_score)
    """
    text_lower = text.lower()
    
    # Count keyword matches for each document type
    scores = {
        'AADHAAR': 0,
        'PAN': 0,
        'VOTER_ID': 0,
        'DRIVING_LICENSE': 0,
        'HANDWRITTEN': 0
    }
    
    # Check keywords
    for keyword in AADHAAR_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['AADHAAR'] += 1
    
    for keyword in PAN_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['PAN'] += 1
    
    for keyword in VOTER_ID_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['VOTER_ID'] += 1
    
    for keyword in DRIVING_LICENSE_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['DRIVING_LICENSE'] += 1
    
    for keyword in HANDWRITTEN_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['HANDWRITTEN'] += 1
    
    # Check for specific patterns (adds more weight)
    if PAN_PATTERN.search(text.upper()):
        scores['PAN'] += 3
    
    if AADHAAR_PATTERN.search(text):
        scores['AADHAAR'] += 2
    
    if VOTER_ID_PATTERN.search(text.upper()):
        scores['VOTER_ID'] += 3
    
    # Check for DL pattern (MH12, KA01, DL14 etc followed by numbers)
    if DL_PATTERN.search(text.upper().replace(' ', '')):
        scores['DRIVING_LICENSE'] += 3
    
    # For handwritten forms, boost score if multiple form-like field labels found
    # But penalize if official document patterns are found
    if scores['HANDWRITTEN'] >= 3:
        # Check if this looks like an official document (has strong ID patterns)
        has_official_id = (
            PAN_PATTERN.search(text.upper()) or 
            AADHAAR_PATTERN.search(text) or 
            VOTER_ID_PATTERN.search(text.upper()) or
            DL_PATTERN.search(text.upper().replace(' ', ''))
        )
        if not has_official_id:
            scores['HANDWRITTEN'] += 2  # Boost handwritten if no official IDs found
        else:
            scores['HANDWRITTEN'] -= 2  # Penalize if official ID patterns exist
    
    # Find the highest score
    max_score = max(scores.values())
    
    if max_score == 0:
        return 'UNKNOWN', 0.0
    
    # Get document type with highest score
    doc_type = max(scores, key=scores.get)
    
    # Calculate confidence (normalized)
    # Max possible score varies by document type
    max_possible = {
        'AADHAAR': len(AADHAAR_KEYWORDS) + 2,
        'PAN': len(PAN_KEYWORDS) + 3,
        'VOTER_ID': len(VOTER_ID_KEYWORDS) + 3,
        'DRIVING_LICENSE': len(DRIVING_LICENSE_KEYWORDS) + 3,
        'HANDWRITTEN': len(HANDWRITTEN_KEYWORDS) + 2
    }
    
    confidence = min(max_score / max_possible.get(doc_type, 5), 1.0)
    
    return doc_type, confidence
