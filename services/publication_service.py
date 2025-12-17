"""
Publication Service
Business logic for publication management and PDF processing
"""

import io
from typing import Optional
import PyPDF2
import pdfplumber


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        file_bytes: PDF file as bytes
        
    Returns:
        Extracted text as a string. Empty string if extraction fails.
    """
    text_content = []
    
    # Try with pdfplumber first (better for complex layouts)
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)
        
        if text_content:
            return "\n\n".join(text_content)
    except Exception as e:
        print(f"pdfplumber extraction failed: {e}")
    
    # Fallback to PyPDF2
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)
        
        return "\n\n".join(text_content)
    except Exception as e:
        print(f"PyPDF2 extraction failed: {e}")
        return ""


def validate_pdf_file(filename: str, content: bytes) -> tuple[bool, Optional[str]]:
    """
    Validate that a file is a proper PDF.
    
    Args:
        filename: Name of the file
        content: File content as bytes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check extension
    if not filename.lower().endswith('.pdf'):
        return False, "El archivo debe ser un PDF (.pdf)"
    
    # Check PDF magic number
    if not content.startswith(b'%PDF'):
        return False, "El archivo no es un PDF válido"
    
    # Check minimum size (avoid empty files)
    if len(content) < 100:
        return False, "El archivo PDF está vacío o corrupto"
    
    return True, None
