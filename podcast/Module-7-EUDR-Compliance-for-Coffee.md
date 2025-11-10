# Module 7: EUDR Compliance for Coffee
## Automated Traceability and Deforestation-Free Proof

**An AgStack Project of The Linux Foundation**

**Episode**: Module 7 of 10  
**Duration**: ~30 minutes  
**Prerequisites**: Episode 0, Module 2 (BITE), Module 4 (MEAL)  
**Technical Level**: Intermediate

---

## Introduction

The **EU Deforestation Regulation (EUDR)** came into effect in December 2024, requiring coffee exporters to prove their products are deforestation-free. This module shows how PANCAKE automates EUDR compliance, turning a 3-month manual process into a 30-second automated report.

**What you'll learn:**
- EUDR requirements (geolocation, traceability, deforestation proof)
- PANCAKE solution (GeoID verification, MEAL traceability, cryptographic audit trail)
- Coffee exporter compliance workflow
- Automated report generation
- Cost comparison (before vs after PANCAKE)

**Who this is for:**
- Coffee exporters and cooperatives
- EUDR compliance managers
- Sustainability directors
- Regulatory auditors

---

## Chapter 1: The EUDR Challenge

### What is EUDR?

**EU Deforestation Regulation (EUDR)**:
- **Effective**: December 30, 2024
- **Scope**: Coffee, cocoa, palm oil, soy, beef, wood, rubber
- **Requirement**: Prove products are deforestation-free (no forest cleared after December 31, 2020)

### EUDR Requirements

**1. Geolocation Data**
- GPS coordinates or polygons for every farm
- Accuracy: ±10 meters
- Verification: Satellite imagery confirmation

**2. Traceability**
- Farm → Processing → Export (complete chain)
- Immutable timestamps
- Batch tracking (which farm's coffee in which export batch)

**3. Deforestation-Free Proof**
- Historical satellite imagery (2020-present)
- Forest cover analysis (NDVI time-series)
- No forest loss detected

**4. Due Diligence Documentation**
- Who: Farmer, processor, exporter
- What: Coffee variety, harvest date, quantity
- Where: Farm GeoID, processing facility, export port
- When: Timestamps for all steps

### The Manual Process (Before PANCAKE)

**José's Cooperative** (50 smallholder farmers):

**Step 1**: Collect GPS coordinates (2 weeks)
- Visit 50 farms with handheld GPS
- Record coordinates manually
- Errors: Typos, wrong fields, outdated boundaries

**Step 2**: Gather land title documents (1 week)
- Request photocopies from farmers
- Organize by farm
- Some missing, some illegible

**Step 3**: Compile harvest records (2 weeks)
- Export Excel spreadsheets from multiple systems
- Manually match harvest dates to farms
- Inconsistencies: Different date formats, missing entries

**Step 4**: Link to export invoices (1 week)
- Match coffee batches to farms
- Cross-reference with processing records
- Gaps: Some batches unaccounted for

**Step 5**: Satellite verification (1 month)
- Hire consultant to analyze satellite imagery
- Generate deforestation reports
- Cost: $5,000

**Total**: 3 months, $5,000 consultant fees, incomplete data

---

## Chapter 2: PANCAKE Solution

### Automated EUDR Compliance

**With PANCAKE**:
```python
# EUDR compliance query (automated)
eudr_report = pancake.generate_eudr_report(
    cooperative='josé_coffee_coop',
    harvest_year='2024',
    export_destination='EU'
)
```

**Result (in 30 seconds)**:
- ✅ All 50 farms have verified GeoIDs (satellite-confirmed polygons)
- ✅ All farms are deforestation-free (NDVI time-series shows forest cover stable since 2020)
- ✅ Complete traceability (MEAL threads: harvest → processing → export, immutable timestamps)
- ✅ Due diligence documentation (BITEs with GPS metadata, cryptographic hashes, tamper-proof)
- ✅ PDF report generated (ready for customs, auditors, EU authorities)

### How It Works

**1. Farm Registration** (one-time)
```python
# Each farmer's field assigned GeoID (S2 polygon)
farm_geoid = pancake.register_field(
    farmer_id='farmer-001',
    field_name='North Block',
    polygon_wkt='POLYGON((-75.5 4.6, -75.4 4.6, -75.4 4.7, -75.5 4.7, -75.5 4.6))',
    verification='satellite_confirmed'  # PANCAKE verifies via satellite imagery
)

# Store in Asset Registry
pancake.asset_registry.create({
    'geoid': farm_geoid,
    'owner': 'farmer-001',
    'crop': 'coffee',
    'certification': 'organic',
    'registration_date': '2024-01-15'
})
```

**2. Harvest Logging** (via mobile app)
```python
# Farmer records harvest in MEAL thread
harvest_meal = MEAL.create(
    meal_type='harvest',
    primary_location={'geoid': farm_geoid},
    participants=['farmer-001', 'cooperative-manager']
)

# Add harvest BITE
harvest_bite = BITE.create(
    bite_type='harvest_event',
    geoid=farm_geoid,
    body={
        'harvest_date': '2024-03-15',
        'quantity_kg': 1250,
        'variety': 'Arabica Caturra',
        'photos': ['https://storage.pancake.org/harvest-001.jpg'],
        'gps_coordinates': [4.6, -75.5],  # Verified against GeoID
        'harvest_method': 'selective_picking'
    }
)

# Add to MEAL (creates traceability chain)
harvest_meal.append_packet(
    packet_type='bite',
    bite=harvest_bite
)
```

**3. Processing Tracking** (via cooperative system)
```python
# Coffee batch linked to farm GeoIDs
processing_bite = BITE.create(
    bite_type='processing_event',
    geoid='processing-facility-001',
    body={
        'batch_id': 'BATCH-2024-001',
        'source_farms': [farm_geoid_1, farm_geoid_2, farm_geoid_3],  # Multiple farms
        'processing_date': '2024-03-20',
        'processing_method': 'washed',
        'output_quantity_kg': 3500,
        'quality_grade': 'premium'
    },
    footer={
        'references': [
            {'type': 'bite', 'id': harvest_bite['Header']['id']}  # Links to harvest
        ]
    }
)
```

**4. Export Documentation** (automated)
```python
# PANCAKE generates EUDR compliance report
def generate_eudr_report(cooperative, harvest_year, export_destination):
    """Generate complete EUDR compliance report"""
    
    # Step 1: Get all farms in cooperative
    farms = pancake.asset_registry.query(
        cooperative=cooperative,
        crop='coffee'
    )
    
    # Step 2: Verify deforestation-free status
    deforestation_status = []
    for farm in farms:
        geoid = farm['geoid']
        
        # Query satellite imagery (NDVI time-series since 2020)
        ndvi_history = pancake.query(
            f"Show me NDVI data for {geoid} from 2020-01-01 to present"
        )
        
        # Analyze forest cover stability
        forest_stable = analyze_forest_cover(ndvi_history)
        
        deforestation_status.append({
            'geoid': geoid,
            'farmer': farm['owner'],
            'deforestation_free': forest_stable,
            'verification_date': datetime.utcnow().isoformat()
        })
    
    # Step 3: Build traceability chain
    traceability = []
    for farm in farms:
        # Get harvest MEALs
        harvest_meals = pancake.query_meals(
            geoid=farm['geoid'],
            meal_type='harvest',
            year=harvest_year
        )
        
        # Get processing events (linked via references)
        processing_events = []
        for meal in harvest_meals:
            for packet in meal.packets:
                if packet['packet_type'] == 'bite':
                    bite_id = packet['bite']['Header']['id']
                    # Find processing events that reference this harvest
                    processing = pancake.query(
                        f"Find processing events that reference BITE {bite_id}"
                    )
                    processing_events.extend(processing)
        
        traceability.append({
            'farm': farm['geoid'],
            'harvests': harvest_meals,
            'processing': processing_events
        })
    
    # Step 4: Generate PDF report
    report = {
        'cooperative': cooperative,
        'harvest_year': harvest_year,
        'export_destination': export_destination,
        'generation_date': datetime.utcnow().isoformat(),
        'farms': deforestation_status,
        'traceability': traceability,
        'cryptographic_hash': compute_report_hash(deforestation_status, traceability)
    }
    
    # Generate PDF
    pdf = generate_pdf_report(report)
    
    return {
        'report': report,
        'pdf': pdf,
        'verification_hash': report['cryptographic_hash']
    }
```

---

## Chapter 3: Complete Workflow

### Step-by-Step: Coffee Export to EU

**1. Farm Registration** (one-time, per farm)
```
Farmer → Mobile App → Register Field → GeoID Assigned → Satellite Verification
```

**2. Harvest Season** (ongoing)
```
Farmer → Mobile App → Log Harvest → BITE Created → MEAL Thread Started
```

**3. Processing** (ongoing)
```
Cooperative → Processing System → Link Batch to Farms → Processing BITE → References Harvest BITEs
```

**4. Export Preparation** (before shipment)
```
Exporter → PANCAKE → Generate EUDR Report → PDF + Hash → Submit to Customs
```

**5. Customs Verification** (EU border)
```
Customs → Verify Hash → Check Satellite Data → Approve Import
```

### Example: Complete Traceability Chain

**Farm A (GeoID: `abc123...`)**:
```
2024-03-15: Harvest BITE (1250 kg, GPS verified)
  ↓ (MEAL reference)
2024-03-20: Processing BITE (Batch BATCH-2024-001, links to Farm A harvest)
  ↓ (BITE reference)
2024-04-10: Export BITE (500 kg from Batch BATCH-2024-001, destination: EU)
  ↓ (cryptographic hash chain)
2024-04-15: EUDR Report (PDF, hash: 0x8B7A...F9E2)
```

**Verification**:
- ✅ GeoID `abc123...` verified via satellite (polygon matches field boundary)
- ✅ NDVI time-series (2020-2024) shows no forest loss
- ✅ Harvest → Processing → Export chain is cryptographically linked
- ✅ All timestamps immutable (MEAL hash chain)

---

## Chapter 4: Cost Comparison

### Before PANCAKE

**José's Cooperative** (50 farms):
- **GPS collection**: 2 weeks × $50/day = $700
- **Document gathering**: 1 week × $50/day = $350
- **Data entry**: 2 weeks × $50/day = $700
- **Consultant (satellite analysis)**: $5,000
- **Total**: $6,750 per export season
- **Time**: 3 months

### With PANCAKE

**Setup** (one-time):
- **PANCAKE software**: $0 (AgStack open-source)
- **Hardware**: Raspberry Pi 5 ($150) or cloud server ($20/month)
- **Farm registration**: 1 day × $50/day = $50
- **Total setup**: $200

**Ongoing** (per export season):
- **Hosting**: $20/farm/year (co-op shares one server) = $1,000/year
- **Report generation**: Automated (0 hours)
- **Total per season**: $0 (hosting already paid)

**Time**: 30 seconds (automated report generation)

### ROI

**Savings per export season**: $6,750 - $0 = **$6,750**  
**Payback period**: $200 setup / $6,750 savings = **0.03 seasons** (1 month)

**Over 5 years**:
- **Before PANCAKE**: $6,750 × 2 seasons/year × 5 years = **$67,500**
- **With PANCAKE**: $200 setup + ($1,000/year × 5 years) = **$5,200**
- **Total savings**: **$62,300**

---

## Chapter 5: Technical Implementation

### GeoID Verification

```python
def verify_geoid_via_satellite(geoid: str) -> dict:
    """Verify GeoID matches actual field via satellite imagery"""
    
    # Get polygon from GeoID
    polygon = pancake.asset_registry.get_polygon(geoid)
    
    # Fetch recent satellite imagery (Sentinel-2)
    satellite_data = tap_adapter.fetch_data(
        vendor='terrapipe_ndvi',
        params={
            'geoid': geoid,
            'date': datetime.utcnow().strftime('%Y-%m-%d')
        }
    )
    
    # Compare polygon with satellite boundary
    satellite_boundary = extract_boundary(satellite_data)
    match_score = polygon_similarity(polygon, satellite_boundary)
    
    return {
        'geoid': geoid,
        'verified': match_score > 0.95,
        'match_score': match_score,
        'verification_date': datetime.utcnow().isoformat(),
        'satellite_source': 'Sentinel-2'
    }
```

### Deforestation Analysis

```python
def analyze_forest_cover(geoid: str, start_date: str = '2020-01-01') -> dict:
    """Analyze NDVI time-series to detect forest loss"""
    
    # Query NDVI data since 2020
    ndvi_data = pancake.query(
        f"Show me NDVI data for {geoid} from {start_date} to present",
        type_filter='imagery_sirup'
    )
    
    # Calculate forest cover (NDVI > 0.6 = forest)
    forest_cover = []
    for bite in ndvi_data:
        ndvi_mean = bite['Body']['sirup_data']['ndvi_stats']['mean']
        is_forest = ndvi_mean > 0.6
        forest_cover.append({
            'date': bite['Header']['timestamp'],
            'ndvi': ndvi_mean,
            'is_forest': is_forest
        })
    
    # Detect forest loss (NDVI drops below 0.6)
    forest_loss_dates = [
        entry['date'] for entry in forest_cover
        if not entry['is_forest'] and entry['date'] > '2020-12-31'
    ]
    
    return {
        'geoid': geoid,
        'deforestation_free': len(forest_loss_dates) == 0,
        'forest_loss_dates': forest_loss_dates,
        'current_ndvi': forest_cover[-1]['ndvi'] if forest_cover else None,
        'analysis_period': f"{start_date} to {datetime.utcnow().isoformat()}"
    }
```

### Report Generation

```python
def generate_pdf_report(eudr_data: dict) -> bytes:
    """Generate EUDR compliance PDF report"""
    
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "EUDR Compliance Report")
    c.drawString(100, 730, f"Cooperative: {eudr_data['cooperative']}")
    c.drawString(100, 710, f"Harvest Year: {eudr_data['harvest_year']}")
    
    # Farms table
    y = 680
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "Farm Verification:")
    y -= 20
    
    c.setFont("Helvetica", 10)
    for farm in eudr_data['farms']:
        status = "✓ Deforestation-Free" if farm['deforestation_free'] else "✗ Forest Loss Detected"
        c.drawString(120, y, f"GeoID: {farm['geoid'][:16]}... | {status}")
        y -= 15
    
    # Traceability chain
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "Traceability Chain:")
    y -= 20
    
    c.setFont("Helvetica", 10)
    for trace in eudr_data['traceability']:
        c.drawString(120, y, f"Farm: {trace['farm'][:16]}... | Harvests: {len(trace['harvests'])} | Processing: {len(trace['processing'])}")
        y -= 15
    
    # Cryptographic hash
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "Verification Hash:")
    c.setFont("Helvetica", 10)
    c.drawString(120, y - 15, eudr_data['cryptographic_hash'])
    
    c.save()
    buffer.seek(0)
    return buffer.read()
```

---

## Conclusion

**PANCAKE automates EUDR compliance**:
- ✅ **Geolocation**: GeoID verification via satellite imagery
- ✅ **Traceability**: MEAL threads (harvest → processing → export)
- ✅ **Deforestation-free proof**: NDVI time-series analysis (2020-present)
- ✅ **Due diligence**: Complete documentation (BITEs with GPS, timestamps, hashes)
- ✅ **Report generation**: Automated PDF (30 seconds)

**Cost savings**: $6,750 per export season → $0 (after setup)  
**Time savings**: 3 months → 30 seconds  
**Compliance rate**: 100% (immutable, cryptographically verified)

**José's comment**: "EUDR used to terrify me. Now it's automatic. PANCAKE made compliance simple."

**Next module**: FMIS Integration & Private Sector - How PANCAKE works with existing farm management systems.

---

**An AgStack Project | Powered by The Linux Foundation**

**Learn more**: https://agstack.org/pancake  
**GitHub**: https://github.com/agstack/pancake  
**License**: Apache 2.0 (Code) | CC BY 4.0 (Documentation)

