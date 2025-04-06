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
    
    # Create a map of policy details for easier reference
    policy_map = {}
    policy_number_map = {}  # Map policy numbers to policy IDs
    policy_id_to_number = {}  # Map policy IDs to policy numbers
    
    for policy in policies:
        policy_id = str(policy["_id"])
        policy_number = policy.get("policy_number", "") or policy.get("policy_id", "")
        
        policy_map[policy_id] = {
            "id": policy_id,
            "provider": policy.get("provider", ""),
            "policy_type": policy.get("policy_type", ""),
            "policy_number": policy_number,
            "coverage_areas": policy.get("coverage_areas", {}),
            "deductible": policy.get("deductible", ""),
            "copayment": policy.get("copayment", ""),
            "out_of_pocket_max": policy.get("out_of_pocket_max", "")
        }
        
        # Map by policy number if available
        if policy_number:
            policy_number_map[policy_number] = policy_id
            policy_id_to_number[policy_id] = policy_number
    
    logger.info(f"Policy number map: {policy_number_map}")
    
    # Use NLP service to analyze policies and recommend claim options
    recommendations = await recommend_claim_options(policies, situation)
    
    logger.info(f"Raw recommendations: {recommendations}")
    
    # Create a mapping of policy types to actual policy IDs
    policy_type_map = {}
    for policy_id, policy in policy_map.items():
        policy_type = policy["policy_type"].lower()
        if "health" in policy_type:
            policy_type_map["health"] = policy_id
        elif "auto" in policy_type:
            policy_type_map["auto"] = policy_id
        elif "home" in policy_type:
            policy_type_map["home"] = policy_id
    
    # Extract policy numbers from the explanation if available
    policy_numbers = {}
    if recommendations.get("explanation"):
        import re
        # Look for patterns like "policy 123456" or "policy number 123456"
        policy_matches = re.findall(r'policy\s+(?:number\s+)?(\d{6})', recommendations["explanation"], re.IGNORECASE)
        for match in policy_matches:
            # Find the policy with this number
            if match in policy_number_map:
                policy_numbers[match] = policy_number_map[match]
    
    logger.info(f"Extracted policy numbers: {policy_numbers}")
    
    # Update applicable policies to use actual policy IDs
    if recommendations.get("applicable_policies"):
        actual_policies = []
        for policy_id in recommendations["applicable_policies"]:
            # If it's a known policy ID, use it directly
            if policy_id in policy_map:
                actual_policies.append(policy_id)
            # If it's a policy number, look it up
            elif policy_id in policy_number_map:
                actual_policies.append(policy_number_map[policy_id])
            else:
                # Try to map based on policy type mentioned in the recommendation
                policy_type = policy_id.lower()
                if "health" in policy_type and "health" in policy_type_map:
                    actual_policies.append(policy_type_map["health"])
                elif "auto" in policy_type and "auto" in policy_type_map:
                    actual_policies.append(policy_type_map["auto"])
                elif "home" in policy_type and "home" in policy_type_map:
                    actual_policies.append(policy_type_map["home"])
        recommendations["applicable_policies"] = list(set(actual_policies))  # Remove duplicates
    
    # If no applicable policies were found, try to extract from the explanation
    if not recommendations.get("applicable_policies") and policy_numbers:
        recommendations["applicable_policies"] = list(policy_numbers.values())
    
    logger.info(f"Applicable policies after mapping: {recommendations.get('applicable_policies', [])}")
    
    # Update coverage details to use actual policy IDs
    if recommendations.get("coverage_details"):
        actual_coverage_details = []
        for detail in recommendations["coverage_details"]:
            policy_id = detail.get("policy_id", "")
            if policy_id in policy_map:
                # Use the actual policy details
                policy = policy_map[policy_id]
                detail["policy_id"] = policy_id
                if "estimated_coverage" not in detail:
                    # Try to get coverage from policy details
                    coverage_areas = policy["coverage_areas"]
                    if coverage_areas:
                        total_coverage = sum(
                            float(str(area.get("limit", "0")).replace("$", "").replace(",", ""))
                            for area in coverage_areas.values()
                            if isinstance(area, dict) and "limit" in area
                        )
                        detail["estimated_coverage"] = f"${total_coverage:,.2f}"
                if "deductible" not in detail and policy["deductible"]:
                    detail["deductible"] = policy["deductible"]
                if "copay" not in detail and policy["copayment"]:
                    detail["copay"] = policy["copayment"]
            # If it's a policy number, look it up
            elif policy_id in policy_number_map:
                actual_id = policy_number_map[policy_id]
                policy = policy_map[actual_id]
                detail["policy_id"] = actual_id
                if "estimated_coverage" not in detail:
                    # Try to get coverage from policy details
                    coverage_areas = policy["coverage_areas"]
                    if coverage_areas:
                        total_coverage = sum(
                            float(str(area.get("limit", "0")).replace("$", "").replace(",", ""))
                            for area in coverage_areas.values()
                            if isinstance(area, dict) and "limit" in area
                        )
                        detail["estimated_coverage"] = f"${total_coverage:,.2f}"
                if "deductible" not in detail and policy["deductible"]:
                    detail["deductible"] = policy["deductible"]
                if "copay" not in detail and policy["copayment"]:
                    detail["copay"] = policy["copayment"]
                actual_coverage_details.append(detail)
            else:
                # Try to map based on policy type
                policy_type = policy_id.lower()
                if "health" in policy_type and "health" in policy_type_map:
                    actual_id = policy_type_map["health"]
                    detail["policy_id"] = actual_id
                    actual_coverage_details.append(detail)
                elif "auto" in policy_type and "auto" in policy_type_map:
                    actual_id = policy_type_map["auto"]
                    detail["policy_id"] = actual_id
                    actual_coverage_details.append(detail)
                elif "home" in policy_type and "home" in policy_type_map:
                    actual_id = policy_type_map["home"]
                    detail["policy_id"] = actual_id
                    actual_coverage_details.append(detail)
        recommendations["coverage_details"] = actual_coverage_details
    
    # If no coverage details were found, create them from the applicable policies
    if not recommendations.get("coverage_details") and recommendations.get("applicable_policies"):
        for policy_id in recommendations["applicable_policies"]:
            if policy_id in policy_map:
                policy = policy_map[policy_id]
                coverage_detail = {
                    "policy_id": policy_id,
                    "estimated_coverage": "See policy for details",
                    "deductible": policy["deductible"] or "See policy for details",
                    "copay": policy["copayment"] or "See policy for details"
                }
                
                # Try to calculate total coverage
                coverage_areas = policy["coverage_areas"]
                if coverage_areas:
                    total_coverage = sum(
                        float(str(area.get("limit", "0")).replace("$", "").replace(",", ""))
                        for area in coverage_areas.values()
                        if isinstance(area, dict) and "limit" in area
                    )
                    if total_coverage > 0:
                        coverage_detail["estimated_coverage"] = f"${total_coverage:,.2f}"
                
                if not recommendations.get("coverage_details"):
                    recommendations["coverage_details"] = []
                recommendations["coverage_details"].append(coverage_detail)
    
    # Update filing order to use actual policy IDs
    if recommendations.get("filing_order"):
        actual_filing_order = []
        for policy_id in recommendations["filing_order"]:
            if policy_id in policy_map:
                actual_filing_order.append(policy_id)
            # If it's a policy number, look it up
            elif policy_id in policy_number_map:
                actual_filing_order.append(policy_number_map[policy_id])
            else:
                # Try to map based on policy type
                policy_type = policy_id.lower()
                if "health" in policy_type and "health" in policy_type_map:
                    actual_filing_order.append(policy_type_map["health"])
                elif "auto" in policy_type and "auto" in policy_type_map:
                    actual_filing_order.append(policy_type_map["auto"])
                elif "home" in policy_type and "home" in policy_type_map:
                    actual_filing_order.append(policy_type_map["home"])
        recommendations["filing_order"] = list(dict.fromkeys(actual_filing_order))  # Remove duplicates while preserving order
    
    # If no filing order was found, use the applicable policies
    if not recommendations.get("filing_order") and recommendations.get("applicable_policies"):
        recommendations["filing_order"] = recommendations["applicable_policies"].copy()
    
    # Ensure limitations exist
    if not recommendations.get("limitations"):
        recommendations["limitations"] = ["See policy for specific limitations and exclusions."]
    
    # Update the explanation to ensure it uses the correct policy IDs
    if recommendations.get("explanation") and recommendations.get("applicable_policies"):
        explanation = recommendations["explanation"]
        for policy_id in recommendations["applicable_policies"]:
            if policy_id in policy_map:
                policy = policy_map[policy_id]
                policy_number = policy["policy_number"]
                policy_type = policy["policy_type"]
                
                # Replace generic references with specific policy numbers
                explanation = explanation.replace(f"{policy_type} insurance policy", f"{policy_type} insurance policy {policy_number}")
                explanation = explanation.replace(f"policy {policy_id}", f"policy {policy_number}")
        
        recommendations["explanation"] = explanation
    
    # Add policy numbers to the response for display
    recommendations["policy_numbers"] = {}
    for policy_id in recommendations.get("applicable_policies", []):
        if policy_id in policy_id_to_number:
            recommendations["policy_numbers"][policy_id] = policy_id_to_number[policy_id]
    
    # Update the structured sections to use policy numbers
    if recommendations.get("applicable_policies"):
        recommendations["applicable_policies"] = [
            f"Policy {policy_id_to_number.get(policy_id, policy_id)} ({', '.join(policy_map[policy_id]['coverage_areas'].keys())})..."
            for policy_id in recommendations["applicable_policies"]
            if policy_id in policy_map
        ]
    
    if recommendations.get("coverage_details"):
        for detail in recommendations["coverage_details"]:
            policy_id = detail.get("policy_id", "")
            if policy_id in policy_map:
                policy = policy_map[policy_id]
                detail["policy_id"] = f"Policy {policy_id_to_number.get(policy_id, policy_id)} ({', '.join(policy['coverage_areas'].keys())})..."
    
    if recommendations.get("filing_order"):
        recommendations["filing_order"] = [
            f"Policy {policy_id_to_number.get(policy_id, policy_id)} ({', '.join(policy_map[policy_id]['coverage_areas'].keys())})..."
            for policy_id in recommendations["filing_order"]
            if policy_id in policy_map
        ]
    
    logger.info(f"Final recommendations: {recommendations}")
    
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
