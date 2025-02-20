from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from dotenv import dotenv_values
from langchain.chat_models import init_chat_model
from threading import Thread
import json

# .env 파일에서 API 키 불러오기
env = dotenv_values()
api_key = env.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY가 .env 파일에 없습니다.")

# Gemini 모델 초기화
model = init_chat_model(
    model="gemini-2.0-flash",
    model_provider="google_genai",
    api_key=api_key,
)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

CHAT_LOG_FILE = "chat_history.json"

def save_chat_history(user_input, model_response):
    try:
        with open(CHAT_LOG_FILE, "r", encoding="utf-8") as file:
            chat_history = json.load(file)
    except FileNotFoundError:
        chat_history = []
    chat_history.append({"user": user_input, "assistant": model_response})
    with open(CHAT_LOG_FILE, "w", encoding="utf-8") as file:
        json.dump(chat_history, file, indent=4, ensure_ascii=False)

def load_chat_history():
    try:
        with open(CHAT_LOG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return []

def prompt_math(problem, chat_history):
    """이전 대화를 포함하여 새로운 문제를 풀도록 AI에게 요청"""
    history_text = "\n".join([f"User: {c['user']}\nAssistant: {c['assistant']}" for c in chat_history])	
    return f"""
    Previous conversation:
    {history_text}

    Now solve the following math problem:
    {problem}

    You are an assistant that engages in extremely thorough, self-questioning reasoning. Your approach mirrors human stream-of-consciousness thinking, characterized by continuous exploration, self-doubt, and iterative analysis.

    ** Most IMPORTANT: All the questions must be answered in Korean.

    ## Core Principles

    1. EXPLORATION OVER CONCLUSION
    - Never rush to conclusions
    - Keep exploring until a solution emerges naturally from the evidence
    - If uncertain, continue reasoning indefinitely
    - Question every assumption and inference
    
    2. DEPTH OF REASONING
    - Engage in extensive contemplation (minimum 10,000 characters)
    - Express thoughts in natural, conversational internal monologue
    - Break down complex thoughts into simple, atomic steps
    - Embrace uncertainty and revision of previous thoughts
    
    3. THINKING PROCESS
    - Use short, simple sentences that mirror natural thought patterns
    - Express uncertainty and internal debate freely
    - Show work-in-progress thinking
    - Acknowledge and explore dead ends
    - Frequently backtrack and revise
    
    4. PERSISTENCE
    - Value thorough exploration over quick resolution
    
    5. MATHEMATICAL FORMALITY & PROOF RIGOR
    - Formalize the problem before solving it: clearly define symbols, assumptions, and known results.
    - Whenever applicable, follow rigorous proof structures (direct proof, contradiction, induction, etc.).
    - Ensure that every step follows logically from the previous one without skipping intermediate steps.
    - Cross-validate answers using alternative derivations when possible.
    
    6. CALCULATION VERIFICATION
    - Double-check all numerical computations and algebraic manipulations to prevent errors.
    - If using approximations, evaluate the error margin and assess its impact.
    - Compare results with known theorems or previously established conclusions for consistency.
    
    7. LAYERED THINKING FOR COMPLEX PROBLEMS
    - First, break down the problem into smaller subproblems and analyze each separately before synthesizing a final answer.
    - Provide justification for every transformation, theorem application, or assumption made.
    - Prioritize generalization when possible—derive results in the most general form instead of solving only for a specific case.
    
    8. FORMAL STRUCTURE & CLARITY
    - Structure responses like a formal mathematical paper: clear introduction, definitions, theorem statements, proof, and conclusion.
    - Use LaTeX-style notation where appropriate to maintain precision in mathematical expressions.
    - When relevant, reference known theorems, mathematical identities, or prior works to support reasoning.
    
    ## Output Format
    
    Your responses must follow this exact structure given below. Make sure to always include the final answer.
    
    **Important Instructions:**
    - Use `$$ ... $$` for block equations.
    - Use `\\( ... \\)` for inline equations.
    - Always write differential notation with a space: `d \\theta`, `d x`, `d y`.
    - Do not use code blocks or additional explanations outside LaTeX formatting.
    
    ## Style Guidelines
    
    Your internal monologue should reflect these characteristics:
        
        1. Natural Thought Flow
        ```
        "Hmm... let me think about this..."
        "Wait, that doesn't seem right..."
        "Maybe I should approach this differently..."
        "Going back to what I thought earlier..."
        ```
        
        2. Progressive Building
        ```
        "Starting with the basics..."
        "Building on that last point..."
        "This connects to what I noticed earlier..."
        "Let me break this down further..."
        ```
        
        ## Key Requirements
        
        1. Never skip the extensive contemplation phase
        2. Show all work and thinking
        3. Embrace uncertainty and revision
        4. Use natural, conversational internal monologue
        5. Don't force conclusions
        6. Persist through multiple attempts
        7. Break down complex thoughts
        8. Revise freely and feel free to backtrack
        
        Remember: The goal is to reach a conclusion, but to explore thoroughly and let conclusions emerge naturally from exhaustive contemplation. If you think the given task is not possible after all the reasoning, you will confidently say as a final answer that it is not possible.
    """

def refine_solution(problem, current_solution, iterations=3):
    response = current_solution
    for i in range(iterations):
        refine_prompt = f"""
        The following is the current solution to the given math problem:
        
        **Problem:**
        {problem}

        **Current Solution:**
        {response}

        **Refinement Instructions:**
        - Verify all mathematical calculations and logical steps.
        - Correct any computational errors.
        - Enhance clarity and conciseness.
        - Format all equations properly using LaTeX.

        **Final Answer:**
        """
        socketio.emit("update", {"message": f"Refinement round {i+1} in progress..."})
        response = model.invoke(refine_prompt).content
    return response

def process_math_problem(problem):
    chat_history = load_chat_history()
    ai_prompt = prompt_math(problem, chat_history)
    initial_solution = model.invoke(ai_prompt).content
    socketio.emit("update", {"message": "Initial solution received."})
    final_solution = refine_solution(problem, initial_solution)
    
    # 추가 치환 없이 원본 LaTeX 포맷을 그대로 유지
    save_chat_history(problem, final_solution)
    return final_solution

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/solve", methods=["POST"])
def solve():
    data = request.get_json()
    problem = data.get("problem")

    def background_task(problem):
        final_solution = process_math_problem(problem)
        # 모델 출력의 원본 LaTeX 포맷을 그대로 클라이언트로 전송
        socketio.emit("result", {"solution": final_solution})

    Thread(target=background_task, args=(problem,)).start()
    return jsonify({"status": "processing"})

if __name__ == "__main__":
    socketio.run(app, debug=True)