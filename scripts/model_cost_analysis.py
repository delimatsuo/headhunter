#!/usr/bin/env python3
"""
Together AI Model Cost-Benefit Analysis for Contextual Intelligence
"""

def analyze_together_ai_models():
    """Analyze cost-benefit of different Together AI models for contextual skill inference"""
    
    print("🧠 TOGETHER AI MODEL COMPARISON FOR CONTEXTUAL INTELLIGENCE")
    print("=" * 70)
    
    # Model options from Together AI pricing
    models = [
        {
            'name': 'Llama 3.2 3B Instruct Turbo',
            'model_id': 'meta-llama/Llama-3.2-3B-Instruct-Turbo',
            'price_per_1m': 0.20,
            'status': 'CURRENT',
            'reasoning_quality': 'Good',
            'context_window': '128K',
            'best_for': 'Basic enhancement (Stage 1)'
        },
        {
            'name': 'Qwen2.5 Coder 32B',
            'model_id': 'Qwen/Qwen2.5-Coder-32B-Instruct', 
            'price_per_1m': 0.80,
            'status': 'RECOMMENDED',
            'reasoning_quality': 'Excellent',
            'context_window': '32K',
            'best_for': 'Contextual skill inference (Stage 2)'
        },
        {
            'name': 'Llama 3.1 70B Instruct Turbo',
            'model_id': 'meta-llama/Llama-3.1-70B-Instruct-Turbo',
            'price_per_1m': 0.88,
            'status': 'PREMIUM',
            'reasoning_quality': 'Superior',
            'context_window': '131K',
            'best_for': 'Complex contextual analysis'
        },
        {
            'name': 'Llama 3.1 405B Instruct Turbo', 
            'model_id': 'meta-llama/Llama-3.1-405B-Instruct-Turbo',
            'price_per_1m': 3.50,
            'status': 'ENTERPRISE',
            'reasoning_quality': 'Maximum',
            'context_window': '128K', 
            'best_for': 'Highest accuracy contextual intelligence'
        }
    ]
    
    # Assumptions for cost calculation
    tokens_per_basic_enhancement = 3000    # Stage 1: Current working well
    tokens_per_contextual_analysis = 2500  # Stage 2: New contextual intelligence
    candidates_per_month = 20000
    
    print(f"\n💼 BUSINESS ASSUMPTIONS:")
    print(f"   - Candidates per month: {candidates_per_month:,}")
    print(f"   - Tokens per basic enhancement: {tokens_per_basic_enhancement:,}")
    print(f"   - Tokens per contextual analysis: {tokens_per_contextual_analysis:,}")
    
    print(f"\n📊 MODEL ANALYSIS:")
    print("-" * 70)
    
    for model in models:
        print(f"\n🤖 {model['name']} ({model['status']})")
        print(f"   Model ID: {model['model_id']}")
        print(f"   Price: ${model['price_per_1m']}/1M tokens")
        print(f"   Reasoning Quality: {model['reasoning_quality']}")
        print(f"   Context Window: {model['context_window']}")
        
        # Cost calculations
        cost_per_candidate = (tokens_per_contextual_analysis * model['price_per_1m']) / 1000000
        monthly_cost = cost_per_candidate * candidates_per_month
        vs_current_multiplier = model['price_per_1m'] / 0.20
        
        print(f"   💰 Cost per candidate: ${cost_per_candidate:.4f}")
        print(f"   💰 Monthly cost (20k candidates): ${monthly_cost:.2f}")
        print(f"   📈 Cost vs current: {vs_current_multiplier:.1f}x")
        
        # Recommendations
        if model['status'] == 'CURRENT':
            print("   ✅ Currently working well for basic enhancement")
        elif model['status'] == 'RECOMMENDED':
            print("   🎯 RECOMMENDED for Stage 2 contextual intelligence")
            print("   🏆 Best cost-benefit for sophisticated reasoning")
        elif model['status'] == 'PREMIUM':
            print("   💎 Premium option for maximum contextual accuracy")
        elif model['status'] == 'ENTERPRISE':
            print("   👑 Enterprise-grade for mission-critical applications")
        
        print(f"   🎯 Best for: {model['best_for']}")
    
    print(f"\n🏗️ RECOMMENDED ARCHITECTURE:")
    print("-" * 40)
    print("📍 STAGE 1 - Basic Enhancement:")
    print("   Model: Llama 3.2 3B Instruct Turbo ($0.20/1M)")
    print("   Why: Current model working well, cost-effective")
    print("   Monthly cost: $12.00 (3000 tokens × 20k candidates)")
    
    print("\n📍 STAGE 2 - Contextual Intelligence:")
    print("   Model: Qwen2.5 Coder 32B ($0.80/1M)")  
    print("   Why: Excellent reasoning at 4x current cost")
    print("   Monthly cost: $40.00 (2500 tokens × 20k candidates)")
    print("   🎯 SWEET SPOT for contextual analysis")
    
    print("\n📈 TOTAL RECOMMENDED COST:")
    stage_1_cost = (3000 * 0.20 * 20000) / 1000000
    stage_2_cost = (2500 * 0.80 * 20000) / 1000000
    total_cost = stage_1_cost + stage_2_cost
    
    print(f"   - Stage 1 (Basic): ${stage_1_cost:.2f}/month")
    print(f"   - Stage 2 (Contextual): ${stage_2_cost:.2f}/month") 
    print(f"   - Total: ${total_cost:.2f}/month")
    print(f"   - Per candidate: ${total_cost/20000:.4f}")
    
    print(f"\n🎯 WHY QWEN2.5 CODER 32B FOR CONTEXTUAL INTELLIGENCE:")
    print("   ✅ Specialized for technical/coding contexts")
    print("   ✅ 32B parameters = sophisticated reasoning")
    print("   ✅ 4x current cost = significant quality improvement")
    print("   ✅ Still affordable for 20k candidates/month")
    print("   ✅ Perfect for company/industry pattern recognition")
    
    print(f"\n💡 ALTERNATIVE CONFIGURATIONS:")
    print("   🥉 Budget: Keep 3B for both stages ($24/month)")
    print("   🥈 Balanced: 3B + Qwen2.5 32B ($52/month) ← RECOMMENDED")
    print("   🥇 Premium: 3B + Llama 70B ($56/month)")
    print("   👑 Enterprise: 3B + Llama 405B ($187/month)")

if __name__ == "__main__":
    analyze_together_ai_models()