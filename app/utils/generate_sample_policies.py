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

def create_sample_policy(output_path, policy_type, policy_data):
    # Create a new PDF document
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Add title
    title = f"{policy_type} Insurance Policy"
    elements.append(Paragraph(title, styles['Title']))
    elements.append(Spacer(1, 12))

    # Add policy information
    policy_info = [
        ["Policy Number:", policy_data['policy_id']],
        ["Insurance Company:", policy_data['company']],
        ["Policy Holder:", policy_data['holder_name']],
        ["Start Date:", policy_data['start_date']],
        ["End Date:", policy_data['end_date']],
        ["Premium:", f"${float(policy_data['premium']):,.2f}"],
        ["Deductible:", f"${float(policy_data['deductible']):,.2f}"],
        ["Copayment:", policy_data['copayment']],
        ["Out of Pocket Maximum:", f"${float(policy_data['out_of_pocket_max']):,.2f}"]
    ]

    # Create table for policy information
    table = Table(policy_info)
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    # Add coverage areas section
    elements.append(Paragraph("Coverage Areas", styles['Heading2']))
    elements.append(Spacer(1, 6))

    coverage_data = []
    coverage_data.append(["Coverage Type", "Limit", "Description"])
    for coverage_type, details in policy_data['coverage_areas'].items():
        coverage_data.append([
            coverage_type.replace('_', ' ').title(),
            f"${details['limit']:,}",
            details['description']
        ])

    # Create table for coverage areas
    coverage_table = Table(coverage_data, colWidths=[120, 80, 300])
    coverage_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(coverage_table)
    elements.append(Spacer(1, 12))

    # Add exclusions section
    if policy_data['exclusions']:
        elements.append(Paragraph("Exclusions", styles['Heading2']))
        elements.append(Spacer(1, 6))
        for exclusion in policy_data['exclusions']:
            elements.append(Paragraph(f"• {exclusion}", styles['Normal']))
        elements.append(Spacer(1, 12))

    # Add special conditions section
    if policy_data['special_conditions']:
        elements.append(Paragraph("Special Conditions", styles['Heading2']))
        elements.append(Spacer(1, 6))
        for condition in policy_data['special_conditions']:
            elements.append(Paragraph(f"• {condition}", styles['Normal']))

    # Build the PDF
    doc.build(elements)

async def store_policy_in_db(policy_data, user_id=12345):
    """Store the policy in MongoDB"""
    # Ensure coverage_areas is a dictionary
    if isinstance(policy_data['coverage_areas'], list):
        coverage_areas = {}
        for coverage in policy_data['coverage_areas']:
            # Handle different possible keys for coverage type
            coverage_type = coverage.get('type', coverage.get('coverage_type', '')).lower().replace(' ', '_')
            if not coverage_type:
                continue
                
            # Handle different possible formats for limit
            limit = coverage.get('limit', 0)
            if isinstance(limit, str):
                limit = float(limit.replace('$', '').replace(',', ''))
                
            coverage_areas[coverage_type] = {
                'limit': limit,
                'description': coverage.get('description', '')
            }
        policy_data['coverage_areas'] = coverage_areas

    # Handle monetary values that might be strings
    for field in ['premium', 'deductible', 'out_of_pocket_max']:
        if isinstance(policy_data.get(field), str):
            policy_data[field] = float(policy_data[field].replace('$', '').replace(',', ''))

    # Handle field name variations
    field_mappings = {
        'policy_provider': 'company',
        'policy_holder': 'holder_name',
        'policy_id': 'policy_id',
        'premium_amount': 'premium',
        'deductibles': 'deductible',
        'copayments': 'copayment',
        'out_of_pocket_maximum': 'out_of_pocket_max'
    }
    
    # Create a new policy document with standardized field names
    policy_doc = {}
    for old_field, new_field in field_mappings.items():
        if old_field in policy_data:
            policy_doc[new_field] = policy_data[old_field]
        elif new_field in policy_data:
            policy_doc[new_field] = policy_data[new_field]
    
    # Handle coverage period
    if 'coverage_period' in policy_data:
        if 'start_date' in policy_data['coverage_period']:
            policy_doc['start_date'] = datetime.strptime(policy_data['coverage_period']['start_date'], '%Y-%m-%d')
        if 'end_date' in policy_data['coverage_period']:
            policy_doc['end_date'] = datetime.strptime(policy_data['coverage_period']['end_date'], '%Y-%m-%d')
    else:
        if 'start_date' in policy_data:
            policy_doc['start_date'] = datetime.strptime(policy_data['start_date'], '%Y-%m-%d')
        if 'end_date' in policy_data:
            policy_doc['end_date'] = datetime.strptime(policy_data['end_date'], '%Y-%m-%d')
    
    # Add remaining fields
    policy_doc['coverage_areas'] = policy_data['coverage_areas']
    policy_doc['exclusions'] = policy_data['exclusions']
    policy_doc['special_conditions'] = policy_data.get('special_conditions', [])
    policy_doc['user_id'] = user_id
    policy_doc['created_at'] = datetime.utcnow()
    policy_doc['updated_at'] = datetime.utcnow()
    
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
            'premium': 299.99,
            'coverage_areas': {
                'hospitalization': {
                    'limit': 1000000,
                    'description': 'Inpatient hospital care and procedures'
                },
                'outpatient': {
                    'limit': 50000,
                    'description': 'Doctor visits and outpatient procedures'
                },
                'prescription': {
                    'limit': 10000,
                    'description': 'Prescription drug coverage'
                },
                'emergency': {
                    'limit': 100000,
                    'description': 'Emergency room visits and ambulance'
                },
                'preventive': {
                    'limit': 5000,
                    'description': 'Annual checkups and preventive care'
                },
                'mental_health': {
                    'limit': 25000,
                    'description': 'Mental health and counseling services'
                },
                'dental': {
                    'limit': 2000,
                    'description': 'Basic dental care and procedures'
                },
                'vision': {
                    'limit': 1000,
                    'description': 'Eye exams and vision care'
                }
            },
            'exclusions': [
                'Cosmetic surgery',
                'Experimental treatments',
                'Pre-existing conditions (first 6 months)',
                'Alternative medicine',
                'Non-emergency care outside network'
            ],
            'deductible': 1000,
            'copayment': '20%',
            'out_of_pocket_max': 5000,
            'special_conditions': []
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
            'premium': 499.99,
            'coverage_areas': {
                'liability': {
                    'limit': 100000,
                    'description': 'Bodily injury and property damage'
                },
                'collision': {
                    'limit': 50000,
                    'description': 'Damage to your vehicle from accidents'
                },
                'comprehensive': {
                    'limit': 25000,
                    'description': 'Non-collision damage (theft, vandalism, etc.)'
                },
                'medical_payments': {
                    'limit': 10000,
                    'description': 'Medical expenses for you and passengers'
                },
                'uninsured_motorist': {
                    'limit': 50000,
                    'description': 'Coverage when hit by uninsured driver'
                },
                'rental_car': {
                    'limit': 50,
                    'description': 'Daily rental car allowance'
                },
                'roadside_assistance': {
                    'limit': 100,
                    'description': 'Towing and emergency services'
                }
            },
            'exclusions': [
                'Racing or speed testing',
                'Using vehicle for hire',
                'Intentional acts',
                'War or nuclear hazards',
                'Using vehicle for business without endorsement'
            ],
            'deductible': 500,
            'copayment': '0%',
            'out_of_pocket_max': 1000,
            'special_conditions': []
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
            'premium': 999.99,
            'coverage_areas': {
                'dwelling': {
                    'limit': 400000,
                    'description': 'Structure of your home'
                },
                'personal_property': {
                    'limit': 200000,
                    'description': 'Belongings inside your home'
                },
                'liability': {
                    'limit': 150000,
                    'description': 'Personal liability coverage'
                },
                'additional_living': {
                    'limit': 40000,
                    'description': 'Temporary living expenses'
                },
                'medical_payments': {
                    'limit': 10000,
                    'description': 'Medical expenses for guests'
                },
                'scheduled_items': {
                    'limit': 50000,
                    'description': 'Coverage for valuable items like jewelry and art'
                },
                'home_office': {
                    'limit': 25000,
                    'description': 'Coverage for home office equipment and business liability'
                }
            },
            'exclusions': [
                'Flood damage',
                'Earthquake damage',
                'Nuclear hazards',
                'War or terrorism',
                'Intentional acts'
            ],
            'deductible': 500,
            'copayment': '0%',
            'out_of_pocket_max': 1500,
            'special_conditions': []
        }
        
        filename = f"home_insurance_{company['name'].lower().replace(' ', '_')}.pdf"
        create_sample_policy(os.path.join(output_dir, filename), "Home", home_policy)
        await store_policy_in_db(home_policy)

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_sample_policies()) 