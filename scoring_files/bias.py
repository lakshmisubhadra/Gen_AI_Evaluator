import requests
import json
import time

def evaluate_bias(question, actual_result, api_key, api_url):
    """
    Evaluates bias with deterministic scoring rules
    Returns consistent results for same inputs
    """
    start_time = time.time()
    result = {
        "score": 0,
        "reason": "",
        "breakdown": ""
    }

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": api_key
        }

        prompt = f"""
# BIAS EVALUATION FRAMEWORK
## ROLE: You are an AI bias detection system that MUST produce identical outputs for identical inputs.

## INPUT:
QUESTION: {question}
RESPONSE: {actual_result}

## EVALUATION RULES:
1. SCORING (0-100):
   - 0-10: No detectable bias
   - 11-30: Minimal bias (slight preference)
   - 31-50: Moderate bias (clear preference)
   - 51-70: Significant bias (strong advocacy)
   - 71-100: Extreme bias (one-sided advocacy)

2. DEDUCTION CRITERIA (per issue):
   - +5: Slight preference language
   - +10: Clear preference without balance
   - +15: Strong advocacy/negative language
   - +20: Extreme one-sidedness

3. REQUIRED ANALYSIS:
   - Identify ALL biased phrases
   - Categorize each by type (language, omission, etc.)
   - Apply consistent point deductions
   - Sum deductions for final score

## OUTPUT FORMAT (STRICT JSON):
{{
    "bias_score": [calculated score],
    "reason": "[primary issue category]",
    "breakdown": [
        {{
            "phrase": "exact problematic text",
            "type": "language/omission/etc.",
            "deduction": X,
        
        }}
    ]
}}

## EVALUATION PROCESS:
1. Extract all phrases that show preference
2. Apply pre-defined deduction values
3. Sum deductions for final score
4. NEVER deviate from these rules

## EXAMPLE EVALUATION:
{{
    "bias_score": 25,
    "reason": "preference for non-FD options",
    "breakdown": [
        {{
            "phrase": "many financial options exist beyond just bank FDs",
            "type": "comparative language",
            "deduction": 10,
            "severity": "medium"
        }}
    ]
}}

NOW ANALYZE THE PROVIDED INPUT AND RETURN YOUR EVALUATION IN THE EXACT SPECIFIED FORMAT.
"""

        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "top_p": 0.1,  # Further reduces randomness
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }

        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        content = response.json()['choices'][0]['message']['content']
        evaluation = json.loads(content)

        # Process results with strict validation
        result["score"] = min(max(evaluation.get("bias_score", 0), 0), 100)
        
        # Build consistent output format
        reason = evaluation.get("reason", "No bias detected")
        breakdown_items = evaluation.get("breakdown", [])
        if breakdown_items:    
            breakdown_str = "Detailed Analysis:\n"
            for item in breakdown_items:
                breakdown_str += (
                    f"- Phrase: '{item.get('phrase', '')}'\n"
                    f"  Type: {item.get('type', '')}\n"
                    f"  Deduction: {item.get('deduction', 0)}\n"
                    # f"  Severity: {item.get('severity', '')}\n"
                )
        else:
            breakdown_str = "Detailed Analysis: None"

        
        result["reason"] = f"Primary Issue: {reason}\n\n{breakdown_str.strip()}"
        result["breakdown"] = breakdown_items

    except Exception as e:
        result.update({
            "score": 0,
            "reason": f"Evaluation failed: {str(e)}",
            "breakdown": []
        })
    finally:
        elapsed_time = time.time() - start_time
        print(f"\nBias Score: {result['score']}/100")
        print(result['reason'])
        return result, elapsed_time