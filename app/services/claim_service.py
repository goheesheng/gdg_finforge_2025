import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from datetime import datetime
import io

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from app.config.config import TEMP_DOWNLOAD_PATH
from app.database import db

logger = logging.getLogger(__name__)

async def generate_claim_form(user_id: int, policy_id: str, claim_data: Dict, output_dir: Path = TEMP_DOWNLOAD_PATH) -> Optional[Path]:
    """Generate a filled-in claim form PDF"""
    try:
        # Get policy details
        policy = await db.get_policy(policy_id)
        if not policy:
            logger.error(f"Policy not found: {policy_id}")
            return None
            
        # Get user details
        user = await db.get_user(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            return None
            
        # Create a timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"claim_form_{user_id}_{timestamp}.pdf"
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_file),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        style_heading = styles['Heading1']
        style_normal = styles['Normal']
        
        # Build the document content
        content = []
        
        # Add title
        content.append(Paragraph(f"Insurance Claim Form", style_heading))
        content.append(Spacer(1, 12))
        
        # Add policy information
        content.append(Paragraph(f"Policy Information", styles['Heading2']))
        content.append(Spacer(1, 6))
        
        policy_data = [
            ["Policy Provider:", policy.get("provider", "")],
            ["Policy Number:", policy.get("policy_number", "")],
            ["Policy Holder:", policy.get("policy_holder", "")],
            ["Policy Type:", policy.get("policy_type", "")]
        ]
        
        policy_table = Table(policy_data, colWidths=[120, 300])
        policy_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        content.append(policy_table)
        content.append(Spacer(1, 12))
        
        # Add claimant information
        content.append(Paragraph(f"Claimant Information", styles['Heading2']))
        content.append(Spacer(1, 6))
        
        claimant_data = [
            ["Name:", user.get("full_name", "")],
            ["Contact Number:", user.get("phone", "")],
            ["Email:", user.get("email", "")],
        ]
        
        claimant_table = Table(claimant_data, colWidths=[120, 300])
        claimant_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        content.append(claimant_table)
        content.append(Spacer(1, 12))
        
        # Add claim information
        content.append(Paragraph(f"Claim Information", styles['Heading2']))
        content.append(Spacer(1, 6))
        
        # Format claim data
        claim_info_data = [
            ["Claim Type:", claim_data.get("claim_type", "")],
            ["Date of Service:", claim_data.get("service_date", "")],
            ["Provider Name:", claim_data.get("provider_name", "")],
            ["Claim Amount:", f"${claim_data.get('amount', 0):.2f}"],
            ["Description:", claim_data.get("description", "")]
        ]
        
        claim_info_table = Table(claim_info_data, colWidths=[120, 300])
        claim_info_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        content.append(claim_info_table)
        content.append(Spacer(1, 24))
        
        # Add signature line
        content.append(Paragraph("I hereby certify that the information provided is true and accurate to the best of my knowledge.", style_normal))
        content.append(Spacer(1, 24))
        
        signature_data = [
            ["Signature:", "________________________"],
            ["Date:", datetime.now().strftime("%Y-%m-%d")]
        ]
        
        signature_table = Table(signature_data, colWidths=[120, 300])
        signature_table.setStyle(TableStyle([
            ('LINEBELOW', (1, 0), (1, 0), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        content.append(signature_table)
        
        # Build the document
        doc.build(content)
        
        logger.info(f"Generated claim form: {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error generating claim form: {e}")
        return None

async def analyze_optimal_claim_path(user_id: int, situation: str) -> Dict:
    """Analyze and recommend the optimal claim path across multiple policies"""
    from app.services.nlp_service import recommend_claim_options
    
    # Get all user policies
    policies = await db.get_policies(user_id)
    if not policies:
        return {
            "success": False,
            "message": "No policies found. Please upload your insurance policies first."
        }
    
    # Use NLP service to analyze policies and recommend claim options
    recommendations = await recommend_claim_options(policies, situation)
    
    return {
        "success": True,
        "recommendations": recommendations
    }

async def track_claim_status(claim_id: str) -> Dict:
    """Check the status of a claim"""
    claim = await db.get_claim(claim_id)
    if not claim:
        return {
            "success": False,
            "message": f"Claim not found with ID: {claim_id}"
        }
    
    return {
        "success": True,
        "claim": claim
    }

async def update_claim_status(claim_id: str, new_status: str, notes: Optional[str] = None) -> Dict:
    """Update the status of a claim"""
    update_data = {
        "status": new_status,
    }
    
    if notes:
        update_data["notes"] = notes
    
    updated_claim = await db.update_claim(claim_id, update_data)
    
    if not updated_claim:
        return {
            "success": False,
            "message": f"Failed to update claim with ID: {claim_id}"
        }
    
    return {
        "success": True,
        "claim": updated_claim
    }
