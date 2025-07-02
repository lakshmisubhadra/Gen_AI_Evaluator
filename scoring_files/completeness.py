import requests
import json
import time

def evaluate_completeness(question, actual_result, api_key, api_url):
    """
    Evaluates response completeness with guaranteed breakdown display
    Returns:
    - dict: {"score": int, "reason": str, "breakdown": str}
    - float: elapsed_time
    """
    start_time = time.time()
    result = {
        "score": 0,
        "reason": "Evaluation initialization",
        "breakdown": "Breakdown: None"  # Initialize with default
    }

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": api_key
        }

        prompt = f"""
Analyze this insurance response for completeness:

Question: {question}
Response: {actual_result}

Return JSON with these EXACT fields:
{{
    "score": 0-100,
    "reason": "text explanation",
    "breakdown": [
        {{
            "missing": "specific missing element",
            "deduction": 15
        }}
    ]
}}

Scoring Rules:
1. 100% = Perfect response
2. -15% per missing element
3. -15% for vague statements
4. -100% if completely irrelevant

Required Output Example:
{{
    "score": 70,
    "reason": "Missing deductible information",
    "breakdown": [
        {{
            "missing": "Annual deductible amount",
            "deduction": 15
        }},
        {{
            "missing": "Per-claim maximum",
            "deduction": 15
        }}
    ]
}}
"""

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
        # Calculate score from breakdown if available
        breakdown_items = evaluation.get("breakdown", [])
        if breakdown_items and isinstance(breakdown_items, list):
            total_deduction = 0
            for item in breakdown_items:
                deduction = item.get("deduction", 0)
                try:
                    total_deduction += int(str(deduction).replace("%", ""))
                except Exception:
                    pass
            result["score"] = max(0, 100 - total_deduction)
        else:
            result["score"] = evaluation.get("score", 0)
        result["reason"] = f"Reason: {evaluation.get('reason', 'No reason provided')}"
        
        # Ensure breakdown is always properly formatted
        breakdown_items = evaluation.get("breakdown", [])
        if breakdown_items:
            breakdown_str = "Breakdown:\n"
            for item in breakdown_items:
                missing = item.get("missing", "Unspecified missing element")
                deduction = item.get("deduction", 0)
                breakdown_str += f"  - {missing} (Deduction: {deduction}%)\n"
            result["breakdown"] = breakdown_str.strip()
        else:
            result["breakdown"] = "Breakdown: None"

    except requests.exceptions.RequestException as e:
        result.update({
            "reason": f"Reason: API Error - {str(e)}",
            "breakdown": "Breakdown: API request failed"
        })
    except json.JSONDecodeError:
        result.update({
            "reason": "Reason: Invalid API response format",
            "breakdown": "Breakdown: Could not parse response"
        })
    except Exception as e:
        result.update({
            "reason": f"Reason: Unexpected error - {str(e)}",
            "breakdown": "Breakdown: Evaluation failed"
        })
    finally:
        elapsed_time = time.time() - start_time
        print("Raw API content:", content)
        # Always combine reason and breakdown for display
        result["reason"] = f"{result['reason']}\n{result['breakdown']}"
        return result, elapsed_time