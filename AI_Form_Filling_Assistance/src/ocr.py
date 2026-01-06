"""
OCR module using EasyOCR (free, open-source).
Supports English and Hindi for Indian government documents.
Enhanced PDF support with image preprocessing.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageEnhance, ImageFilter

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


def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    """
    Preprocess image to improve OCR accuracy.
    
    Args:
        image: PIL Image object
        
    Returns:
        Preprocessed PIL Image
    """
    # Convert to RGB if needed
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Resize if image is too small (improves OCR accuracy)
    min_dimension = 1000
    width, height = image.size
    if width < min_dimension or height < min_dimension:
        scale = max(min_dimension / width, min_dimension / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.3)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.5)
    
    # Slight brightness adjustment
    enhancer = ImageEnhance.Brightness(image)
    image = enhancer.enhance(1.1)
    
    return image


def ocr_image(image_path: str, preprocess: bool = True) -> str:
    """
    Extract text from an image using EasyOCR.
    
    Args:
        image_path: Path to the image file
        preprocess: Whether to apply image preprocessing for better OCR
        
    Returns:
        Extracted text as a string
    """
    try:
        reader = get_reader()
        
        # Optionally preprocess the image
        if preprocess:
            try:
                img = Image.open(image_path)
                img = preprocess_image_for_ocr(img)
                # Save preprocessed image to temp file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    img.save(tmp.name, 'PNG')
                    temp_path = tmp.name
                results = reader.readtext(temp_path, detail=1, paragraph=False)
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except:
                    pass
            except Exception as prep_err:
                print(f"Preprocessing failed, using original: {prep_err}")
                results = reader.readtext(image_path, detail=1, paragraph=False)
        else:
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


def ocr_pil_image(image: Image.Image) -> str:
    """
    Extract text from a PIL Image object using EasyOCR.
    
    Args:
        image: PIL Image object
        
    Returns:
        Extracted text as a string
    """
    try:
        # Preprocess the image
        image = preprocess_image_for_ocr(image)
        
        # Save to temp file for EasyOCR
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            image.save(tmp.name, 'PNG')
            temp_path = tmp.name
        
        # Perform OCR (skip preprocessing since we already did it)
        text = ocr_image(temp_path, preprocess=False)
        
        # Clean up
        try:
            os.remove(temp_path)
        except:
            pass
        
        return text
        
    except Exception as e:
        print(f"PIL OCR error: {e}")
        return ""


def ocr_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file with comprehensive support for:
    - Text-based PDFs (embedded text extraction)
    - Scanned/Image PDFs (OCR)
    - Mixed PDFs (both embedded text and images)
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text from all pages
    """
    all_text = []
    
    # Try PyMuPDF first (faster and more reliable)
    try:
        all_text = _ocr_pdf_pymupdf(pdf_path)
        if all_text:
            return '\n\n'.join(all_text)
    except Exception as e:
        print(f"PyMuPDF failed: {e}")
    
    # Fallback to pdf2image + OCR
    try:
        all_text = _ocr_pdf_pdf2image(pdf_path)
        if all_text:
            return '\n\n'.join(all_text)
    except Exception as e:
        print(f"pdf2image fallback failed: {e}")
    
    return ""


def _ocr_pdf_pymupdf(pdf_path: str) -> List[str]:
    """
    Extract text from PDF using PyMuPDF with OCR fallback for scanned pages.
    """
    import fitz  # PyMuPDF
    
    doc = fitz.open(pdf_path)
    all_text = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = ""
        
        # First try to extract embedded text
        embedded_text = page.get_text().strip()
        
        # Check if embedded text is meaningful (more than just whitespace/numbers)
        has_meaningful_text = False
        if embedded_text:
            # Count alphabetic characters
            alpha_count = sum(1 for c in embedded_text if c.isalpha())
            has_meaningful_text = alpha_count > 20  # At least 20 letters
        
        if has_meaningful_text:
            page_text = embedded_text
            print(f"Page {page_num + 1}: Extracted embedded text ({len(embedded_text)} chars)")
        else:
            # No meaningful embedded text - this is likely a scanned page
            # Render page as high-resolution image and OCR
            print(f"Page {page_num + 1}: Scanned page detected, performing OCR...")
            
            # Use high DPI for better OCR accuracy (300 DPI is standard for documents)
            mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Perform OCR on the image
            page_text = ocr_pil_image(img)
            print(f"Page {page_num + 1}: OCR extracted ({len(page_text)} chars)")
        
        if page_text:
            all_text.append(page_text)
    
    doc.close()
    return all_text


def _ocr_pdf_pdf2image(pdf_path: str) -> List[str]:
    """
    Fallback PDF extraction using pdf2image (requires poppler).
    This is useful when PyMuPDF fails or for complex PDFs.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        print("pdf2image not available for fallback")
        return []
    
    all_text = []
    
    try:
        # Convert PDF pages to images at 300 DPI
        images = convert_from_path(pdf_path, dpi=300)
        
        for page_num, image in enumerate(images):
            print(f"Page {page_num + 1}: Processing with pdf2image...")
            
            # Perform OCR on the image
            page_text = ocr_pil_image(image)
            
            if page_text:
                all_text.append(page_text)
                print(f"Page {page_num + 1}: Extracted ({len(page_text)} chars)")
        
        return all_text
        
    except Exception as e:
        print(f"pdf2image conversion error: {e}")
        return []


def is_scanned_pdf(pdf_path: str) -> bool:
    """
    Check if a PDF is scanned (image-based) or has embedded text.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        True if PDF appears to be scanned/image-based
    """
    try:
        import fitz
        
        doc = fitz.open(pdf_path)
        total_text_length = 0
        
        # Check first few pages
        for page_num in range(min(3, len(doc))):
            page = doc[page_num]
            text = page.get_text().strip()
            total_text_length += len(text)
        
        doc.close()
        
        # If very little text, it's likely scanned
        return total_text_length < 100
        
    except:
        return True  # Assume scanned if we can't check


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
        
        # Preprocess image for better OCR
        try:
            img = Image.open(image_path)
            img = preprocess_image_for_ocr(img)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                img.save(tmp.name, 'PNG')
                temp_path = tmp.name
            results = reader.readtext(temp_path, detail=1)
            try:
                os.remove(temp_path)
            except:
                pass
        except:
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
