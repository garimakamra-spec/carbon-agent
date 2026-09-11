import os
import json
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. THE TOOLS (Things the agents can query)
# ==========================================

PROJECT_SCHEDULES = {
    "High-Speed Rail Viaduct - Phase 2": [
        {"id": "ACT-101", "name": "Foundations & Piling (North)", "duration_days": 20, "material": "C30/37 Concrete", "quantity": 800, "unit": "m3", "month": "Month 1"},
        {"id": "ACT-102", "name": "Viaduct Piers Section 1", "duration_days": 35, "material": "C40/50 High-Strength Concrete", "quantity": 1200, "unit": "m3", "month": "Month 2"},
        {"id": "ACT-103", "name": "Viaduct Piers Section 2 (Rush)", "duration_days": 15, "material": "Rapid-Setting Concrete", "quantity": 1100, "unit": "m3", "month": "Month 2"},
        {"id": "ACT-104", "name": "Deck Superstructure Steelwork", "duration_days": 40, "material": "Structural Steel Beams", "quantity": 450, "unit": "tonnes", "month": "Month 3"},
        {"id": "ACT-105", "name": "Retaining Wall & Drainage", "duration_days": 25, "material": "Pre-cast Concrete Blocks", "quantity": 300, "unit": "m3", "month": "Month 4"},
    ],
    "Urban Hospital Tower": [
        {"id": "HOS-201", "name": "Substructure & Deep Piling", "duration_days": 28, "material": "C30/37 Concrete", "quantity": 950, "unit": "m3", "month": "Month 1"},
        {"id": "HOS-202", "name": "Core Walls & Shear Columns", "duration_days": 42, "material": "C40/50 High-Strength Concrete", "quantity": 1350, "unit": "m3", "month": "Month 2"},
        {"id": "HOS-203", "name": "Composite Floor Beams", "duration_days": 35, "material": "Structural Steel Beams", "quantity": 420, "unit": "tonnes", "month": "Month 3"},
        {"id": "HOS-204", "name": "Enclosure & Partition Walls", "duration_days": 22, "material": "Pre-cast Concrete Blocks", "quantity": 380, "unit": "m3", "month": "Month 4"},
    ],
    "Highway Interchange": [
        {"id": "HWY-301", "name": "Earth Retaining Structures", "duration_days": 25, "material": "Pre-cast Concrete Blocks", "quantity": 550, "unit": "m3", "month": "Month 1"},
        {"id": "HWY-302", "name": "Bridge Abutments & Columns", "duration_days": 38, "material": "C40/50 High-Strength Concrete", "quantity": 1100, "unit": "m3", "month": "Month 2"},
        {"id": "HWY-303", "name": "Emergency Deck Repair (Fast-Cure)", "duration_days": 12, "material": "Rapid-Setting Concrete", "quantity": 900, "unit": "m3", "month": "Month 2"},
        {"id": "HWY-304", "name": "Span Girders & Safety Barriers", "duration_days": 30, "material": "Structural Steel Beams", "quantity": 360, "unit": "tonnes", "month": "Month 3"},
    ]
}

MOCK_SCHEDULE = PROJECT_SCHEDULES["High-Speed Rail Viaduct - Phase 2"]

EPD_DATABASE = {
    "c30/37 concrete": {"gwp_per_unit": 240.0, "unit": "kg CO2e/m3", "source": "National ICE Database", "confidence": 0.95},
    "c40/50 high-strength concrete": {"gwp_per_unit": 310.0, "unit": "kg CO2e/m3", "source": "Verified EPD - Cemex", "confidence": 0.92},
    "rapid-setting concrete": {"gwp_per_unit": 460.0, "unit": "kg CO2e/m3", "source": "Supplier Data (High Carbon)", "confidence": 0.88},
    "structural steel beams": {"gwp_per_unit": 1250.0, "unit": "kg CO2e/tonne", "source": "CARES UK Recycled", "confidence": 0.94},
    "pre-cast concrete blocks": {"gwp_per_unit": 210.0, "unit": "kg CO2e/m3", "source": "Regional Benchmark", "confidence": 0.72}
}

# ==========================================
# 2. SPECIALIST AGENT FUNCTIONS
# ==========================================

def schedule_quant_agent(schedule_data):
    """Parses activities and organizes timeline."""
    summary = []
    for item in schedule_data:
        summary.append({
            "Activity ID": item["id"],
            "Task": item["name"],
            "Timeline": item["month"],
            "Material": item["material"],
            "Quantity": f"{item['quantity']} {item['unit']}"
        })
    return summary

def material_epd_agent(schedule_data):
    """Matches each material to an EPD and calculates carbon."""
    enriched = []
    for item in schedule_data:
        mat_key = item["material"].lower()
        epd = EPD_DATABASE.get(mat_key, {"gwp_per_unit": 300.0, "unit": "kg CO2e/unit", "source": "Default Proxy", "confidence": 0.50})
        
        # Carbon Calculation: Quantity * Carbon factor / 1000 = Tonnes CO2e
        total_co2e_tonnes = (item["quantity"] * epd["gwp_per_unit"]) / 1000.0
        
        enriched.append({
            "activity_id": item["id"],
            "task": item["name"],
            "month": item["month"],
            "material": item["material"],
            "co2e_tonnes": round(total_co2e_tonnes, 2),
            "epd_source": epd["source"],
            "confidence": epd["confidence"]
        })
    return enriched

def compliance_critic_agent(carbon_data, monthly_cap_tonnes=600.0):
    """Audits data for carbon budget spikes and low confidence matches."""
    flags = []
    
    # Check monthly totals against cap
    df = pd.DataFrame(carbon_data)
    monthly_totals = df.groupby("month")["co2e_tonnes"].sum().to_dict()
    
    for month, total in monthly_totals.items():
        if total > monthly_cap_tonnes:
            flags.append({
                "type": "BUDGET_SPIKE",
                "severity": "HIGH",
                "message": f"🚨 Warning: {month} emissions reach {total:.1f} t CO2e, exceeding client ceiling of {monthly_cap_tonnes} t CO2e!"
            })
            
    # Check confidence
    for item in carbon_data:
        if item["confidence"] < 0.80:
            flags.append({
                "type": "LOW_CONFIDENCE",
                "severity": "MEDIUM",
                "message": f"⚠️ Activity {item['activity_id']} ({item['task']}) has low EPD match confidence ({item['confidence']*100:.0f}%). Needs human sign-off."
            })
            
    return flags, monthly_totals

# ==========================================
# 3. THE ORCHESTRATOR
# ==========================================

def run_esg_pipeline(project_name="High-Speed Rail Viaduct - Phase 2", monthly_cap=600.0, schedule_data=None):
    """Runs the entire multi-agent workflow sequentially."""
    logs = []
    
    if schedule_data is None:
        schedule_data = PROJECT_SCHEDULES.get(project_name, MOCK_SCHEDULE)
    
    logs.append(f"🤖 [Orchestrator]: Ingesting P6 Construction Schedule for '{project_name}'...")
    quant_results = schedule_quant_agent(schedule_data)
    logs.append(f"✓ [Schedule Quant Agent]: Parsed {len(quant_results)} structural activities.")
    
    logs.append("🤖 [Orchestrator]: Querying verified EPD registries for embodied carbon factors...")
    carbon_results = material_epd_agent(schedule_data)
    logs.append(f"✓ [Material & EPD Agent]: Successfully calculated Scope 3 embodied carbon.")
    
    logs.append(f"🤖 [Orchestrator]: Handing data to Compliance Critic for boundary & cap auditing (Cap: {monthly_cap:.0f} t CO2e)...")
    flags, monthly_totals = compliance_critic_agent(carbon_results, monthly_cap_tonnes=monthly_cap)
    logs.append(f"✓ [Critic Agent]: Audit complete. Emitted {len(flags)} alerts.")
    
    total_project_carbon = sum(item["co2e_tonnes"] for item in carbon_results)
    
    return {
        "logs": logs,
        "carbon_data": carbon_results,
        "monthly_totals": monthly_totals,
        "flags": flags,
        "total_co2e": total_project_carbon,
        "project_name": project_name,
        "monthly_cap": monthly_cap
    }