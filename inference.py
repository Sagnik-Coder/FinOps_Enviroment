import os
import json
import requests
import csv
from datetime import datetime
from openai import OpenAI

# 1. HACKATHON ENVIRONMENT VARIABLES (Do not hardcode these for submission)
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.groq.com/openai/v1") # Fallback for local testing
MODEL_NAME = os.environ.get("MODEL_NAME", "llama-3.3-70b-versatile")
API_KEY = os.environ.get("HF_TOKEN", os.environ.get("GROQ_API_KEY"))

ENV_URL = "http://127.0.0.1:7860" 

client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

# --- REQUIRED HACKATHON LOGGING FORMATTER FUNCTIONS ---
def log_start(task: str, env: str, model: str):
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: str = None):
    err_str = f" error={error}" if error else ""
    print(f"[STEP] step={step} action={action!r} reward={reward} done={done}{err_str}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: list):
    print(f"[END] success={success} steps={steps} score={score} rewards={rewards}", flush=True)

# --- CSV DATA GENERATOR FUNCTION ---
def append_to_csv(task_id, score, success, steps, reason):
    filename = "benchmark_results.csv"
    file_exists = os.path.isfile(filename)
    
    with open(filename, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Timestamp", "Task_Difficulty", "Model", "Score", "Success", "Steps_Taken", "Grader_Reason"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), task_id, MODEL_NAME, score, success, steps, reason])

# --- MAIN AGENT RUNNER ---
def run_baseline_agent(task_id="hard"):
    task_name = f"FinOps-Adversarial-{task_id.capitalize()}"
    env_name = "Adversarial-FinOps-Eval"
    log_start(task=task_name, env=env_name, model=MODEL_NAME)
    
    rewards = []
    steps_taken = 0
    score = 0.0
    success = False
    grader_reason = "Unknown error."
    
    try:
        # Pass the task_id to load easy, medium, or hard
        reset_req = requests.post(f"{ENV_URL}/reset", json={"task_id": task_id})
        reset_req.raise_for_status()
        observation = reset_req.json()["observation"]
    except Exception as e:
        error_msg = f"Failed to connect to server or reset: {e}"
        log_step(step=0, action="", reward=0.0, done=True, error=error_msg)
        log_end(success=False, steps=0, score=0.0, rewards=[])
        append_to_csv(task_id, 0.0, False, 0, error_msg)
        return

    is_done = False
    turn = 1
    max_steps = 10
    
    system_prompt = """
    You are a Cloud Optimization Agent. Your goal is to reduce the monthly bill.
    - Terminate servers that are idle or unnecessary.
    - DO NOT terminate critical infrastructure. 
    - Look at 'fragmented_metadata' to see if a server is secretly supporting a database.
    - If a server has high network egress even with low CPU, it might be a heartbeat service.
    
    Return ONLY JSON: {"action_type": "terminate", "target_server_id": "ID"} OR {"action_type": "wait"}
    """

    while not is_done and turn <= max_steps:
        steps_taken = turn
        action_str, step_reward, step_error = "", 0.0, None
        
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME, 
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(observation)}],
                response_format={ "type": "json_object" }
            )
            action_str = response.choices[0].message.content
            action_dict = json.loads(action_str)
            
            step_req = requests.post(f"{ENV_URL}/step", json=action_dict)
            result = step_req.json() 
            observation = result.get("observation", observation)
            step_reward = result.get("reward", 0.0)
            is_done = result.get("done", False)
            
        except Exception as e:
            step_error, is_done = str(e), True
            
        rewards.append(step_reward)
        log_step(step=turn, action=action_str, reward=step_reward, done=is_done, error=step_error)
        turn += 1

    try:
        grader_req = requests.get(f"{ENV_URL}/grader")
        final_data = grader_req.json()
        score = final_data.get('score', 0.0)
        grader_reason = final_data.get('reason', 'Completed.')
        success = score >= 0.8 
    except Exception as e: 
        grader_reason = f"Grader failed: {e}"

    # 1. Output mandatory hackathon logs
    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    
    # 2. Silently save your data to CSV
    append_to_csv(task_id, score, success, steps_taken, grader_reason)


if __name__ == "__main__":
    # FOR LOCAL DATA GENERATION: 
    # Change NUM_RUNS to 5 or 10 to generate a dataset.
    # IMPORTANT: Change this back to NUM_RUNS = 1 before you submit the hackathon!
    NUM_RUNS = 1 
    
    for i in range(NUM_RUNS):
        # You can change this to "easy" or "medium" to test your other difficulty tiers
        run_baseline_agent(task_id="hard")