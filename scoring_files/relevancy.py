import requests
import json
import time

# Editable prompt for Relevancy evaluation
RELEVANCY_PROMPT = {
    "description": "Evaluates how closely an AI-generated output aligns with the intent, context, and user needs of a given input",
    "prompt_template": """
You are an expert evaluator of AI responses. Evaluate the following AI response based on the Relevancy metric.

User Question: {question}

AI Response: {response}

Evaluate the AI response on a scale of 0-100 for Relevancy. Provide a detailed explanation for your score.
Consider:
- How well the response addresses the specific question asked
- Whether the response stays on topic and provides information relevant to the user's needs
- The absence of irrelevant or tangential information

Format your response as a JSON with two fields:
1. "score": A number between 0 and 100
2. "reason": A detailed explanation for the score

JSON response only:
"""
}

def evaluate_relevancy(question, actual_result, api_key, api_url):
    """
    Evaluates the relevancy of a chatbot response using a detailed insurance-specific prompt.
    Returns:
    - dict: {"score": ..., "reason": ...}
    - float: elapsed time in seconds
    """
    start_time = time.time()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key
    }
    
    # Updated prompt as requested
    prompt_template = """
Analyze this insurance response test case:

    Question: {question}
    Actual Result: {actual_result}

    Return JSON with:
    1. relavancy_score (0-100%) using these rules:
       - 15% if it says unrelated details.
       - 15% if the response is not addressing the user's question fully.
       - 15% deduction for partial relevance
       - 15% if not incorporate key terms from the user's question.
       - 15% if it not correctly interpret the user’s underlying need

    2. breakdown: points deducted per mismatch in a table format with columns:
         - Irrelavant details
         - Deduction (%)
    3. Reason: Two line description of reason for the score. 
    
    Example Response:
    {{
        "Relavancy score": 85,
        "Reason": "Reason for the score",
        "breakdown": [
            {{
                "Irrelavant Details: Python is great for data science. Start with basics like variables and loops. Also, Java is popular for enterprise apps.",
                "Deduction": 15
            }}
        ]
    }}
    """

    formatted_prompt = prompt_template.format(
        question=question,
        actual_result=actual_result
    )
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": formatted_prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"API request failed with status code {response.status_code}: {response.text}")
        
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Extract JSON from content
        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                evaluation_result = json.loads(json_str)
                breakdown = evaluation_result.get("breakdown", [])
            else:
                evaluation_result = {"score": 0, "reason": "Could not parse API response."}
                breakdown = evaluation_result.get("breakdown", [])
        except json.JSONDecodeError:
            evaluation_result = {"score": 0, "reason": "Could not parse API response."}
            breakdown = []
        
    except Exception as e:
        evaluation_result = {"score": 0, "reason": f"Error: {str(e)}"}
        breakdown = []
    
    elapsed_time = time.time() - start_time

    # Calculate score from breakdown if available
    if breakdown and isinstance(breakdown, list):
        total_deduction = 0
        for item in breakdown:
            if isinstance(item, dict):
                for k, v in item.items():
                    if "deduction" in k.lower():
                        try:
                            total_deduction += int(str(v).replace("%", ""))
                        except Exception:
                            pass
        score = max(0, 100 - total_deduction)
    else:
        score = (
            evaluation_result.get("Relavancy_score")
            or evaluation_result.get("Relavancy score")
            or evaluation_result.get("Relevancy_score")
            or evaluation_result.get("Relevancy score")
            or evaluation_result.get("score")
            or 0
        )
    reason = evaluation_result.get("Reason", "") or evaluation_result.get("Reason", "")
    breakdown = evaluation_result.get("breakdown", [])

    breakdown_str = ""
    if breakdown and isinstance(breakdown, list):
        breakdown_str += "Breakdown:\n"
        for item in breakdown:
            if isinstance(item, dict):
                detail = ""
                deduction = ""
                for k, v in item.items():
                    if k.lower().startswith("irrelavant details"):
                        # Only print the value, not the key
                        detail = str(v)
                    elif "deduction" in k.lower():
                        deduction = str(v).replace("%", "")
                if detail:
                    breakdown_str += f"  - {detail}\n"
                if deduction:
                    breakdown_str += f"    Deduction: {deduction}\n"
            else:
                breakdown_str += f"  - {str(item)}\n"
    else:
        breakdown_str += "Breakdown: None\n"

    summary = f"Reason: {reason}\n{breakdown_str}"
    print("Raw API content:", content)

    print("Evaluation result dict:", evaluation_result)
    return {"score": score, "reason": summary}, elapsed_time
