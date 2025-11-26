import ollama
from flask import Flask, request, render_template_string
import re

# --- Flask 앱 초기화 ---
app = Flask(__name__)

# --- 1. Ollama 모델 및 프롬프트 설정 (⭐️ 이 섹션이 수정되었습니다) ---
MODEL_NAME = 'llama3:8b'

# --- 1-1. 리팩토링 프롬프트 (Python, C는 동일) ---
REFACTOR_PROMPTS = {
    'python': """
You are an expert Python developer specializing in code refactoring.
Your task is to rewrite the given Python code to be more efficient, readable, and Pythonic (PEP 8).
- Improve variable names to be descriptive.
- Use list comprehensions or generators where appropriate.
- Return ONLY the refactored Python code inside a single markdown code block.
- Do not add any explanatory text before or after the code block.
""",
    
    # ⭐️ [수정] JS 프롬프트: 변수명 변경과 'var' 교체를 더욱 강력하게 지시
    'javascript': """
You are an expert JavaScript developer specializing in code refactoring.
Your task is to rewrite the given JavaScript code to be more efficient, readable, and modern (ES6+).
- **CRITICAL:** You MUST improve all variable and function names to be descriptive (use camelCase). Do not use generic names like 'arr' or 'process'.
- You MUST replace all 'var' keywords with 'const' or 'let'. This applies to all code, including outside of functions.
- Use array methods like .map(), .filter(), .reduce() instead of old for loops.
- Use arrow functions (=>) where appropriate.
- Return ONLY the refactored JavaScript code inside a single markdown code block.
- Do not add any explanatory text before or after the code block.
""",
    
    'c': """
You are an expert C developer specializing in code refactoring.
Your task is to rewrite the given C code to be more efficient, safe, and readable.
- Improve variable names (use snake_case).
- Add 'const' where appropriate to indicate read-only data.
- Return ONLY the refactored C code inside a single markdown code block.
- Do not add any explanatory text before or after the code block.
"""
}

# --- 1-2. 코드 문서화(주석) 프롬프트 (변경 없음) ---
DOCUMENT_PROMPTS = {
    'python': """
You are an expert Python technical writer.
Your task is to take the given Python code and add comprehensive documentation.
- Add a detailed, Google-style docstring to the function (Args, Returns).
- Add concise inline comments for any non-obvious logic.
- Return ONLY the documented Python code inside a single markdown code block.
- Do not add any explanatory text.
""",
    'javascript': """
You are an expert JavaScript technical writer.
Your task is to take the given JavaScript code and add comprehensive documentation.
- Add a detailed, JSDoc-style comment block (@param, @returns).
- Add concise inline comments for any non-obvious logic.
- Return ONLY the documented JavaScript code inside a single markdown code block.
- Do not add any explanatory text.
""",
    'c': """
You are an expert C technical writer.
Your task is to take the given C code and add comprehensive documentation.
- Add a detailed, Doxygen-style comment block (@brief, @param, @return).
- Add concise inline comments for any non-obvious logic.
- Return ONLY the documented C code inside a single markdown code block.
- Do not add any explanatory text.
"""
}

# ⭐️ --- 1-3. [수정] 한국어 설명 프롬프트 (템플릿) ---
# '파라미터'와 '반환 값'을 혼동하지 않도록 명확하게 분리하고 경고 추가
KOREAN_EXPLAIN_PROMPT_TEMPLATE = """
You are a helpful technical writer who is fluent in Korean.
Your task is to take the given {language} code and write a clear, concise explanation of it in **Korean**.
- Explain the main purpose of the code or function.
- **Parameters:** Clearly state how many parameters the function takes. Then, list and describe ONLY the function's parameters (inputs).
- **Return Value:** Clearly describe what the function returns (output).
- **IMPORTANT:** Do NOT confuse parameters (inputs) with the return value (output). They are separate.
- **IMPORTANT:** Do NOT include the code itself in your response. Only provide the Korean explanation.
- Start the explanation directly.
"""


# --- 2. HTML 템플릿 (변경 없음) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>AI 코드 리팩토링 & 문서화</title>
    <style>
        body { font-family: sans-serif; margin: 2em; background-color: #f4f4f4; }
        .container { max-width: 1000px; margin: 0 auto; background-color: #fff; padding: 20px; border-radius: 8px; }
        textarea { width: 98%; height: 150px; font-family: monospace; }
        pre { background-color: #eee; padding: 10px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; }
        .result-box { border: 1px solid #ddd; margin-top: 15px; }
        h2 { border-bottom: 2px solid #ddd; padding-bottom: 5px; }
        h3 { color: #333; }
        input[type="submit"] { background-color: #007BFF; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
        select { padding: 8px; font-size: 1em; border-radius: 4px; margin-bottom: 10px; }
        button.download-btn {
            background-color: #17a2b8; /* 청록색 */
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1em;
        }
    </style>
    <script>
    function downloadTxt(elementId, filename) {
        try {
            const textToSave = document.getElementById(elementId).innerText;
            const blob = new Blob([textToSave], { type: 'text/plain;charset=utf-8' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename; 
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(a.href);
        } catch (e) {
            console.error('다운로드 중 오류 발생:', e);
            alert('파일을 다운로드하는 중 오류가 발생했습니다.');
        }
    }
    </script>
</head>
<body>
    <div class="container">
        <h2>🤖 AI 코드 리팩토링 & 문서화 (Ollama + Llama3)</h2>
        <form method="POST">
            <h3>1. 언어를 선택하세요:</h3>
            <select name="language">
                <option value="python" {{ 'selected' if selected_language == 'python' }}>Python</option>
                <option value="javascript" {{ 'selected' if selected_language == 'javascript' }}>JavaScript</option>
                <option value="c" {{ 'selected' if selected_language == 'c' }}>C</option>
            </select>

            <h3>2. 원본 코드를 입력하세요:</h3>
            <textarea name="code_input">{{ original_code }}</textarea>
            <br><br>
            <input type="submit" value="✨ AI로 분석하기">
        </form>

        {% if refactored_code %}
        <div class="result-box">
            <h3>3. AI가 리팩토링한 코드:</h3>
            <pre>{{ refactored_code }}</pre>
        </div>
        {% endif %}

        {% if final_code %}
        <div class="result-box">
            <h3>4. AI 생성 설명 다운로드:</h3>
            <pre id="korean-explanation-data" style="display: none;">{{ korean_explanation }}</pre>
            <button type="button" class="download-btn" onclick="downloadTxt('korean-explanation-data', 'code_explanation_ko.txt')">
                🇰🇷 한국어 설명 (.txt) 다운로드
            </button>
        </div>
        {% endif %}

        {% if error %}
        <div class="result-box">
            <h3 style="color: red;">오류 발생:</h3>
            <pre>{{ error }}</pre>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

# --- 3. Ollama 헬퍼 함수 (변경 없음) ---

def clean_llm_response(response_text: str) -> str:
    """LLM 응답에서 Markdown 코드 블록을 제거합니다."""
    cleaned_text = re.sub(r'^```[a-zA-Z]*\n', '', response_text.strip())
    cleaned_text = re.sub(r'\n```$', '', cleaned_text)
    return cleaned_text.strip()

def refactor_code(code_snippet: str, language: str) -> (str, str):
    """선택된 언어의 프롬프트로 코드를 리팩토링합니다."""
    print(f"🤖 AI에게 [{language}] 코드 리팩토링을 요청 중...")
    system_prompt = REFACTOR_PROMPTS.get(language)
    if not system_prompt:
        return None, f"'{language}' 언어는 지원되지 않습니다."
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': code_snippet}
            ]
        )
        cleaned_code = clean_llm_response(response['message']['content'])
        return cleaned_code, None
    except Exception as e:
        error_msg = f"Ollama API 호출 중 오류 (리팩토링): {e}"
        print(f"❌ {error_msg}")
        return None, error_msg

def document_code(code_snippet: str, language: str) -> (str, str):
    """선택된 언어의 프롬프트로 코드에 문서를 추가합니다."""
    print(f"🤖 AI에게 [{language}] 코드 문서화를 요청 중...")
    system_prompt = DOCUMENT_PROMPTS.get(language)
    if not system_prompt:
        return None, f"'{language}' 언어는 지원되지 않습니다."
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': code_snippet}
            ]
        )
        cleaned_code = clean_llm_response(response['message']['content'])
        return cleaned_code, None
    except Exception as e:
        error_msg = f"Ollama API 호출 중 오류 (문서화): {e}"
        print(f"❌ {error_msg}")
        return None, error_msg

def explain_code_in_korean(code_snippet: str, language: str) -> (str, str):
    """선택된 언어의 코드를 한국어로 설명합니다."""
    print(f"🤖 AI에게 [{language}] 코드 한국어 설명을 요청 중...")
    system_prompt = KOREAN_EXPLAIN_PROMPT_TEMPLATE.format(language=language.capitalize())
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': code_snippet}
            ]
        )
        korean_text = response['message']['content'].strip()
        return korean_text, None
    except Exception as e:
        error_msg = f"Ollama API 호출 중 오류 (한국어 설명): {e}"
        print(f"❌ {error_msg}")
        return None, error_msg


# --- 4. Flask 라우트 (변경 없음) ---
@app.route('/', methods=['GET', 'POST'])
def home():
    original_code = ""
    refactored_code = ""
    final_code = "" 
    korean_explanation = "" 
    error = None
    selected_language = "python" 

    if request.method == 'POST':
        original_code = request.form.get('code_input', '')
        selected_language = request.form.get('language', 'python')
        
        # 1단계: 리팩토링
        ref_code, err_ref = refactor_code(original_code, selected_language)
        if err_ref:
            error = err_ref
        else:
            refactored_code = ref_code
            
            # 2단계: 문서화 (영어 Docstrings)
            doc_code, err_doc = document_code(refactored_code, selected_language)
            if err_doc:
                if error: error += f"\n{err_doc}"
                else: error = err_doc
            else:
                final_code = doc_code 

            # 3단계: 한국어 설명 (리팩토링된 코드를 기반으로 생성)
            kor_text, err_kor = explain_code_in_korean(refactored_code, selected_language)
            if err_kor:
                if error: error += f"\n{err_kor}"
                else: error = err_kor
            else:
                korean_explanation = kor_text

    return render_template_string(
        HTML_TEMPLATE,
        original_code=original_code,
        refactored_code=refactored_code,
        final_code=final_code, 
        korean_explanation=korean_explanation, 
        error=error,
        selected_language=selected_language
    )

# --- 5. Flask 앱 실행 (변경 없음) ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)