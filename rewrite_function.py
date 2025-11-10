#!/usr/bin/env python3
"""
Completely rewrite ask_pancake_enhanced function to fix all issues
"""

import json

# Read the notebook
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'r') as f:
    notebook = json.load(f)

# The corrected function
corrected_function = '''# Enhanced conversational AI with reasoning and timing
def print_enhanced_response(query: str, answer: str, timing: Dict, top_bites: List[Dict], scores: List[Dict]):
    """Pretty print conversational AI response with reasoning"""
    
    print("\\n" + "╔" + "="*98 + "╗")
    print(f"║ 🤖 CONVERSATIONAL AI QUERY{' '*70}║")
    print("╠" + "="*98 + "╣")
    print(f"║ ❓ {query[:92]:<92} ║")
    print("╚" + "="*98 + "╝")
    
    # Timing breakdown
    print(f"\\n⏱️  TIMING BREAKDOWN:")
    print(f"   Retrieval: {timing.get('retrieval', 0):.3f}s")
    print(f"   LLM Generation: {timing.get('generation', 0):.3f}s")
    print(f"   Total: {timing.get('total', 0):.3f}s")
    
    # Cost estimate (OpenAI pricing)
    input_tokens = timing.get('input_tokens', 0)
    output_tokens = timing.get('output_tokens', 0)
    cost = (input_tokens / 1000 * 0.0015) + (output_tokens / 1000 * 0.002)  # GPT-4 pricing
    print(f"   Estimated cost: ${cost:.4f} (input: {input_tokens}, output: {output_tokens} tokens)")
    
    # Top BITEs with similarity scores
    print(f"\\n📊 TOP RELEVANT BITEs (showing {len(top_bites)}):")
    for i, (bite, score_breakdown) in enumerate(zip(top_bites, scores), 1):
        print(f"\\n   {i}. {bite['Header']['type']} | {bite['Header']['timestamp'][:10]}")
        print(f"      Similarity Scores:")
        print(f"        Semantic:  {score_breakdown['semantic']:.3f}")
        print(f"        Spatial:   {score_breakdown['spatial']:.3f}")
        print(f"        Temporal:  {score_breakdown['temporal']:.3f}")
        print(f"        Combined:  {score_breakdown['combined']:.3f}")
    
    # AI Answer
    print(f"\\n💡 AI RESPONSE:")
    print("   " + "-"*96)
    # Pretty format the answer
    for line in answer.split('\\n'):
        print(f"   {line}")
    print("   " + "-"*96)

def ask_pancake_enhanced(query: str, days_back: int = 30, top_k: int = 5):
    """
    Enhanced conversational AI with reasoning chain and timing
    """
    import time
    
    timing = {}
    total_start = time.time()
    retrieval_start = time.time()
    
    # Step 1: RAG retrieval
    # Convert days_back to time_filter
    from datetime import datetime, timedelta
    cutoff_time = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + 'Z'
    time_filter = f">= '{cutoff_time}'"
    
    results = rag_query(query, top_k=top_k, time_filter=time_filter)
    
    timing['retrieval'] = time.time() - retrieval_start
    
    if not results:
        timing['generation'] = 0
        timing['total'] = time.time() - total_start
        timing['input_tokens'] = 0
        timing['output_tokens'] = 0
        return "No relevant data found.", timing, [], []
    
    # Extract top BITEs and compute score breakdowns
    top_bites = results  # rag_query returns list of bite dicts
    score_breakdowns = []
    
    for bite in results:
        # Get semantic distance from rag_query result
        semantic_dist = bite.get('semantic_distance', 1.0)
        # Convert distance to similarity (lower distance = higher similarity)
        sem_sim = max(0.0, 1.0 - semantic_dist)
        
        # Compute spatial and temporal similarities
        query_emb = get_embedding(query)
        
        # Spatial similarity (comparing bite's geoid with itself for now - could compare with query location)
        spat_sim = 1.0  # Default to 1.0 since we don't have a query GeoID
        
        # Temporal similarity (how recent is the BITE?)
        temp_sim = temporal_similarity(bite['Header']['timestamp'], datetime.utcnow().isoformat() + 'Z')
        
        # Combined score (weighted average)
        combined_score = (sem_sim * 0.5) + (spat_sim * 0.2) + (temp_sim * 0.3)
        
        score_breakdowns.append({
            'semantic': sem_sim,
            'spatial': spat_sim,
            'temporal': temp_sim,
            'combined': combined_score
        })
    
    # Step 2: Build context for LLM
    context = "Here is the relevant PANCAKE data:\\n\\n"
    for i, bite in enumerate(results, 1):
        context += f"{i}. {bite['Header']['type']} ({bite['Header']['timestamp'][:10]}):\\n"
        context += f"{json.dumps(bite['Body'], indent=2)}\\n\\n"
    
    # Step 3: Generate AI response
    generation_start = time.time()
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an agricultural AI assistant. Analyze the PANCAKE data and provide clear, actionable insights."},
                {"role": "user", "content": f"Query: {query}\\n\\n{context}\\n\\nPlease provide a comprehensive answer with reasoning."}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        answer = response.choices[0].message.content
        timing['generation'] = time.time() - generation_start
        timing['input_tokens'] = response.usage.prompt_tokens
        timing['output_tokens'] = response.usage.completion_tokens
        
    except Exception as e:
        answer = f"Error generating AI response: {e}"
        timing['generation'] = time.time() - generation_start
        timing['input_tokens'] = 0
        timing['output_tokens'] = 0
    
    timing['total'] = time.time() - total_start
    
    return answer, timing, top_bites, score_breakdowns

print("✓ Enhanced conversational AI functions defined")
'''

# Find and replace the cell
for i, cell in enumerate(notebook['cells']):
    source_str = ''.join(cell.get('source', []))
    if 'def ask_pancake_enhanced(' in source_str:
        print(f"Replacing cell {i} with corrected function")
        cell['source'] = [corrected_function]
        break

# Write back
with open('POC_Nov20_BITE_PANCAKE.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Function completely rewritten and fixed")



