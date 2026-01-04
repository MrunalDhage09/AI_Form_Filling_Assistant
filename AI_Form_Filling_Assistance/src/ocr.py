"""
OCR module using EasyOCR (free, open-source).
Supports English and Hindi for Indian government documents.
"""

import os
from pathlib import Path
from typing import List, Tuple
from PIL import Image

# Lazy load EasyOCR to speed up imports
_reader = None

def get_reader():
    """Get or create EasyOCR reader (lazy loading)."""
    global _reader
    if _reader is None:
        import easyocr
        # Support English and Hindi for Indian documents
        _reader = easyocr.Reader(['en', 'hi'], gpu=False, verbose=False)
    return _reader


def ocr_image(image_path: str) -> str:
    """
    Extract text from an image using EasyOCR.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Extracted text as a string
    """
    try:
        reader = get_reader()
        results = reader.readtext(image_path, detail=1, paragraph=False)
        
        # Sort results by vertical position (top to bottom), then horizontal (left to right)
        # This helps maintain reading order
        sorted_results = sorted(results, key=lambda x: (x[0][0][1], x[0][0][0]))
        
        # Group text by approximate lines (within 20 pixels vertically)
        lines = []
        current_line = []
        current_y = None
        
        for result in sorted_results:
            bbox, text, conf = result
            y_pos = bbox[0][1]  # Top-left Y coordinate
            
            if current_y is None:
                current_y = y_pos
                current_line = [(bbox[0][0], text)]  # (x_pos, text)
            elif abs(y_pos - current_y) < 20:  # Same line
                current_line.append((bbox[0][0], text))
            else:  # New line
                # Sort current line by x position and join
                current_line.sort(key=lambda x: x[0])
                lines.append(' '.join([t[1] for t in current_line]))
                current_line = [(bbox[0][0], text)]
                current_y = y_pos
        
        # Don't forget the last line
        if current_line:
            current_line.sort(key=lambda x: x[0])
            lines.append(' '.join([t[1] for t in current_line]))
        
        return '\n'.join(lines)
        
    except Exception as e:
        print(f"EasyOCR error: {e}")
        return ""


def ocr_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text from all pages
    """
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        all_text = []
        
        for page_num, page in enumerate(doc):
            # First try to extract embedded text
            text = page.get_text()
            
            if text.strip():
                all_text.append(text)
            else:
                # If no embedded text, render as image and OCR
                pix = page.get_pixmap(dpi=200)
                img_path = f"{pdf_path}_page_{page_num}.png"
                pix.save(img_path)
                
                # OCR the image
                page_text = ocr_image(img_path)
                all_text.append(page_text)
                
                # Clean up temp image
                try:
                    os.remove(img_path)
                except:
                    pass
        
        doc.close()
        return '\n\n'.join(all_text)
        
    except Exception as e:
        print(f"PDF OCR error: {e}")
        return ""


def ocr_with_positions(image_path: str) -> List[Tuple[str, Tuple[int, int, int, int], float]]:
    """
    Extract text with bounding box positions.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of (text, (x1, y1, x2, y2), confidence) tuples
    """
    try:
        reader = get_reader()
        results = reader.readtext(image_path, detail=1)
        
        extracted = []
        for bbox, text, conf in results:
            # Convert bbox to (x1, y1, x2, y2)
            x1 = min(p[0] for p in bbox)
            y1 = min(p[1] for p in bbox)
            x2 = max(p[0] for p in bbox)
            y2 = max(p[1] for p in bbox)
            extracted.append((text, (int(x1), int(y1), int(x2), int(y2)), conf))
        
        return extracted
        
    except Exception as e:
        print(f"OCR with positions error: {e}")
        return []
