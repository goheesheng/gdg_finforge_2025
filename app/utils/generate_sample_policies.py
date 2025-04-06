from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import os
from datetime import datetime, timedelta
import random
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.config import MONGODB_URI, DB_NAME

# MongoDB setup
client = AsyncIOMotorClient(MONGODB_URI)
db = client[DB_NAME]

def create_sample_policy(filename, policy_type, policy_data):
    # Create PDF document
    doc = SimpleDocTemplate(
        filename,
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
    content.append(Paragraph(f"{policy_type} Insurance Policy", style_heading))
    content.append(Spacer(1, 12))
    
    # Add policy information
    policy_info = [
        ["Insurance Provider:", policy_data['company']],
        ["Policy ID:", policy_data['policy_id']],
        ["Policy Holder:", policy_data['holder_name']],
        ["Start Date:", policy_data['start_date']],
        ["End Date:", policy_data['end_date']],
        ["Premium:", f"${policy_data['premium']}"],
        ["Deductible:", f"${policy_data['deductible']}"],
        ["Copayment:", f"{policy_data['copayment']}%"],
        ["Out-of-Pocket Maximum:", f"${policy_data['out_of_pocket_max']}"]
    ]
    
    policy_table = Table(policy_info, colWidths=[150, 300])
    policy_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
    ]))
    
    content.append(policy_table)
    content.append(Spacer(1, 12))
    
    # Add coverage information
    content.append(Paragraph("Coverage Details", styles['Heading2']))
    content.append(Spacer(1, 6))
    
    coverage_data = [["Type", "Limit", "Description"]]
    for coverage in policy_data['coverages']:
        coverage_data.append([
            coverage['type'],
            f"${coverage['limit']}",
            coverage['description']
        ])
    
    coverage_table = Table(coverage_data, colWidths=[100, 100, 250])
    coverage_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
    ]))
    
    content.append(coverage_table)
    content.append(Spacer(1, 12))
    
    # Add exclusions
    content.append(Paragraph("Exclusions", styles['Heading2']))
    content.append(Spacer(1, 6))
    
    for exclusion in policy_data['exclusions']:
        content.append(Paragraph(f"• {exclusion}", style_normal))
        content.append(Spacer(1, 3))
    
    # Build the document
    doc.build(content)

async def store_policy_in_db(policy_data, user_id=12345):
    """Store the policy in MongoDB"""
    policy_doc = {
        "user_id": user_id,
        "provider": policy_data['company'],
        "policy_number": policy_data['policy_id'],
        "policy_holder": policy_data['holder_name'],
        "start_date": policy_data['start_date'],
        "end_date": policy_data['end_date'],
        "premium": float(policy_data['premium']),
        "deductible": float(policy_data['deductible']),
        "copayment": float(policy_data['copayment']),
        "out_of_pocket_max": float(policy_data['out_of_pocket_max']),
        "coverage_areas": {
            coverage['type']: {
                "limit": float(coverage['limit']),
                "description": coverage['description']
            }
            for coverage in policy_data['coverages']
        },
        "exclusions": policy_data['exclusions'],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.policies.insert_one(policy_doc)
    return result.inserted_id

def generate_6digit_policy_id():
    return str(random.randint(100000, 999999))

async def generate_sample_policies():
    # Create output directory if it doesn't exist
    output_dir = "generated_forms"
    os.makedirs(output_dir, exist_ok=True)
    
    # Clear existing policies from the database
    await db.policies.delete_many({})

    # Health Insurance Companies
    health_companies = [
        {
            'name': 'HealthCare Plus',
            'premium': '299.99',
            'deductible': '1000',
            'copayment': '20',
            'out_of_pocket_max': '5000',
            'coverages': [
                {'type': 'Hospital', 'limit': '500000', 'description': 'Inpatient and outpatient hospital services'},
                {'type': 'Medical', 'limit': '100000', 'description': 'Doctor visits and medical procedures'},
                {'type': 'Prescription', 'limit': '50000', 'description': 'Prescription medications'},
                {'type': 'Dental', 'limit': '2000', 'description': 'Basic dental services'},
                {'type': 'Vision', 'limit': '1000', 'description': 'Vision care and eyewear'},
            ],
            'exclusions': [
                'Cosmetic procedures',
                'Experimental treatments',
                'Pre-existing conditions (first 12 months)',
                'Alternative medicine',
                'Travel-related injuries'
            ]
        },
        {
            'name': 'MediGuard Insurance',
            'premium': '249.99',
            'deductible': '1500',
            'copayment': '15',
            'out_of_pocket_max': '4000',
            'coverages': [
                {'type': 'Hospital', 'limit': '400000', 'description': 'Inpatient and outpatient hospital services'},
                {'type': 'Medical', 'limit': '80000', 'description': 'Doctor visits and medical procedures'},
                {'type': 'Prescription', 'limit': '40000', 'description': 'Prescription medications'},
                {'type': 'Dental', 'limit': '1500', 'description': 'Basic dental services'},
                {'type': 'Vision', 'limit': '800', 'description': 'Vision care and eyewear'},
            ],
            'exclusions': [
                'Cosmetic procedures',
                'Experimental treatments',
                'Pre-existing conditions (first 18 months)',
                'Alternative medicine',
                'Travel-related injuries',
                'Weight loss programs'
            ]
        },
        {
            'name': 'WellnessFirst Health',
            'premium': '349.99',
            'deductible': '800',
            'copayment': '25',
            'out_of_pocket_max': '6000',
            'coverages': [
                {'type': 'Hospital', 'limit': '600000', 'description': 'Inpatient and outpatient hospital services'},
                {'type': 'Medical', 'limit': '150000', 'description': 'Doctor visits and medical procedures'},
                {'type': 'Prescription', 'limit': '75000', 'description': 'Prescription medications'},
                {'type': 'Dental', 'limit': '3000', 'description': 'Basic dental services'},
                {'type': 'Vision', 'limit': '1500', 'description': 'Vision care and eyewear'},
                {'type': 'Mental Health', 'limit': '50000', 'description': 'Mental health services and counseling'},
            ],
            'exclusions': [
                'Cosmetic procedures',
                'Experimental treatments',
                'Pre-existing conditions (first 6 months)',
                'Alternative medicine',
                'Travel-related injuries'
            ]
        },
        {
            'name': 'VitalCare Insurance',
            'premium': '199.99',
            'deductible': '2000',
            'copayment': '10',
            'out_of_pocket_max': '3500',
            'coverages': [
                {'type': 'Hospital', 'limit': '300000', 'description': 'Inpatient and outpatient hospital services'},
                {'type': 'Medical', 'limit': '50000', 'description': 'Doctor visits and medical procedures'},
                {'type': 'Prescription', 'limit': '25000', 'description': 'Prescription medications'},
                {'type': 'Dental', 'limit': '1000', 'description': 'Basic dental services'},
                {'type': 'Vision', 'limit': '500', 'description': 'Vision care and eyewear'},
            ],
            'exclusions': [
                'Cosmetic procedures',
                'Experimental treatments',
                'Pre-existing conditions (first 24 months)',
                'Alternative medicine',
                'Travel-related injuries',
                'Mental health services'
            ]
        }
    ]

    # Auto Insurance Companies
    auto_companies = [
        {
            'name': 'SafeDrive Insurance',
            'premium': '149.99',
            'deductible': '500',
            'copayment': '0',
            'out_of_pocket_max': '1000',
            'coverages': [
                {'type': 'Liability', 'limit': '100000', 'description': 'Bodily injury and property damage'},
                {'type': 'Collision', 'limit': '50000', 'description': 'Damage to your vehicle from accidents'},
                {'type': 'Comprehensive', 'limit': '25000', 'description': 'Non-collision damage (theft, weather, etc.)'},
                {'type': 'Medical', 'limit': '10000', 'description': 'Medical expenses for you and passengers'},
                {'type': 'Uninsured', 'limit': '25000', 'description': 'Coverage for uninsured motorists'},
            ],
            'exclusions': [
                'Racing or speed testing',
                'Commercial use',
                'Intentional damage',
                'Normal wear and tear',
                'Mechanical breakdown'
            ]
        },
        {
            'name': 'RoadGuard Auto',
            'premium': '179.99',
            'deductible': '750',
            'copayment': '0',
            'out_of_pocket_max': '1500',
            'coverages': [
                {'type': 'Liability', 'limit': '150000', 'description': 'Bodily injury and property damage'},
                {'type': 'Collision', 'limit': '75000', 'description': 'Damage to your vehicle from accidents'},
                {'type': 'Comprehensive', 'limit': '35000', 'description': 'Non-collision damage (theft, weather, etc.)'},
                {'type': 'Medical', 'limit': '15000', 'description': 'Medical expenses for you and passengers'},
                {'type': 'Uninsured', 'limit': '35000', 'description': 'Coverage for uninsured motorists'},
                {'type': 'Rental Car', 'limit': '5000', 'description': 'Rental car coverage while your vehicle is being repaired'},
            ],
            'exclusions': [
                'Racing or speed testing',
                'Commercial use',
                'Intentional damage',
                'Normal wear and tear',
                'Mechanical breakdown',
                'Off-road use'
            ]
        },
        {
            'name': 'SecureWheels Insurance',
            'premium': '129.99',
            'deductible': '1000',
            'copayment': '0',
            'out_of_pocket_max': '2000',
            'coverages': [
                {'type': 'Liability', 'limit': '50000', 'description': 'Bodily injury and property damage'},
                {'type': 'Collision', 'limit': '25000', 'description': 'Damage to your vehicle from accidents'},
                {'type': 'Comprehensive', 'limit': '15000', 'description': 'Non-collision damage (theft, weather, etc.)'},
                {'type': 'Medical', 'limit': '5000', 'description': 'Medical expenses for you and passengers'},
                {'type': 'Uninsured', 'limit': '15000', 'description': 'Coverage for uninsured motorists'},
            ],
            'exclusions': [
                'Racing or speed testing',
                'Commercial use',
                'Intentional damage',
                'Normal wear and tear',
                'Mechanical breakdown',
                'Rental car coverage'
            ]
        },
        {
            'name': 'AutoShield Protection',
            'premium': '199.99',
            'deductible': '250',
            'copayment': '0',
            'out_of_pocket_max': '800',
            'coverages': [
                {'type': 'Liability', 'limit': '200000', 'description': 'Bodily injury and property damage'},
                {'type': 'Collision', 'limit': '100000', 'description': 'Damage to your vehicle from accidents'},
                {'type': 'Comprehensive', 'limit': '50000', 'description': 'Non-collision damage (theft, weather, etc.)'},
                {'type': 'Medical', 'limit': '25000', 'description': 'Medical expenses for you and passengers'},
                {'type': 'Uninsured', 'limit': '50000', 'description': 'Coverage for uninsured motorists'},
                {'type': 'Rental Car', 'limit': '10000', 'description': 'Rental car coverage while your vehicle is being repaired'},
                {'type': 'Roadside Assistance', 'limit': '5000', 'description': 'Towing and roadside assistance services'},
            ],
            'exclusions': [
                'Racing or speed testing',
                'Commercial use',
                'Intentional damage',
                'Normal wear and tear',
                'Mechanical breakdown'
            ]
        }
    ]

    # Home Insurance Companies
    home_companies = [
        {
            'name': 'HomeGuard Insurance',
            'premium': '899.99',
            'deductible': '1000',
            'copayment': '0',
            'out_of_pocket_max': '2000',
            'coverages': [
                {'type': 'Dwelling', 'limit': '300000', 'description': 'Structure of your home'},
                {'type': 'Personal Property', 'limit': '150000', 'description': 'Belongings inside your home'},
                {'type': 'Liability', 'limit': '100000', 'description': 'Personal liability coverage'},
                {'type': 'Additional Living', 'limit': '30000', 'description': 'Temporary living expenses'},
                {'type': 'Medical Payments', 'limit': '5000', 'description': 'Medical expenses for guests'},
            ],
            'exclusions': [
                'Flood damage',
                'Earthquake damage',
                'Nuclear hazards',
                'War or terrorism',
                'Intentional acts'
            ]
        },
        {
            'name': 'SecureHome Protection',
            'premium': '799.99',
            'deductible': '1500',
            'copayment': '0',
            'out_of_pocket_max': '2500',
            'coverages': [
                {'type': 'Dwelling', 'limit': '250000', 'description': 'Structure of your home'},
                {'type': 'Personal Property', 'limit': '125000', 'description': 'Belongings inside your home'},
                {'type': 'Liability', 'limit': '75000', 'description': 'Personal liability coverage'},
                {'type': 'Additional Living', 'limit': '25000', 'description': 'Temporary living expenses'},
                {'type': 'Medical Payments', 'limit': '3000', 'description': 'Medical expenses for guests'},
                {'type': 'Scheduled Items', 'limit': '25000', 'description': 'Coverage for valuable items like jewelry and art'},
            ],
            'exclusions': [
                'Flood damage',
                'Earthquake damage',
                'Nuclear hazards',
                'War or terrorism',
                'Intentional acts',
                'Mold damage'
            ]
        },
        {
            'name': 'HouseShield Insurance',
            'premium': '999.99',
            'deductible': '500',
            'copayment': '0',
            'out_of_pocket_max': '1500',
            'coverages': [
                {'type': 'Dwelling', 'limit': '400000', 'description': 'Structure of your home'},
                {'type': 'Personal Property', 'limit': '200000', 'description': 'Belongings inside your home'},
                {'type': 'Liability', 'limit': '150000', 'description': 'Personal liability coverage'},
                {'type': 'Additional Living', 'limit': '40000', 'description': 'Temporary living expenses'},
                {'type': 'Medical Payments', 'limit': '10000', 'description': 'Medical expenses for guests'},
                {'type': 'Scheduled Items', 'limit': '50000', 'description': 'Coverage for valuable items like jewelry and art'},
                {'type': 'Home Office', 'limit': '25000', 'description': 'Coverage for home office equipment and business liability'},
            ],
            'exclusions': [
                'Flood damage',
                'Earthquake damage',
                'Nuclear hazards',
                'War or terrorism',
                'Intentional acts'
            ]
        },
        {
            'name': 'PropertyGuard Coverage',
            'premium': '699.99',
            'deductible': '2000',
            'copayment': '0',
            'out_of_pocket_max': '3000',
            'coverages': [
                {'type': 'Dwelling', 'limit': '200000', 'description': 'Structure of your home'},
                {'type': 'Personal Property', 'limit': '100000', 'description': 'Belongings inside your home'},
                {'type': 'Liability', 'limit': '50000', 'description': 'Personal liability coverage'},
                {'type': 'Additional Living', 'limit': '20000', 'description': 'Temporary living expenses'},
                {'type': 'Medical Payments', 'limit': '2000', 'description': 'Medical expenses for guests'},
            ],
            'exclusions': [
                'Flood damage',
                'Earthquake damage',
                'Nuclear hazards',
                'War or terrorism',
                'Intentional acts',
                'Mold damage',
                'Sewer backup',
                'Termite damage'
            ]
        }
    ]

    # Generate Health Insurance PDFs
    for company in health_companies:
        health_policy = {
            'company': company['name'],
            'policy_id': generate_6digit_policy_id(),  # Generate 6-digit policy ID
            'holder_name': 'John Smith',
            'start_date': (datetime.now()).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d'),
            'premium': company['premium'],
            'coverages': company['coverages'],
            'exclusions': company['exclusions'],
            'deductible': company['deductible'],
            'copayment': company['copayment'],
            'out_of_pocket_max': company['out_of_pocket_max']
        }
        
        filename = f"health_insurance_{company['name'].lower().replace(' ', '_')}.pdf"
        create_sample_policy(os.path.join(output_dir, filename), "Health", health_policy)
        await store_policy_in_db(health_policy)

    # Generate Auto Insurance PDFs
    for company in auto_companies:
        auto_policy = {
            'company': company['name'],
            'policy_id': generate_6digit_policy_id(),  # Generate 6-digit policy ID
            'holder_name': 'Sarah Johnson',
            'start_date': (datetime.now()).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d'),
            'premium': company['premium'],
            'coverages': company['coverages'],
            'exclusions': company['exclusions'],
            'deductible': company['deductible'],
            'copayment': company['copayment'],
            'out_of_pocket_max': company['out_of_pocket_max']
        }
        
        filename = f"auto_insurance_{company['name'].lower().replace(' ', '_')}.pdf"
        create_sample_policy(os.path.join(output_dir, filename), "Auto", auto_policy)
        await store_policy_in_db(auto_policy)

    # Generate Home Insurance PDFs
    for company in home_companies:
        home_policy = {
            'company': company['name'],
            'policy_id': generate_6digit_policy_id(),  # Generate 6-digit policy ID
            'holder_name': 'Michael Brown',
            'start_date': (datetime.now()).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d'),
            'premium': company['premium'],
            'coverages': company['coverages'],
            'exclusions': company['exclusions'],
            'deductible': company['deductible'],
            'copayment': company['copayment'],
            'out_of_pocket_max': company['out_of_pocket_max']
        }
        
        filename = f"home_insurance_{company['name'].lower().replace(' ', '_')}.pdf"
        create_sample_policy(os.path.join(output_dir, filename), "Home", home_policy)
        await store_policy_in_db(home_policy)

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_sample_policies()) 