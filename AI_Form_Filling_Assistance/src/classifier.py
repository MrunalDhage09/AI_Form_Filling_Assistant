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

PASSPORT_KEYWORDS = [
    'passport', 'republic of india', 'भारत गणराज्य',
    'place of birth', 'place of issue', 'date of expiry',
    'nationality', 'surname', 'given name',
    'p<<', 'ind'  # MRZ markers
]

VOTER_ID_KEYWORDS = [
    'election commission', 'voter', 'elector', 'epic',
    'निर्वाचन', 'मतदाता', 'elector photo identity',
    'भारत निर्वाचन आयोग', 'फोटो पहचान पत्र'
]

DRIVING_LICENSE_KEYWORDS = [
    'driving licence', 'driving license', 'transport',
    'motor vehicle', 'dl no', 'licence no'
]


# Patterns for document IDs (strict formats)
# PAN: 10 characters (5 letters + 4 digits + 1 letter)
PAN_PATTERN = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
# Passport: 8 characters (1 letter + 7 digits)
PASSPORT_PATTERN = re.compile(r'\b[A-Z][0-9]{7}\b')
# Aadhaar: 12 digits
AADHAAR_PATTERN = re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b')
# Voter ID: 10 characters (3 letters + 7 digits)
VOTER_ID_PATTERN = re.compile(r'\b[A-Z]{3}[0-9]{7}\b')


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
        'PASSPORT': 0,
        'VOTER_ID': 0,
        'DRIVING_LICENSE': 0
    }
    
    # Check keywords
    for keyword in AADHAAR_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['AADHAAR'] += 1
    
    for keyword in PAN_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['PAN'] += 1
    
    for keyword in PASSPORT_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['PASSPORT'] += 1
    
    for keyword in VOTER_ID_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['VOTER_ID'] += 1
    
    for keyword in DRIVING_LICENSE_KEYWORDS:
        if keyword.lower() in text_lower:
            scores['DRIVING_LICENSE'] += 1
    
    # Check for specific patterns (adds more weight)
    if PAN_PATTERN.search(text.upper()):
        scores['PAN'] += 3
    
    if PASSPORT_PATTERN.search(text.upper()):
        scores['PASSPORT'] += 3
    
    if AADHAAR_PATTERN.search(text):
        scores['AADHAAR'] += 2
    
    if VOTER_ID_PATTERN.search(text.upper()):
        scores['VOTER_ID'] += 3
    
    # Check for MRZ (Machine Readable Zone) - strong passport indicator
    if 'P<<' in text.upper() or re.search(r'[A-Z]\d{7}<\dIND', text.upper()):
        scores['PASSPORT'] += 5
    
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
        'PASSPORT': len(PASSPORT_KEYWORDS) + 8,  # MRZ adds 5
        'VOTER_ID': len(VOTER_ID_KEYWORDS),
        'DRIVING_LICENSE': len(DRIVING_LICENSE_KEYWORDS)
    }
    
    confidence = min(max_score / max_possible.get(doc_type, 5), 1.0)
    
    return doc_type, confidence
