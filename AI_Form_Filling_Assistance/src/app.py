"""
Government Document Analyzer - Flask Application
Uses EasyOCR (free, open-source) for text extraction.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from flask import Flask, request, render_template, send_file, jsonify
import traceback
from werkzeug.utils import secure_filename

# Fix import paths for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))

try:
    from ocr import ocr_image, ocr_pdf
    from classifier import classify_document
    from extractor import extract_document_info
except ImportError:
    from .ocr import ocr_image, ocr_pdf
    from .classifier import classify_document
    from .extractor import extract_document_info


# -------------------- CONFIG --------------------

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
PROCESSING_TIMEOUT = 30  # seconds

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))


# -------------------- HELPERS --------------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def process_document(file_path: str, filename: str):
    """
    Process document: OCR -> Classify -> Extract.
    This function runs in a thread with timeout.
    """
    # Perform OCR
    print(f"Processing: {filename}")
    if filename.lower().endswith(".pdf"):
        extracted_text = ocr_pdf(file_path)
    else:
        extracted_text = ocr_image(file_path)
    
    print(f"OCR completed, text length: {len(extracted_text)}")
    
    # Classify document type
    doc_type, confidence = classify_document(extracted_text)
    print(f"Classified as: {doc_type} (confidence: {confidence:.2f})")
    
    # Extract information
    extracted_info = extract_document_info(extracted_text, doc_type)
    print(f"Extracted fields: {list(extracted_info.keys())}")
    
    return {
        "extracted_text": extracted_text,
        "doc_type": doc_type,
        "confidence": confidence,
        "extracted_info": extracted_info
    }


# -------------------- ROUTES --------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze_document():
    """Analyze uploaded document using EasyOCR with 30s timeout."""
    file = request.files.get("document")
    
    if not file or file.filename == '':
        return render_template("error.html", message="No file uploaded"), 400
    
    if not allowed_file(file.filename):
        return render_template("error.html", 
                             message=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        file_path = UPLOAD_DIR / unique_filename
        file.save(file_path)
        
        # Process document with timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(process_document, str(file_path), filename)
            try:
                processing_result = future.result(timeout=PROCESSING_TIMEOUT)
            except FuturesTimeoutError:
                return render_template("error.html", 
                    message=f"Document processing timed out after {PROCESSING_TIMEOUT} seconds. Please try with a clearer or smaller image."), 408
        
        # Prepare result
        result = {
            "filename": filename,
            "upload_timestamp": timestamp,
            "document_type": processing_result["doc_type"],
            "classification_confidence": round(processing_result["confidence"], 2),
            "extraction_method": "easyocr",
            "extracted_text": processing_result["extracted_text"][:3000] if len(processing_result["extracted_text"]) > 3000 else processing_result["extracted_text"],
            "extracted_fields": processing_result["extracted_info"],
            "status": "success"
        }
        
        # Save result
        output_json = UPLOAD_DIR / f"{timestamp}_result.json"
        output_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        
        return render_template("result.html", result=result)
        
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Error: {e}\n{tb}")
        try:
            (UPLOAD_DIR / 'error.log').write_text(tb, encoding='utf-8')
        except:
            pass
        return render_template('error.html', message=f"Error: {str(e)}"), 500


@app.route("/export/json")
def export_json():
    """Export latest result as JSON."""
    result_files = sorted(UPLOAD_DIR.glob("*_result.json"), reverse=True)
    
    if not result_files:
        return jsonify({"error": "No results found"}), 404
    
    return send_file(str(result_files[0]), as_attachment=True, download_name="document_analysis.json")


@app.route("/history")
def history():
    """View analysis history."""
    result_files = sorted(UPLOAD_DIR.glob("*_result.json"), reverse=True)
    
    history_items = []
    for result_file in result_files[:10]:
        try:
            data = json.loads(result_file.read_text(encoding='utf-8'))
            history_items.append({
                "filename": data.get("filename", "Unknown"),
                "timestamp": data.get("upload_timestamp", ""),
                "doc_type": data.get("document_type", "Unknown"),
                "confidence": data.get("classification_confidence", 0),
                "result_file": result_file.name
            })
        except:
            continue
    
    return render_template("history.html", history=history_items)


@app.route("/view/<result_filename>")
def view_result(result_filename):
    """View specific result from history."""
    result_path = UPLOAD_DIR / secure_filename(result_filename)
    
    if not result_path.exists() or not result_filename.endswith("_result.json"):
        return render_template("error.html", message="Result not found"), 404
    
    try:
        result = json.loads(result_path.read_text(encoding='utf-8'))
        return render_template("result.html", result=result)
    except Exception as e:
        return render_template("error.html", message=f"Error: {str(e)}"), 500


@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    try:
        (UPLOAD_DIR / 'error.log').write_text(tb, encoding='utf-8')
    except:
        pass
    return render_template('error.html', message=str(e)), 500


# -------------------- MAIN --------------------

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Government Document Analyzer")
    print("  Using EasyOCR (Free & Open Source)")
    print(f"  Processing timeout: {PROCESSING_TIMEOUT} seconds")
    print("="*60)
    print("\n📝 First run may take a minute to download OCR models...")
    print("🌐 Server starting at http://localhost:5000\n")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
