# Module 6: Multi-Pronged RAG Query Engine
## Semantic + Spatial + Temporal Search for Agricultural Intelligence

**An AgStack Project of The Linux Foundation**

**Episode**: Module 6 of 10  
**Duration**: ~25 minutes  
**Prerequisites**: Episode 0, Module 1 (PANCAKE Core), Module 2 (BITE)  
**Technical Level**: Intermediate to Advanced

---

## Introduction

In Module 1, we introduced PANCAKE's multi-pronged RAG architecture. Now, let's dive deep into how it works—combining semantic understanding, spatial proximity, and temporal relevance to answer agricultural questions.

**What you'll learn:**
- What is Multi-Pronged RAG? (semantic + spatial + temporal)
- Semantic similarity (vector embeddings, pgvector)
- Spatial similarity (GeoID distance, S2 geometry)
- Temporal similarity (time decay, recency weighting)
- Combined scoring (weighted fusion)
- Conversational AI integration (LLM synthesis)
- Real-world query examples (from POC)

**Who this is for:**
- AI engineers building RAG systems
- Data scientists optimizing search relevance
- Backend developers implementing query engines
- Product managers designing conversational interfaces

---

## Chapter 1: What is Multi-Pronged RAG?

### Traditional RAG (Single-Pronged)

**Standard RAG** (Retrieval-Augmented Generation):
1. **Query**: "What pests have been observed?"
2. **Retrieval**: Semantic search (vector similarity)
3. **Generation**: LLM synthesizes answer from retrieved documents

**Problem**: Only considers **semantic similarity** (what the query means)

**Example failure**:
- Query: "What pests in Field A last week?"
- RAG retrieves: Pest observation from Field B (100km away, 6 months ago)
- **Why?** High semantic similarity ("pest" matches), but wrong location and time

### Multi-Pronged RAG (PANCAKE Innovation)

**PANCAKE RAG** searches **three dimensions simultaneously**:

1. **Semantic**: What does the query mean? (vector embeddings)
2. **Spatial**: How close is the location? (GeoID distance)
3. **Temporal**: How recent is the data? (time decay)

**Result**: Retrieves BITEs that are:
- ✅ Semantically relevant (matches query meaning)
- ✅ Spatially relevant (near target location)
- ✅ Temporally relevant (recent data)

---

## Chapter 2: Semantic Similarity (Vector Embeddings)

### How It Works

**Step 1**: Generate embedding for query
```python
import openai

def get_embedding(text: str) -> list[float]:
    """Generate 1536-dim embedding via OpenAI"""
    response = openai.Embedding.create(
        model="text-embedding-3-small",
        input=text
    )
    return response['data'][0]['embedding']

query = "What pests have been observed in coffee fields?"
query_embedding = get_embedding(query)
# Output: [0.0234, -0.0156, 0.0891, ...] (1536 dimensions)
```

**Step 2**: Compare with BITE embeddings (pgvector)
```sql
SELECT 
    id, geoid, timestamp, type, body,
    embedding <=> %s::vector AS distance
FROM bites
WHERE embedding IS NOT NULL
ORDER BY distance
LIMIT 10;
```

**Step 3**: Convert distance to similarity
```python
# Cosine distance: 0 = identical, 2 = opposite
# Similarity: 1.0 = identical, 0.0 = opposite
semantic_similarity = 1.0 - (distance / 2.0)
```

### Example

**Query**: "coffee rust disease"

**Top 3 semantic matches**:
1. BITE: "Coffee rust observed in Field A" (distance: 0.12, similarity: 0.94)
2. BITE: "Fungal disease outbreak" (distance: 0.18, similarity: 0.91)
3. BITE: "Leaf spot disease" (distance: 0.25, similarity: 0.88)

**Notice**: All semantically relevant, but no spatial/temporal filtering yet.

---

## Chapter 3: Spatial Similarity (GeoID Distance)

### How It Works

**Step 1**: Lookup GeoID coordinates (from Asset Registry)
```python
def get_geoid_coords(geoid: str) -> tuple[float, float]:
    """Get lat/lon for GeoID"""
    # Query Asset Registry or cache
    return (4.6, -75.5)  # Example: Colombia coffee field
```

**Step 2**: Calculate distance (Haversine formula)
```python
from math import radians, sin, cos, sqrt, atan2

def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """Calculate distance in km between two lat/lon points"""
    R = 6371  # Earth radius in km
    
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

target_coords = get_geoid_coords("field-abc")  # (4.6, -75.5)
bite_coords = get_geoid_coords("field-xyz")    # (4.7, -75.4)

distance_km = haversine_distance(
    target_coords[0], target_coords[1],
    bite_coords[0], bite_coords[1]
)
# Output: 11.1 km
```

**Step 3**: Convert distance to similarity (exponential decay)
```python
import math

def spatial_similarity(target_geoid: str, bite_geoid: str) -> float:
    """Calculate spatial similarity (exponential decay based on distance)"""
    target_coords = get_geoid_coords(target_geoid)
    bite_coords = get_geoid_coords(bite_geoid)
    
    distance_km = haversine_distance(
        target_coords[0], target_coords[1],
        bite_coords[0], bite_coords[1]
    )
    
    # Exponential decay: same location = 1.0, 10km away = 0.37, 50km = 0.007
    return math.exp(-distance_km / 10.0)
```

### Example

**Target**: Field A (4.6°N, 75.5°W)

**Spatial similarity scores**:
1. Field A (same location): 1.0
2. Field B (5km away): 0.61
3. Field C (20km away): 0.14
4. Field D (100km away): 0.00005

**Notice**: Exponential decay means nearby fields are much more relevant than distant ones.

---

## Chapter 4: Temporal Similarity (Time Decay)

### How It Works

**Step 1**: Calculate time delta
```python
from datetime import datetime, timedelta

def temporal_similarity(target_time: datetime, bite_time: datetime) -> float:
    """Calculate temporal similarity (exponential decay based on time delta)"""
    delta_days = abs((target_time - bite_time).total_seconds() / 86400)
    
    # Exponential decay: same day = 1.0, 7 days = 0.37, 30 days = 0.02
    return math.exp(-delta_days / 7.0)
```

### Example

**Target time**: March 15, 2025

**Temporal similarity scores**:
1. March 15, 2025 (same day): 1.0
2. March 10, 2025 (5 days ago): 0.49
3. March 1, 2025 (14 days ago): 0.14
4. February 1, 2025 (42 days ago): 0.003

**Notice**: Recent data is exponentially more relevant than old data.

---

## Chapter 5: Combined Scoring (Weighted Fusion)

### Multi-Pronged RAG Function

```python
def multi_pronged_rag(
    query: str,
    target_geoid: str = None,
    target_time: datetime = None,
    top_k: int = 10,
    weights: dict = {'semantic': 0.33, 'spatial': 0.33, 'temporal': 0.33}
) -> list[dict]:
    """
    Multi-pronged RAG retrieval
    
    Args:
        query: Natural language query
        target_geoid: Optional GeoID for spatial filtering
        target_time: Optional timestamp for temporal filtering (default: now)
        top_k: Number of results to return
        weights: Similarity weights (must sum to 1.0)
    
    Returns:
        List of BITEs with combined similarity scores
    """
    # Default to current time if not specified
    if target_time is None:
        target_time = datetime.utcnow()
    
    # Step 1: Semantic search (retrieve top 100 candidates)
    semantic_results = semantic_similarity_search(query, top_k=100)
    
    # Step 2: Rerank with spatial + temporal
    scored_results = []
    for bite in semantic_results:
        scores = {
            'semantic': bite['semantic_similarity']
        }
        
        # Spatial similarity (if target_geoid provided)
        if target_geoid:
            scores['spatial'] = spatial_similarity(target_geoid, bite['geoid'])
        else:
            scores['spatial'] = 1.0  # No spatial filtering
        
        # Temporal similarity
        scores['temporal'] = temporal_similarity(target_time, bite['timestamp'])
        
        # Combined score
        combined_score = (
            weights['semantic'] * scores['semantic'] +
            weights['spatial'] * scores['spatial'] +
            weights['temporal'] * scores['temporal']
        )
        
        bite['scores'] = scores
        bite['combined_score'] = combined_score
        scored_results.append(bite)
    
    # Step 3: Sort by combined score and return top_k
    scored_results.sort(key=lambda x: x['combined_score'], reverse=True)
    return scored_results[:top_k]
```

### Weight Tuning

**Default weights** (equal importance):
```python
weights = {
    'semantic': 0.33,
    'spatial': 0.33,
    'temporal': 0.33
}
```

**Location-focused query** (e.g., "What happened in Field A?"):
```python
weights = {
    'semantic': 0.20,
    'spatial': 0.60,  # Emphasize location
    'temporal': 0.20
}
```

**Recent events query** (e.g., "What happened last week?"):
```python
weights = {
    'semantic': 0.20,
    'spatial': 0.20,
    'temporal': 0.60  # Emphasize recency
}
```

**General knowledge query** (e.g., "What is coffee rust?"):
```python
weights = {
    'semantic': 0.70,  # Emphasize meaning
    'spatial': 0.15,
    'temporal': 0.15
}
```

---

## Chapter 6: Conversational AI Integration

### Generate Answer with LLM

```python
def ask_pancake(
    query: str,
    target_geoid: str = None,
    days_back: int = 30,
    top_k: int = 5
) -> str:
    """
    Conversational AI query with multi-pronged RAG
    
    Args:
        query: Natural language question
        target_geoid: Optional field/location context
        days_back: How many days to search (temporal filter)
        top_k: Number of BITEs to retrieve for context
    
    Returns:
        AI-generated answer based on retrieved BITEs
    """
    # Calculate target time (days_back from now)
    target_time = datetime.utcnow() - timedelta(days=days_back)
    
    # Multi-pronged RAG retrieval
    results = multi_pronged_rag(
        query=query,
        target_geoid=target_geoid,
        target_time=target_time,
        top_k=top_k
    )
    
    # Build context for LLM
    context = "Here is relevant agricultural data from PANCAKE:\n\n"
    for i, bite in enumerate(results, 1):
        context += f"{i}. {bite['type']} ({bite['timestamp'].isoformat()}):\n"
        context += f"   Location: {bite['geoid']}\n"
        context += f"   Data: {json.dumps(bite['body'], indent=2)}\n"
        context += f"   Relevance scores: Semantic={bite['scores']['semantic']:.2f}, "
        context += f"Spatial={bite['scores']['spatial']:.2f}, "
        context += f"Temporal={bite['scores']['temporal']:.2f}\n\n"
    
    # Call LLM
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are an agricultural AI assistant. Answer questions based on the provided PANCAKE data. Be specific, cite data, and explain your reasoning."
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}"
            }
        ],
        temperature=0.3  # Lower = more factual
    )
    
    return response['choices'][0]['message']['content']
```

### Example Query

```python
answer = ask_pancake(
    query="What pest issues have been observed in the coffee fields recently?",
    target_geoid="field-abc",  # Focus on field-abc and nearby
    days_back=14,              # Last 2 weeks
    top_k=5                    # Top 5 most relevant BITEs
)

print(answer)
```

**Output**:
```
Based on recent observations from PANCAKE, three pest issues have been identified 
in the coffee fields:

1. Coffee rust (Hemileia vastatrix) - Moderate severity
   - Observed in Field-ABC (March 12-15)
   - Also detected in Field-C (nearby, March 14)
   - Affected 30% of plants in Field-ABC
   
2. Aphid infestation - Low severity
   - Observed in Field-B (March 10)
   - Minor population, natural predators present
   
3. Leaf miners - Trace amounts
   - Observed in Field-A (March 8)
   - Below treatment threshold

Weather data shows high humidity (85%+) during March 10-15, which correlates 
with fungal disease spread (coffee rust). Satellite imagery (NDVI) confirms 
vegetation stress in Field-ABC, declining from 0.75 to 0.62 during the outbreak period.

Recommendation: Prioritize fungicide application for coffee rust in Field-ABC and Field-C. 
Monitor Field-B for aphid population growth. No action needed for leaf miners at this time.
```

**Notice how the AI**:
- Retrieved BITEs from multiple sources (observations, weather sensors, satellite data)
- Correlated spatial patterns (rust in Field-ABC and nearby Field-C)
- Identified temporal correlation (humidity → fungal disease)
- Provided actionable recommendations (spray Field-ABC and Field-C, monitor Field-B)

---

## Chapter 7: Performance Characteristics

### Benchmarks (From POC)

| Operation | Latency | Notes |
|-----------|---------|-------|
| **Semantic search** (100K BITEs) | 45-60ms | pgvector IVFFlat index |
| **Spatial lookup** (GeoID → coords) | <1ms | Cached in memory |
| **Temporal calculation** | <0.1ms | Simple math |
| **Multi-pronged RAG** (rerank 100 → 10) | 80-120ms | Includes all three dimensions |
| **LLM synthesis** (GPT-4) | 2-5 seconds | Network + generation |

### Optimization Strategies

**1. Cache GeoID coordinates**
```python
# In-memory cache (LRU, 10K entries)
@lru_cache(maxsize=10000)
def get_geoid_coords(geoid: str) -> tuple[float, float]:
    # Query Asset Registry or database
    ...
```

**2. Batch embedding generation**
```python
# Generate embeddings for 100 BITEs at once (vs 100 API calls)
embeddings = openai.Embedding.create(
    model="text-embedding-3-small",
    input=[bite_text for bite in bites]  # Batch
)
```

**3. Pre-filter by GeoID (if provided)**
```sql
-- If target_geoid provided, filter before semantic search
SELECT * FROM bites
WHERE geoid = %s  -- Pre-filter
AND embedding <=> %s::vector < 0.5  -- Semantic search
ORDER BY distance
LIMIT 100;
```

**4. Temporal pre-filter**
```sql
-- If days_back provided, filter before semantic search
SELECT * FROM bites
WHERE timestamp >= NOW() - INTERVAL '%s days'  -- Pre-filter
AND embedding <=> %s::vector < 0.5
ORDER BY distance
LIMIT 100;
```

---

## Conclusion

**Multi-Pronged RAG enables PANCAKE to answer agricultural questions with unprecedented accuracy**:
- ✅ **Semantic**: Understands query meaning (vector embeddings)
- ✅ **Spatial**: Finds relevant locations (GeoID distance)
- ✅ **Temporal**: Prioritizes recent data (time decay)
- ✅ **Combined**: Weighted fusion for optimal relevance
- ✅ **Conversational**: LLM synthesizes natural language answers

**The result**: "ChatGPT for spatio-temporal farm data" - ask questions in natural language, get answers based on your fields, your time, your context.

**Next module**: EUDR Compliance for Coffee - Real-world regulatory use case.

---

**An AgStack Project | Powered by The Linux Foundation**

**Learn more**: https://agstack.org/pancake  
**GitHub**: https://github.com/agstack/pancake  
**License**: Apache 2.0 (Code) | CC BY 4.0 (Documentation)

