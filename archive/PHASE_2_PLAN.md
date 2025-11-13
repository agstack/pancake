# Phase 2: Performance & Visualization Enhancements

**Status**: 🚧 IN PROGRESS  
**Started**: November 1, 2024  
**Target**: Enhanced demo experience

---

## Objectives

### 1. BITE Loader Optimization ✅ COMPLETE
- ✅ Batch embedding generation (10-50x faster)
- ✅ Progress indicators
- ✅ Performance metrics display
- ✅ Expected: 100 BITEs in <1 minute (vs 16+ minutes)

### 2. Conversational AI Enhancement 🚧 IN PROGRESS
- [ ] Pretty print responses (markdown formatting, colors)
- [ ] Show reasoning chain (retrieved BITEs, similarity scores)
- [ ] Display query timing (total, retrieval, generation breakdown)
- [ ] Token usage statistics (for cost tracking)

### 3. NDVI Geospatial Visualization 🚧 IN PROGRESS
- [ ] NDVI raster heatmap (matplotlib/seaborn)
- [ ] Highlight areas of interest (threshold-based binning)
- [ ] Field boundary overlay (GeoJSON/WKT)
- [ ] Color scale (red=low, yellow=medium, green=high)
- [ ] Export capability (save as PNG for reports)

---

## Implementation Plan

### Task 1: Enhanced Conversational AI Output

**Current**: Plain text response
```
"Based on the retrieved data, coffee rust was observed..."
```

**Target**: Rich formatted output
```
╔══════════════════════════════════════════════════════════╗
║        PANCAKE Conversational AI Response               ║
╚══════════════════════════════════════════════════════════╝

Question: "What pest issues have been observed?"

📊 Retrieved Context:
  • 3 relevant BITEs found
  • Time range: Last 30 days
  • Spatial filter: field-abc (+ 50km radius)

🔍 Reasoning Chain:
  1. coffee_rust observation (2024-10-15) - Similarity: 0.92
     → Semantic: 0.95 (keyword match)
     → Spatial: 0.90 (0.5km away)
     → Temporal: 0.91 (16 days ago)
  
  2. leaf_miner activity (2024-10-20) - Similarity: 0.78
     → Semantic: 0.85 (related pest)
     → Spatial: 0.75 (5km away)
     → Temporal: 0.75 (11 days ago)
  
  3. soil_health observation (2024-10-25) - Similarity: 0.65
     → Semantic: 0.70 (indirect relevance)
     → Spatial: 0.62 (12km away)
     → Temporal: 0.63 (6 days ago)

💬 AI Response:
Based on recent field observations, two significant pest issues 
have been identified:

1. Coffee Rust (Hemileia vastatrix):
   - Observed on October 15, 2024
   - Severity: Moderate (30% coverage)
   - Location: Field-abc (primary field)
   - Recommendation: Copper-based fungicide within 48 hours

2. Leaf Miner Activity:
   - Detected on October 20, 2024
   - Severity: Low but increasing
   - Location: Adjacent field (5km north)
   - Recommendation: Monitor weekly, consider pheromone traps

⏱️  Query Performance:
  • Retrieval: 85ms (multi-pronged RAG)
  • LLM Generation: 1,240ms (GPT-4)
  • Total: 1,325ms

💰 Cost Estimate:
  • Prompt tokens: 450 ($0.0045)
  • Completion tokens: 180 ($0.0054)
  • Total: $0.0099

═══════════════════════════════════════════════════════════
```

### Task 2: NDVI Raster Visualization

**Function Signature**:
```python
def visualize_ndvi_bite(bite: Dict[str, Any], threshold_low: float = 0.3, 
                        threshold_high: float = 0.6, save_path: str = None):
    """
    Visualize NDVI data from a SIRUP BITE with highlighted areas
    
    Args:
        bite: BITE containing NDVI imagery data
        threshold_low: Below this = stressed vegetation (red)
        threshold_high: Above this = healthy vegetation (green)
        save_path: Optional path to save PNG
    """
```

**Output**:
```
┌─────────────────────────────────────────────┐
│  NDVI Heatmap - Field ABC (2024-10-07)     │
├─────────────────────────────────────────────┤
│                                             │
│   [Color-coded raster map showing:]         │
│   - Field boundary (black outline)          │
│   - Low NDVI areas (red) - stressed        │
│   - Medium NDVI (yellow) - recovering      │
│   - High NDVI (green) - healthy            │
│                                             │
│   Statistics:                               │
│   • Mean NDVI: 0.52                         │
│   • Stressed area: 15% (red zones)          │
│   • Healthy area: 65% (green zones)         │
│   • Alert: NW corner shows stress           │
│                                             │
└─────────────────────────────────────────────┘

📊 Binned Analysis:
  Low (0.0-0.3):  15% - 🔴 ALERT: Possible disease/drought
  Med (0.3-0.6):  20% - 🟡 CAUTION: Monitor closely
  High (0.6-1.0): 65% - 🟢 HEALTHY: Normal growth

💡 Recommendations:
  • Investigate red zones (NW corner) for pests/disease
  • Increase irrigation in yellow zones
  • Continue current management for green zones
```

---

## Code Snippets

### Enhanced ask_pancake() Function

```python
def ask_pancake_enhanced(question: str, geoid: str = None, days_back: int = 30, 
                         verbose: bool = True) -> Dict[str, Any]:
    """
    Enhanced conversational AI with reasoning display
    
    Returns:
        {
            'answer': str,
            'reasoning': List[Dict],
            'timing': Dict[str, float],
            'tokens': Dict[str, int],
            'cost': float
        }
    """
    import time
    start_time = time.time()
    
    # Retrieval phase
    retrieval_start = time.time()
    relevant_bites = rag_query(question, top_k=10, geoid_filter=geoid, 
                                time_filter=time_filter, return_scores=True)
    retrieval_time = time.time() - retrieval_start
    
    if not relevant_bites:
        return {'answer': "No relevant data found", 'timing': {}, 'tokens': {}}
    
    # Build reasoning chain
    reasoning = []
    for bite, scores in relevant_bites[:5]:  # Top 5
        reasoning.append({
            'bite_id': bite['Header']['id'],
            'type': bite['Header']['type'],
            'date': bite['Header']['timestamp'][:10],
            'similarity': scores['total'],
            'semantic': scores['semantic'],
            'spatial': scores['spatial'],
            'temporal': scores['temporal'],
            'location': f"{scores['distance_km']:.1f}km away"
        })
    
    # LLM generation phase
    llm_start = time.time()
    context = build_context(relevant_bites)
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an agricultural AI assistant..."},
            {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}"}
        ]
    )
    
    answer = response.choices[0].message.content
    llm_time = time.time() - llm_start
    
    # Metrics
    total_time = time.time() - start_time
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens
    cost = (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)  # GPT-4 pricing
    
    result = {
        'answer': answer,
        'reasoning': reasoning,
        'timing': {
            'retrieval_ms': retrieval_time * 1000,
            'llm_ms': llm_time * 1000,
            'total_ms': total_time * 1000
        },
        'tokens': {
            'prompt': prompt_tokens,
            'completion': completion_tokens,
            'total': prompt_tokens + completion_tokens
        },
        'cost': cost
    }
    
    if verbose:
        print_enhanced_response(result, question)
    
    return result

def print_enhanced_response(result: Dict, question: str):
    """Pretty print the enhanced response"""
    print("\n" + "="*70)
    print("    PANCAKE Conversational AI Response")
    print("="*70)
    print(f"\n📝 Question: \"{question}\"\n")
    
    print(f"🔍 Retrieved {len(result['reasoning'])} relevant BITEs:\n")
    for i, r in enumerate(result['reasoning'], 1):
        print(f"  {i}. {r['type']} ({r['date']}) - Similarity: {r['similarity']:.3f}")
        print(f"     → Semantic: {r['semantic']:.3f} | Spatial: {r['spatial']:.3f} | Temporal: {r['temporal']:.3f}")
        print(f"     → Location: {r['location']}\n")
    
    print("💬 AI Response:")
    print("-" * 70)
    print(result['answer'])
    print("-" * 70)
    
    print(f"\n⏱️  Performance:")
    print(f"  • Retrieval: {result['timing']['retrieval_ms']:.0f}ms")
    print(f"  • LLM Generation: {result['timing']['llm_ms']:.0f}ms")
    print(f"  • Total: {result['timing']['total_ms']:.0f}ms")
    
    print(f"\n💰 Cost:")
    print(f"  • Tokens: {result['tokens']['prompt']} prompt + {result['tokens']['completion']} completion = {result['tokens']['total']} total")
    print(f"  • Estimated cost: ${result['cost']:.4f}")
    
    print("="*70 + "\n")
```

### NDVI Visualization Function

```python
def visualize_ndvi_bite(bite: Dict[str, Any], threshold_low: float = 0.3, 
                        threshold_high: float = 0.6, figsize=(12, 8), 
                        save_path: str = None):
    """
    Visualize NDVI raster from SIRUP BITE with highlighted stress areas
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import LinearSegmentedColormap
    import numpy as np
    
    # Extract NDVI data from BITE
    body = bite['Body']
    ndvi_img = body.get('ndvi_image', {})
    features = ndvi_img.get('features', [])
    
    if not features:
        print("⚠️  No NDVI data found in BITE")
        return
    
    # Extract NDVI values and coordinates
    ndvi_values = []
    coordinates = []
    
    for feature in features:
        props = feature.get('properties', {})
        geom = feature.get('geometry', {})
        
        if 'NDVI' in props and geom.get('type') == 'Point':
            ndvi_values.append(props['NDVI'])
            coords = geom['coordinates']
            coordinates.append(coords)
    
    if not ndvi_values:
        print("⚠️  No valid NDVI values found")
        return
    
    ndvi_array = np.array(ndvi_values)
    coords_array = np.array(coordinates)
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
    
    # Plot 1: NDVI Heatmap
    scatter = ax1.scatter(coords_array[:, 0], coords_array[:, 1], 
                          c=ndvi_array, cmap='RdYlGn', 
                          s=100, alpha=0.7, edgecolors='black', linewidth=0.5)
    
    ax1.set_title(f"NDVI Heatmap - {bite['Header']['geoid'][:16]}...\n{bite['Header']['timestamp'][:10]}", 
                  fontsize=14, fontweight='bold')
    ax1.set_xlabel("Longitude")
    ax1.set_ylabel("Latitude")
    
    # Colorbar
    cbar = plt.colorbar(scatter, ax=ax1)
    cbar.set_label('NDVI Value', rotation=270, labelpad=20)
    
    # Add threshold lines
    ax1.axhline(y=threshold_low, color='red', linestyle='--', alpha=0.5, label=f'Low threshold ({threshold_low})')
    ax1.axhline(y=threshold_high, color='green', linestyle='--', alpha=0.5, label=f'High threshold ({threshold_high})')
    
    # Plot 2: Binned Analysis
    low_mask = ndvi_array < threshold_low
    med_mask = (ndvi_array >= threshold_low) & (ndvi_array < threshold_high)
    high_mask = ndvi_array >= threshold_high
    
    low_pct = (low_mask.sum() / len(ndvi_array)) * 100
    med_pct = (med_mask.sum() / len(ndvi_array)) * 100
    high_pct = (high_mask.sum() / len(ndvi_array)) * 100
    
    # Highlight stressed areas
    if low_mask.any():
        ax1.scatter(coords_array[low_mask, 0], coords_array[low_mask, 1], 
                   s=200, facecolors='none', edgecolors='red', linewidths=3,
                   label='Stressed areas')
    
    ax1.legend(loc='upper right')
    
    # Bar chart
    categories = ['Low\n(Stressed)', 'Medium\n(Recovering)', 'High\n(Healthy)']
    percentages = [low_pct, med_pct, high_pct]
    colors = ['#d62728', '#ffcc00', '#2ca02c']
    
    bars = ax2.bar(categories, percentages, color=colors, alpha=0.7, edgecolor='black')
    ax2.set_ylabel('Percentage of Area (%)', fontsize=12)
    ax2.set_title('NDVI Distribution', fontsize=14, fontweight='bold')
    ax2.set_ylim(0, 100)
    
    # Add percentage labels
    for bar, pct in zip(bars, percentages):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{pct:.1f}%', ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved to {save_path}")
    
    plt.show()
    
    # Print statistics
    print("\n" + "="*60)
    print("📊 NDVI Analysis Summary")
    print("="*60)
    print(f"Field: {bite['Header']['geoid'][:16]}...")
    print(f"Date: {bite['Header']['timestamp'][:10]}")
    print(f"\nStatistics:")
    print(f"  • Mean NDVI: {np.mean(ndvi_array):.3f}")
    print(f"  • Std Dev: {np.std(ndvi_array):.3f}")
    print(f"  • Min: {np.min(ndvi_array):.3f}")
    print(f"  • Max: {np.max(ndvi_array):.3f}")
    print(f"\nArea Distribution:")
    print(f"  🔴 Low (0-{threshold_low}): {low_pct:.1f}% - {'⚠️  ALERT: Investigate stress' if low_pct > 10 else '✓ Normal'}")
    print(f"  🟡 Medium ({threshold_low}-{threshold_high}): {med_pct:.1f}% - {'⚠️  CAUTION: Monitor' if med_pct > 30 else '✓ Normal'}")
    print(f"  🟢 High ({threshold_high}-1.0): {high_pct:.1f}% - ✓ Healthy")
    
    if low_pct > 15:
        print(f"\n💡 Recommendation: {low_pct:.1f}% of field shows stress. Investigate for:")
        print("   • Pest/disease presence")
        print("   • Water stress (check irrigation)")
        print("   • Nutrient deficiency")
    
    print("="*60 + "\n")
```

---

## Status

- ✅ Phase 1 Complete: Basic POC working
- ✅ BITE Loader Optimized: 10-50x faster
- 🚧 Conversational AI Enhancement: Functions designed, ready to implement
- 🚧 NDVI Visualization: Functions designed, ready to implement

**Next**: Implement enhanced functions in notebook and test

