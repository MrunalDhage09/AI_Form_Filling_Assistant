# Government Document Analyzer

Free, open-source document analysis for Indian government documents using **EasyOCR**.

## Features

- **100% Free** - No API keys or paid services required
- **EasyOCR** - Open-source OCR supporting English and Hindi
- **Supported Documents**: Aadhaar, PAN, Passport, Voter ID, Driving License
- **Extracted Fields**: Name, DOB, Document ID, Address, Gender, and more

## Quick Start

```bash
cd AI_Form_Filling_Assistance

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
cd src
python3 app.py
```

Open http://localhost:5000 in your browser.

**Note**: First run downloads OCR models (~100MB) - takes 1-2 minutes.

## Supported Documents

| Document | Extracted Fields |
|----------|-----------------|
| **Aadhaar** | Aadhaar Number, Name, DOB, Gender, Address, PIN Code, Enrollment No |
| **PAN** | PAN Number, Name, Father's Name, DOB |
| **Passport** | Passport Number, Name, DOB, Gender, Place of Birth/Issue, Issue/Expiry Dates |

## Project Structure

```
AI_Form_Filling_Assistance/
├── src/
│   ├── app.py         # Flask application
│   ├── ocr.py         # EasyOCR wrapper
│   ├── classifier.py  # Document type detection
│   ├── extractor.py   # Field extraction patterns
│   └── templates/     # HTML templates
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.7+
- ~500MB disk space (for OCR models)

## How It Works

1. **OCR**: EasyOCR extracts text from the document image
2. **Classification**: Keywords and patterns identify document type
3. **Extraction**: Regex patterns extract structured fields

## Tips for Best Results

- Use clear, well-lit images
- Ensure document fills most of the frame
- Avoid glare and shadows
- PDF scans work better than photos
