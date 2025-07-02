import requests
import json
import time

# Editable prompt for Correctness evaluation
# CORRECTNESS_PROMPT = {

#     "prompt_template": """
# You are an expert evaluator of AI responses. Evaluate the following AI response for Correctness in a strict, step-by-step, deterministic way.
# User Question: {question}
# AI Response: {response}
# Expected Response: {expected}

# Evaluate the AI response on a scale of 0-100 for Correctness. Provide a detailed explanation for your score.
# Consider:
# - Factual accuracy of the information provided
# - Alignment with the expected response
# - Absence of incorrect statements or misinterpretations

# Format your response as a JSON with two fields:
# 1. "score": A percentage score (0-100) indicating the correctness of the response
# 2. "reason": A detailed explanation for the score

# JSON response only:
# """
# }

def evaluate_correctness(question, actual_result, expected_result, api_key, api_url, stop_requested=None):
    #content = None
    if stop_requested and stop_requested():
        return {"score": 0, "reason": "Stopped by user.", "breakdown": []}, 0.0
    # Add this input length check
    if len(actual_result) + len(expected_result) > 8000:  # or another threshold
        return {"score": 0, "reason": "Input too long for evaluation.", "breakdown": []}, 0.0
    """
    Evaluates the correctness of a chatbot response using a detailed insurance-specific prompt.
    Returns:
    - dict: {"score": ..., "reason": ...}
    - float: elapsed time in seconds
    """
    start_time = time.time()
    content = ""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key
    }
    
 
    prompt_template = """
    You are a strict correctness evaluator that follows exact rules. Analyze this response:

    [EVALUATION RULES]
    1. Scoring (MUST follow exactly):
    - Base score: 100%
    - Deduct EXACTLY 15% for each mismatch found
    - 0% for completely irrelevant responses

    2. Mismatch Types (15% each):
    - Currency/value differences (USD→HKD, 100→150)
    - Condition changes ("up to"→"exactly")
    - Coverage changes ("covered"→"not covered")
    - Missing required conditions
    - Added unnecessary information
    - Meaning-changing phrasing differences

    3. Required Actions:
    - COMPARE LINE-BY-LINE
    - IGNORE grammar/style differences
    - ALWAYS deduct 15% per mismatch
    - NEVER make exceptions

    [INPUT]
    Question: {question}
    Expected: {expected_result}
    Actual: {actual_result}

    [OUTPUT FORMAT]
    ```json
    {{
    "Correctness_score": [100 - (15 * mismatch_count)],
    "reason": "Brief issue summary",
    "breakdown": [
        {{
        "type": "[Mismatch category]",
        "expected": "[exact expected text]",
        "actual": "[exact actual text]",
        "deduction": 15
        }}
    ]
    }}

    [EVALUATION STEPS]
    1. Compare each element of expected vs actual result
    2. For each difference found:
    a) Categorize the mismatch type
    b) Record expected and actual values
    c) Apply 15% deduction
    3. Calculate final score (100 - total deductions)
    4. Prepare output in EXACTLY the specified JSON format

    [EXAMPLE]
    {{
    "Correctness_score": 70,
    "reason": "3 mismatches found in currency, coverage and conditions",
    "breakdown": [
        {{
        "mismatch_type": "currency",
        "expected": "USD",
        "actual": "HKD",
        "deduction": 15
        }},
        {{
        "mismatch_type": "coverage",
        "expected": "not covered",
        "actual": "covered",
        "deduction": 15
        }},
        {{
        "mismatch_type": "condition",
        "expected": "up to $1000",
        "actual": "exactly $1000",
        "deduction": 15
        }}
    ]
    }}
    """

    formatted_prompt = prompt_template.format(
        question=question,
        expected_result=expected_result,
        actual_result=actual_result
    )
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": formatted_prompt}
        ],
        "temperature": 0.0,
        "top_p": 0.1,
        "max_tokens": 8000
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        if stop_requested and stop_requested():
            return {"score": 0, "reason": "Stopped by user.", "breakdown": []}, 0.0
        
        if response.status_code != 200:
            raise Exception(f"API request failed with status code {response.status_code}: {response.text}")
        
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Print token usage if available
        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", "N/A")
        completion_tokens = usage.get("completion_tokens", "N/A")
        total_tokens = usage.get("total_tokens", "N/A")
        print(f"Token usage - prompt: {prompt_tokens}, completion: {completion_tokens}, total: {total_tokens}")
        
        # Extract JSON from content
        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                evaluation_result = json.loads(json_str)
            else:
                evaluation_result = {
                    "Correctness_score": 0,
                    "Reason": "Could not parse API response.",
                    "breakdown": []
                }
        except json.JSONDecodeError:
            evaluation_result = {
                "Correctness_score": 0,
                "Reason": "Could not parse API response.",
                "breakdown": []
            }
    
    except Exception as e:
        evaluation_result = {
            "Correctness_score": 0,
            "Reason": f"Error: {str(e)}",
            "breakdown": []
        }
        content = ""
    
    elapsed_time = time.time() - start_time

    breakdown = evaluation_result.get("breakdown", [])
    reason = (
    evaluation_result.get("Reason")
    or evaluation_result.get("reason")
    or evaluation_result.get("discrepancies")
    or ""
)

    # Calculate score from breakdown if available
    if breakdown and isinstance(breakdown, list):
            total_deduction = sum(
                int(item.get("deduction", 0)) for item in breakdown if isinstance(item, dict)
            )
            score = max(0, 100 - total_deduction)
    else:
        score = (
    evaluation_result.get("Correctness_score")
    or evaluation_result.get("correctness_score")
    or evaluation_result.get("Correctness score")
    or evaluation_result.get("correctness score")
    or evaluation_result.get("score")
    or 0
)

    breakdown_str = ""
    if breakdown and isinstance(breakdown, list):
        breakdown_str += "Breakdown:\n"
        for item in breakdown:
            # If item is a dict, format its keys/values nicely
            if isinstance(item, dict):
                for k, v in item.items():
                    # Remove % if present in value
                    v_str = str(v).replace("%", "")
                    breakdown_str += f"  - {k}: {v_str}\n"
            else:
                # fallback for non-dict items
                breakdown_str += f"  - {str(item)}\n"
    else:
        breakdown_str += "Breakdown: None\n"

    summary = f"Reason: {reason}\n{breakdown_str}"

    print("Correctness score:", score)
    print("Raw API content:", content)

    # Return a dict for compatibility with main.py
    return {"score": score, "reason": summary}, elapsed_time

# question = "What is the capital of France?"
# actual_result = "The capital of France is Paris."
# expected_result = "The capital of France is Paris." # Example usage 
# api_key = "Bearer sk-e09a03dca28b434eba574f0cee3e5f13"
# api_url = "https://api.deepseek.com/v1/chat/completions"
# evaluate_correctness(
#     question,
#     actual_result,
#     expected_result,api_key=api_key,
#     api_url=api_url)

