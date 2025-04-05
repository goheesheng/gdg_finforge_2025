import os
import io
import pytesseract
from PIL import Image
import pdfplumber
import aiofiles
from typing import Optional, List, Union
from pathlib import Path
import logging

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
    """Extract text from a PDF file using pdfplumber"""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
    return text

async def extract_text_from_image_tesseract(file_path: Union[str, Path]) -> str:
    """Extract text from an image using Tesseract OCR"""
    try:
        return pytesseract.image_to_string(Image.open(file_path))
    except Exception as e:
        logger.error(f"Error with Tesseract OCR: {e}")
        return ""

async def extract_text_from_image_google_vision(file_path: Union[str, Path]) -> str:
    """Extract text from an image using Google Vision API"""
    if not USE_GOOGLE_VISION:
        return await extract_text_from_image_tesseract(file_path)
    
    try:
        async with aiofiles.open(file_path, 'rb') as image_file:
            content = await image_file.read()
        
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations
        
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
