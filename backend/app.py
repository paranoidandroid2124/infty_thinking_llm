import os
import re
import json
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
from dotenv import dotenv_values
from langchain.chat_models import init_chat_model
from threading import Thread

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

# 채팅방 대화 내역 저장용 JSON 파일 (각 채팅방별로 저장)
CHAT_FILE = "chats.json"

def load_chats():
    """chats.json 파일에서 모든 채팅방의 대화 내역을 로드"""
    if not os.path.exists(CHAT_FILE):
        return {}
    with open(CHAT_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_chats(chats):
    """chats.json 파일에 채팅방 대화 내역을 저장"""
    with open(CHAT_FILE, "w", encoding="utf-8") as file:
        json.dump(chats, file, indent=4, ensure_ascii=False)

def format_paragraphs(text):
    # 문장 마침표 뒤에 줄바꿈을 추가
    text = re.sub(r"\. ", ".\n\n", text) 
    return text

def insert_paragraph_breaks(text):
    """
    모델이 생성한 답변 내에서
    **Problem**, **Current Solution** 등 특정 키워드를 기준으로
    문단 구분을 위해 두 줄의 줄바꿈을 추가하는 함수
    """
    sections = ["**Problem**", "**Current Solution**", "**Refined Solution**", "**Final Answer**"]
    for section in sections:
        text = text.replace(section, f"\n\n{section}")
    return text

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
	- 답변은 무조건 한국어로 생성해 주세요.

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

def refine_solution(problem, current_solution, iterations=5):
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
	- 답변은 무조건 한국어로 생성해 주세요.
	- 출력 시, input text와 final response를 비롯한 각 단락은 세부적으로 문단화 되어서 줄 바꿈이 일어나야 합니다.
	- 항목을 세분화해서 각 항목마다 설명을 하는 경우, 무조건적으로 줄 바꿈을 해야 합니다.
	- 가독성을 확보해 주세요.

        **Final Answer:**
        """
        socketio.emit("update", {"message": f"Refinement round {i+1} in progress..."})
        response = model.invoke(refine_prompt).content
    return response

def process_math_problem(chat_id, problem, iterations=5):
    chats = load_chats()
    chat_history = chats.get(chat_id, [])
    ai_prompt = prompt_math(problem, chat_history)
    initial_solution = model.invoke(ai_prompt).content
    socketio.emit("update", {"message": "Initial solution received."})

    # iterations 값을 인자로 전달
    final_solution = refine_solution(problem, initial_solution, iterations)
    final_solution = insert_paragraph_breaks(final_solution)
    final_solution = format_paragraphs(final_solution)
    final_solution = final_solution.replace("\n", "<br>")

    chat_history.append({"user": problem, "assistant": final_solution})
    chats[chat_id] = chat_history
    save_chats(chats)
    return final_solution

# === 웹 인터페이스 관련 라우트 ===

@app.route("/")
def index():
    """메인 페이지 렌더링 (프론트엔드에서 사이드바와 채팅 UI를 구현)"""
    return render_template("index.html")

# === API 엔드포인트: 여러 채팅방 관리 ===

@app.route("/api/chat_rooms", methods=["GET"])
def get_chat_rooms():
    """모든 채팅방의 ID 목록 반환"""
    chats = load_chats()
    return jsonify(list(chats.keys()))

@app.route("/api/new_chat", methods=["POST"])
def new_chat():
    """새로운 채팅방 생성 후 chat_id 반환"""
    chats = load_chats()
    chat_id = uuid.uuid4().hex[:8].upper()  # 예: "ABCD1234"
    chats[chat_id] = []  # 빈 대화 내역 초기화
    save_chats(chats)
    return jsonify({"chat_id": chat_id})

@app.route("/api/chat_rooms/<chat_id>", methods=["GET"])
def get_chat_room(chat_id):
    """특정 채팅방의 대화 내역 반환"""
    chats = load_chats()
    if chat_id not in chats:
        return jsonify({"error": "Chat room not found"}), 404
    return jsonify(chats[chat_id])

# --- 기존 /api/chat_rooms/<chat_id>/message 엔드포인트 수정 ---
@app.route("/api/chat_rooms/<chat_id>/message", methods=["POST"])
def post_message(chat_id):
    """특정 채팅방에 사용자 메시지를 추가하고, 모델의 답변 생성"""
    chats = load_chats()
    if chat_id not in chats:
        return jsonify({"error": "Chat room not found"}), 404
    data = request.get_json()
    user_message = data.get("message", "")
    # iterations 값 추가: 클라이언트가 전달한 값이 있으면 사용, 없으면 기본값 5
    iterations = int(data.get("iterations", 5))
    
    # 모델 호출 및 대화 내역 업데이트 (process_math_problem 함수 내에서 수행)
    assistant_reply = process_math_problem(chat_id, user_message, iterations)
    
    return jsonify({"assistant_reply": assistant_reply})


# === 기존 /solve 엔드포인트 (단일 채팅용, 선택 사항) ===

@app.route("/solve", methods=["POST"])
def solve():
    data = request.get_json()
    problem = data.get("problem")
    default_chat_id = "DEFAULT"
    chats = load_chats()
    if default_chat_id not in chats:
        chats[default_chat_id] = []
        save_chats(chats)
    
    def background_task(problem):
        final_solution = process_math_problem(default_chat_id, problem)
        socketio.emit("result", {"solution": final_solution})
    
    Thread(target=background_task, args=(problem,)).start()
    return jsonify({"status": "processing"})

if __name__ == "__main__":
    socketio.run(app, debug=True)