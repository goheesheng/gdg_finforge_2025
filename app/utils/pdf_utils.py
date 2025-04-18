import os
import logging
import aiofiles
from pathlib import Path
from typing import Optional, List, Union, BinaryIO
import aiohttp
from PIL import Image, ImageEnhance, ImageFilter
import io
import numpy as np

from app.config.config import TEMP_DOWNLOAD_PATH, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

async def download_file(file_url: str, output_dir: Path = TEMP_DOWNLOAD_PATH) -> Optional[Path]:
    """Download a file from a URL and save it to the output directory"""
    try:
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate a unique filename
        file_name = os.path.basename(file_url)
        if not file_name:
            file_name = f"download_{hash(file_url)}"
            
        output_path = output_dir / file_name
        
        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to download file from {file_url}: {response.status}")
                    return None
                    
                # Check file size
                content_length = response.content_length
                if content_length and content_length > MAX_FILE_SIZE_MB * 1024 * 1024:
                    logger.warning(f"File too large: {content_length / (1024 * 1024):.2f} MB, max: {MAX_FILE_SIZE_MB} MB")
                    return None
                
                # Save the file
                async with aiofiles.open(output_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024):
                        await f.write(chunk)
                        
        return output_path
    except Exception as e:
        logger.error(f"Error downloading file from {file_url}: {e}")
        return None

async def save_telegram_file(file_obj: BinaryIO, file_name: str, output_dir: Path = TEMP_DOWNLOAD_PATH) -> Optional[Path]:
    """Save a file received from Telegram to the output directory"""
    try:
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate file path
        output_path = output_dir / file_name
        
        # Save the file
        async with aiofiles.open(output_path, 'wb') as f:
            await f.write(file_obj.read())
            
        return output_path
    except Exception as e:
        logger.error(f"Error saving Telegram file {file_name}: {e}")
        return None

async def get_file_type(file_path: Union[str, Path]) -> str:
    """Determine the file type (PDF, image, etc.)"""
    file_path = Path(file_path)
    file_extension = file_path.suffix.lower()
    
    if file_extension == '.pdf':
        return 'application/pdf'
    elif file_extension in ['.jpg', '.jpeg']:
        return 'image/jpeg'
    elif file_extension == '.png':
        return 'image/png'
    elif file_extension in ['.tif', '.tiff']:
        return 'image/tiff'
    elif file_extension == '.bmp':
        return 'image/bmp'
    else:
        # Try to determine type from content
        try:
            img = Image.open(file_path)
            return f'image/{img.format.lower()}'
        except:
            return 'application/octet-stream'

async def preprocess_image_for_ocr(image_path: Union[str, Path]) -> Optional[Path]:
    """
    Preprocess an image to improve OCR results.
    
    This function applies several enhancements to the image:
    1. Resize if too large
    2. Convert to grayscale
    3. Increase contrast
    4. Apply adaptive thresholding
    5. Reduce noise
    
    Returns the path to the processed image.
    """
    try:
        image_path = Path(image_path)
        output_path = image_path.parent / f"processed_{image_path.name}"
        
        # Open the image
        img = Image.open(image_path)
        
        # Resize if too large
        max_size = 2000  # Maximum dimension
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # Convert to grayscale
        if img.mode != 'L':
            img = img.convert('L')
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)  # Adjust contrast factor as needed
        
        # Apply light sharpening
        img = img.filter(ImageFilter.SHARPEN)
        
        # Apply a small blur to reduce noise
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        # Save the processed image
        img.save(output_path)
        
        return output_path
    except Exception as e:
        logger.error(f"Error preprocessing image: {e}")
        return None

async def cleanup_temp_files(file_paths: List[Path]) -> None:
    """Clean up temporary files"""
    for file_path in file_paths:
        try:
            os.remove(file_path)
            logger.info(f"Deleted temporary file: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting temporary file {file_path}: {e}")
