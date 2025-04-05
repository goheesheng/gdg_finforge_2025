import os
import io
import pytesseract
from PIL import Image
import pdfplumber
import aiofiles
from typing import Optional, List, Union, Dict
from pathlib import Path
import logging
import re

from app.config.config import TESSERACT_CMD, USE_GOOGLE_VISION, GOOGLE_APPLICATION_CREDENTIALS

logger = logging.getLogger(__name__)

# Set Tesseract command path if configured
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Initialize Google Vision if enabled
if USE_GOOGLE_VISION:
    try:
        from google.cloud import vision
        from google.cloud.vision_v1 import types
        vision_client = vision.ImageAnnotatorClient()
    except ImportError:
        logger.warning("Google Vision library not available. Falling back to Tesseract.")
        USE_GOOGLE_VISION = False
    except Exception as e:
        logger.error(f"Failed to initialize Google Vision: {e}")
        USE_GOOGLE_VISION = False

async def extract_text_from_pdf(file_path: Union[str, Path]) -> str:
    """Extract text from a PDF file using pdfplumber with enhanced handling for tables and structure"""
    text = ""
    tables_data = []
    
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extract tables first to prevent duplicating content
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if table:
                            table_text = "\n".join([
                                " | ".join([str(cell) if cell else "" for cell in row])
                                for row in table
                            ])
                            tables_data.append(f"Table (Page {page_num + 1}):\n{table_text}\n")
                
                # Extract regular text
                page_text = page.extract_text() or ""
                text += page_text + "\n"
                
                # Try to extract form fields (useful for PDF forms)
                try:
                    if hasattr(page, 'annots') and page.annots:
                        for annot in page.annots:
                            if annot.get('subtype') == 'Widget':
                                field_value = annot.get('value', '')
                                field_name = annot.get('field_name', '')
                                if field_name and field_value:
                                    text += f"{field_name}: {field_value}\n"
                except Exception as e:
                    logger.warning(f"Error extracting form fields: {e}")
    
        # Append tables data to the end
        if tables_data:
            text += "\n\nEXTRACTED TABLES:\n" + "\n".join(tables_data)
            
        # Post-process to fix common OCR issues with insurance policies
        text = post_process_insurance_policy(text)
            
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
    
    return text

def post_process_insurance_policy(text: str) -> str:
    """Post-process extracted text to improve readability for insurance documents"""
    # Fix common OCR issues
    text = re.sub(r'(\d),(\d)', r'\1\2', text)  # Fix numbers with commas
    
    # Identify policy numbers using patterns
    policy_pattern = re.compile(r'([Pp]olicy\s*(?:#|[Nn]o|[Nn]umber)[:.]?\s*)([A-Z0-9-]{5,20})')
    text = policy_pattern.sub(r'Policy Number: \2', text)
    
    # Identify coverage amounts
    coverage_pattern = re.compile(r'(\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')
    text = coverage_pattern.sub(r'\1', text)
    
    # Identify dates in various formats
    date_pattern = re.compile(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})')
    text = date_pattern.sub(r'\1', text)
    
    # Make sure key policy sections are on new lines
    section_headers = [
        "Coverage Summary", "Policy Details", "Premium", "Exclusions", 
        "Limitations", "Benefits", "Deductible", "Co-payment", "Co-pay"
    ]
    for header in section_headers:
        text = re.sub(f'([^\n])({header})', r'\1\n\2', text, flags=re.IGNORECASE)
    
    return text

async def extract_text_from_image_tesseract(file_path: Union[str, Path]) -> str:
    """Extract text from an image using Tesseract OCR"""
    try:
        from app.utils import pdf_utils
        
        # Preprocess the image to improve OCR results
        processed_path = await pdf_utils.preprocess_image_for_ocr(file_path)
        if processed_path:
            # Use improved image for OCR
            result = pytesseract.image_to_string(Image.open(processed_path))
            
            # Clean up the processed image
            try:
                processed_path.unlink()
            except:
                pass
                
            return result
        else:
            # Fall back to original image if preprocessing fails
            return pytesseract.image_to_string(Image.open(file_path))
    except Exception as e:
        logger.error(f"Error with Tesseract OCR: {e}")
        return ""

async def extract_text_from_image_google_vision(file_path: Union[str, Path]) -> str:
    """Extract text from an image using Google Vision API"""
    if not USE_GOOGLE_VISION:
        return await extract_text_from_image_tesseract(file_path)
    
    try:
        from app.utils import pdf_utils
        
        # Preprocess the image to improve OCR results
        processed_path = await pdf_utils.preprocess_image_for_ocr(file_path)
        use_path = processed_path if processed_path else file_path
        
        async with aiofiles.open(use_path, 'rb') as image_file:
            content = await image_file.read()
        
        image = vision.Image(content=content)
        
        # Use text detection with language hints to improve accuracy
        # This is especially useful for documents with specialized terminology
        image_context = vision.ImageContext(
            language_hints=["en"]  # Adding more languages if needed: ["en", "fr", "es"]
        )
        
        response = vision_client.text_detection(image=image, image_context=image_context)
        texts = response.text_annotations
        
        # Clean up the processed image if it exists
        if processed_path:
            try:
                processed_path.unlink()
            except:
                pass
        
        if texts:
            return texts[0].description
        return ""
    except Exception as e:
        logger.error(f"Error with Google Vision OCR: {e}")
        # Fall back to Tesseract
        return await extract_text_from_image_tesseract(file_path)

async def extract_text_from_image(file_path: Union[str, Path]) -> str:
    """Extract text from an image using the preferred OCR method"""
    if USE_GOOGLE_VISION:
        return await extract_text_from_image_google_vision(file_path)
    else:
        return await extract_text_from_image_tesseract(file_path)

async def extract_text_from_file(file_path: Union[str, Path]) -> str:
    """Extract text from a file based on its type"""
    file_path = Path(file_path)
    file_extension = file_path.suffix.lower()
    
    if file_extension == '.pdf':
        return await extract_text_from_pdf(file_path)
    elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
        return await extract_text_from_image(file_path)
    else:
        logger.warning(f"Unsupported file type: {file_extension}")
        return ""
