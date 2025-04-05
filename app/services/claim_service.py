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
        
        # Add policy information with default values
        content.append(Paragraph(f"Policy Information", styles['Heading2']))
        content.append(Spacer(1, 6))
        
        # Extract policy ID for display if other details are missing
        policy_id_str = str(policy.get("_id", ""))
        policy_id_short = policy_id_str[-6:] if policy_id_str else ""
        
        # Format policy information with defaults
        provider = policy.get("provider", "")
        if not provider:
            # Try alternative fields
            if policy.get("company_name"):
                provider = policy.get("company_name")
            elif policy.get("insurer"):
                provider = policy.get("insurer")
            elif policy_id_short:
                provider = f"Policy {policy_id_short}"
            else:
                provider = "Not Specified"
        
        policy_number = policy.get("policy_number", "")
        if not policy_number:
            policy_number = policy.get("id_number", policy_id_short) or "Not Specified"
        
        policy_holder = policy.get("policy_holder", "")
        if not policy_holder:
            # Try to construct from user information
            policy_holder = f"{user.get('first_name', '')} {user.get('last_name', '')}"
            if not policy_holder.strip():
                policy_holder = user.get('username', 'John Doe')
        
        policy_type = policy.get("policy_type", "")
        if not policy_type:
            # Try to determine from coverage areas
            if policy.get("coverage_areas"):
                areas = list(policy.get("coverage_areas", {}).keys())
                if areas:
                    policy_type = f"{areas[0].capitalize()} Insurance"
            else:
                policy_type = "Health Insurance"
                
        policy_data = [
            ["Policy Provider:", provider],
            ["Policy Number:", policy_number],
            ["Policy Holder:", policy_holder],
            ["Policy Type:", policy_type]
        ]
        
        policy_table = Table(policy_data, colWidths=[120, 300])
        policy_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        content.append(policy_table)
        content.append(Spacer(1, 12))
        
        # Add claimant information with defaults
        content.append(Paragraph(f"Claimant Information", styles['Heading2']))
        content.append(Spacer(1, 6))
        
        # Construct full name from available fields
        full_name = user.get("full_name", "")
        if not full_name:
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            if first_name or last_name:
                full_name = f"{first_name} {last_name}".strip()
            else:
                full_name = user.get("username", "John Doe")
        
        # Use Telegram ID as fallback for contact info
        phone = user.get("phone", "")
        if not phone:
            phone = user.get("contact_number", f"Telegram ID: {user_id}")
        
        email = user.get("email", "")
        if not email:
            email = user.get("username", "") + "@example.com" if user.get("username") else "Not Provided"
        
        claimant_data = [
            ["Name:", full_name],
            ["Contact Number:", phone],
            ["Email:", email],
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
            ["Claim Type:", claim_data.get("claim_type", "Not Specified")],
            ["Date of Service:", claim_data.get("service_date", datetime.now().strftime("%Y-%m-%d"))],
            ["Provider Name:", claim_data.get("provider_name", "Not Specified")],
            ["Claim Amount:", f"${claim_data.get('amount', 0):.2f}"],
            ["Description:", claim_data.get("description", "Not Specified")]
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
    
    logger.info(f"Found {len(policies)} policies for user {user_id}")
    logger.info(f"Policy IDs: {[str(p['_id']) for p in policies]}")
    
    # Use NLP service to analyze policies and recommend claim options
    recommendations = await recommend_claim_options(policies, situation)
    
    logger.info(f"Raw recommendations: {recommendations}")
    
    # Create a list of actual policy IDs as strings
    actual_policy_ids = [str(p["_id"]) for p in policies]
    
    # FIX: Check if returned policies exist - if not, replace them with actual ones
    if recommendations.get("applicable_policies"):
        # Check if any of the applicable_policies don't exist in our database
        for i, policy_id in enumerate(recommendations["applicable_policies"]):
            if policy_id not in actual_policy_ids:
                logger.warning(f"Replacing fictional policy ID {policy_id} with a real one")
                # Replace with the first actual policy ID
                if actual_policy_ids:
                    recommendations["applicable_policies"][i] = actual_policy_ids[0]
        
        # If we still have no valid policies, use all available policies
        if not recommendations["applicable_policies"] or all(pid not in actual_policy_ids for pid in recommendations["applicable_policies"]):
            recommendations["applicable_policies"] = actual_policy_ids
    else:
        # Default to all policies if none provided
        recommendations["applicable_policies"] = actual_policy_ids
    
    # FIX: Update coverage details to use actual policy IDs
    if recommendations.get("coverage_details"):
        fixed_coverage_details = []
        for detail in recommendations["coverage_details"]:
            if detail.get("policy_id") not in actual_policy_ids:
                # Get the first applicable policy ID or first actual policy ID
                replacement_id = (
                    recommendations["applicable_policies"][0] 
                    if recommendations.get("applicable_policies") 
                    else actual_policy_ids[0]
                )
                detail["policy_id"] = replacement_id
            fixed_coverage_details.append(detail)
        recommendations["coverage_details"] = fixed_coverage_details
    else:
        # Create default coverage details for each applicable policy
        recommendations["coverage_details"] = []
        for policy_id in recommendations["applicable_policies"]:
            # Extract coverage and deductible info from explanation if possible
            explanation = recommendations.get("explanation", "").lower()
            
            # Try to find dollar amounts in the explanation
            import re
            amount_matches = re.findall(r'\$?(\d+[,\d]*)', explanation)
            estimated_coverage = None
            deductible = None
            
            if amount_matches:
                for match in amount_matches:
                    amount = match.replace(',', '')
                    if "deductible" in explanation.lower() and not deductible:
                        deductible = f"${amount}"
                    elif estimated_coverage is None:
                        estimated_coverage = f"${amount}"
            
            recommendations["coverage_details"].append({
                "policy_id": policy_id,
                "estimated_coverage": estimated_coverage or "See policy for details",
                "deductible": deductible or "See policy for details",
                "copay": "See policy for details"
            })
    
    # FIX: Update filing order to use actual policy IDs
    if not recommendations.get("filing_order") or not all(pid in actual_policy_ids for pid in recommendations["filing_order"]):
        # Use applicable_policies as filing order
        recommendations["filing_order"] = recommendations["applicable_policies"].copy()
    
    # Ensure limitations exist
    if not recommendations.get("limitations"):
        recommendations["limitations"] = ["See policy for specific limitations and exclusions."]
    
    logger.info(f"Final applicable_policies: {recommendations.get('applicable_policies', [])}")
    logger.info(f"Final coverage_details: {recommendations.get('coverage_details', [])}")
    logger.info(f"Final filing_order: {recommendations.get('filing_order', [])}")
    
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
