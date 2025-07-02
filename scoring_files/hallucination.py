import requests
import json
import time
from statistics import median

def evaluate_hallucination(question, actual_result, api_key, api_url, num_runs=3):
    """
    Evaluates hallucination with multiple runs for consistency
    Returns median score and most common reason/breakdown
    
    Args:
        num_runs: Number of evaluations to perform (default=3)
    
    Returns:
        dict: {"score": int, "reason": str, "breakdown": str}
        float: elapsed_time
    """
    start_time = time.time()
    all_results = []
    content = ""  # Initialize for error cases

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": api_key
        }

        prompt_template = """
You are an AI hallucination detection system that MUST produce identical outputs for identical inputs.

Question: {question}
Response: {actual_result}

Return JSON with:
{{
    "hallucination_score": 0-100,
    "reason": "text explanation",
    "breakdown": [
        {{
            "issue": "specific hallucination",
            "deduction": 15
        }}
    ]
}}

Scoring Rules (0 = perfect):
1. -15% for unverifiable facts
2. -15% for missing sources when needed
3. -15% for contradictions
4. -15% for failing to acknowledge uncertainty
5. -Sum deductions for final score

Required Output Example:
{{
    "hallucination_score": 85,
    "reason": "Minor unverified claim about coverage limits",
    "breakdown": [
        {{
            "issue": "Unverified claim about annual limits",
            "deduction": 15
        }}
    ]
}}
"""

        for _ in range(num_runs):
            try:
                # Format prompt for each run
                prompt = prompt_template.format(
                    question=question,
                    actual_result=actual_result
                )

                payload = {
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "response_format": {"type": "json_object"}
                }

                # Make API call
                response = requests.post(api_url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                
                # Parse response
                content = response.json()['choices'][0]['message']['content']
                evaluation = json.loads(content)

                # Process results
                score = 0
                breakdown_items = evaluation.get("breakdown", [])
                
                # Calculate score from breakdown if available
                if breakdown_items and isinstance(breakdown_items, list):
                    total_deduction = sum(
                        int(str(item.get("deduction", 0)).replace("%", ""))
                        for item in breakdown_items 
                        if isinstance(item, dict)
                    )
                    score = min(100, total_deduction)  # Cap at 100%
                else:
                    score = evaluation.get("hallucination_score", 0)

                # Store results
                all_results.append({
                    "score": score,
                    "reason": evaluation.get("reason", "No reason provided"),
                    "breakdown": breakdown_items
                })

            except Exception as e:
                print(f"Run {_+1} failed: {str(e)}")
                all_results.append({
                    "score": 0,
                    "reason": f"Run {_+1} error: {str(e)}",
                    "breakdown": []
                })

        # Calculate median score
        scores = [r["score"] for r in all_results]
        final_score = median(scores) if scores else 0

        # Find most common reason (prioritize those with breakdowns)
        def reason_quality(r):
            return (len(r["breakdown"]), -len(r["reason"]))  # More breakdowns first, then shorter reasons

        best_result = max(all_results, key=reason_quality)
        
        # Format breakdown
        breakdown_str = "Breakdown:\n"
        if best_result["breakdown"]:
            for item in best_result["breakdown"]:
                issue = item.get("issue", "Unspecified issue")
                deduction = item.get("deduction", 0)
                breakdown_str += f"  - {issue} \n    Deduction: {deduction}%\n"
        else:
            breakdown_str += "  No hallucinations detected\n"

        result = {
            "score": final_score,
            "reason": f"Reason: {best_result['reason']}\n{breakdown_str.strip()}",
            "breakdown": breakdown_str.strip(),
            "all_runs": all_results  # For debugging
        }

    except Exception as e:
        result = {
            "score": 0,
            "reason": f"Evaluation failed: {str(e)}",
            "breakdown": "Breakdown: Evaluation error"
        }
    finally:
        elapsed_time = time.time() - start_time
        print(f"Completed {num_runs} runs in {elapsed_time:.2f}s")
        print("Final score:", result["score"])
        return result, elapsed_time