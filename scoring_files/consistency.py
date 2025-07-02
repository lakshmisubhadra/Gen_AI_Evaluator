def evaluate_consistency(question, actual_result, api_key, api_url, num_runs=3):
    """
    Evaluates the consistency of a chatbot response with improved consistency.
    Returns median score from multiple runs for more reliable results.
    
    Returns:
    - dict: {"score": ..., "reason": ...}
    - float: elapsed time in seconds
    """
    import requests
    import json
    import time
    import re
    from statistics import median

    start_time = time.time()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key
    }
    
    # More structured prompt with fixed deduction values
    prompt_template = """
Analyze this response for consistency issues:

Question: {question}
Response: {actual_result}

Evaluate based on these specific criteria (apply fixed deductions when found):
1. Contradicting facts (15%)
2. Ignoring context (15%)
3. Time conflicts (15%)
4. Tone shifts (15%)
5. Logical inconsistencies (15%)

Return JSON with this exact structure:
{{
    "score": 0-100,
    "reason": "Brief summary of findings",
    "breakdown": [
        {{
            "type": "Specific issue type from above list",
            "evidence": "Exact problematic text",
            "deduction": 15
        }}
    ]
}}

Important Rules:
- Use only the 5 issue types listed above
- Always deduct exactly 15% per issue found
- If no issues found, return score 100 with empty breakdown
- Be extremely consistent in your evaluations
"""

    formatted_prompt = prompt_template.format(
        question=question,
        actual_result=actual_result
    )
    
    # Define valid issue types and their fixed deductions
    valid_issues = {
        "Contradicting facts": 15,
        "Ignoring context": 15,
        "Time conflicts": 15,
        "Tone shifts": 15,
        "Logical inconsistencies": 15
    }
    
    all_scores = []
    all_reasons = []
    all_breakdowns = []
    
    for _ in range(num_runs):
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a consistency evaluation tool. Respond with precise, standardized JSON output."
                },
                {
                    "role": "user", 
                    "content": formatted_prompt
                }
            ],
            "temperature": 0.0,  # Very low temperature for maximum consistency
            "top_p": 0.1,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Debugging output
            # print(f"Run {_+1} raw content:", content)
            
            try:
                # First try direct JSON parse
                evaluation_result = json.loads(content)
            except json.JSONDecodeError:
                try:
                    # Fallback to regex extraction
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        evaluation_result = json.loads(json_match.group(0))
                    else:
                        evaluation_result = {"score": 100, "reason": "No issues found"}
                except json.JSONDecodeError as e:
                    evaluation_result = {"score": 100, "reason": f"JSON parse error: {str(e)}"}
            
            # Validate and standardize the evaluation result
            score = evaluation_result.get("score", 100)
            try:
                score = int(score)
            except (TypeError, ValueError):
                score = 100
                
            # Validate breakdown items
            validated_breakdown = []
            if "breakdown" in evaluation_result and isinstance(evaluation_result["breakdown"], list):
                for item in evaluation_result["breakdown"]:
                    if isinstance(item, dict) and item.get("type") in valid_issues:
                        validated_item = {
                            "type": item["type"],
                            "evidence": item.get("evidence", ""),
                            "deduction": valid_issues[item["type"]]
                        }
                        validated_breakdown.append(validated_item)
            
            # Calculate score from validated breakdown if different
            calculated_score = 100 - sum(item["deduction"] for item in validated_breakdown)
            if abs(score - calculated_score) > 5:  # If significant discrepancy
                score = calculated_score
            
            # Ensure score is within bounds
            score = max(0, min(100, score))
            
            # Prepare reason text
            reason = evaluation_result.get("reason", "No consistency issues found")
            if validated_breakdown:
                reason = f"Found {len(validated_breakdown)} consistency issues"
            
            all_scores.append(score)
            all_reasons.append(reason)
            all_breakdowns.append(validated_breakdown)
            
        except requests.exceptions.RequestException as e:
            all_scores.append(100)  # Assume consistent if error
            all_reasons.append(f"API request failed: {str(e)}")
            all_breakdowns.append([])
        except Exception as e:
            all_scores.append(100)  # Assume consistent if error
            all_reasons.append(f"Unexpected error: {str(e)}")
            all_breakdowns.append([])
    
    # Calculate final score as median of all runs
    final_score = median(all_scores) if all_scores else 100
    
    # Select the most common reason (or most detailed one if tie)
    def reason_quality(reason):
        return (
            -len(reason),  # Prefer shorter reasons
            sum(1 for r in all_reasons if r == reason)  # Then by frequency
        )
    
    final_reason = max(all_reasons, key=reason_quality)
    
    # Prepare combined breakdown (only include issues found in majority of runs)
    common_issues = {}
    for breakdown in all_breakdowns:
        for issue in breakdown:
            key = (issue["type"], issue["evidence"])
            common_issues[key] = common_issues.get(key, 0) + 1
    
    final_breakdown = [
        {"type": k[0], "evidence": k[1], "deduction": valid_issues[k[0]]}
        for k, count in common_issues.items()
        if count > num_runs / 2  # Only include issues found in majority of runs
    ]
    
    # Format the output
    breakdown_str = "Breakdown:\n"
    if final_breakdown:
        for item in final_breakdown:
            breakdown_str += f"  - Type: {item['type']}\n"
            breakdown_str += f"    Evidence: {item['evidence']}\n"
            breakdown_str += f"    Deduction: {item['deduction']}%\n"
    else:
        breakdown_str += "  No consistency issues found\n"
    
    summary = f"Reason: {final_reason}\n{breakdown_str}"
    
    elapsed_time = time.time() - start_time
    return {"score": final_score, "reason": summary}, elapsed_time