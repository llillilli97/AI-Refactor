import sys
import re
import ollama
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QTextEdit, QPushButton, QLabel, QMessageBox, QFileDialog
)
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont

# --- 1. Ollama 프롬프트 설정 (Flask 버전과 동일) ---

# ⭐️ (참고) JS와 한국어 설명 프롬프트는 이전에 개선한 버전입니다.
REFACTOR_PROMPTS = {
    'python': """
You are an expert Python developer specializing in code refactoring...
- Return ONLY the refactored Python code inside a single markdown code block.
""", 
    'javascript': """
You are an expert JavaScript developer specializing in code refactoring...
- **CRITICAL:** You MUST improve all variable and function names...
- Return ONLY the refactored JavaScript code inside a single markdown code block.
""", 
    'c': """
You are an expert C developer specializing in code refactoring...
- Return ONLY the refactored C code inside a single markdown code block.
""" 
}

# ⭐️ --- 1-3. [수정] 한국어 설명 프롬프트 (더 강력하게) ---
KOREAN_EXPLAIN_PROMPT_TEMPLATE = """
You are a helpful technical writer who is fluent in Korean.
Your task is to take the given {language} code and write a clear, concise explanation of it.
**YOUR RESPONSE MUST BE ENTIRELY IN KOREAN.**

- Explain the main purpose of the code or function in KOREAN.
- **파라미터 (Parameters):** Clearly state in KOREAN how many parameters the function takes. Then, list and describe ONLY the function's parameters (inputs) in KOREAN.
- **반환 값 (Return Value):** Clearly describe what the function returns (output) in KOREAN.
- **CRITICAL:** Do NOT confuse parameters (inputs) with the return value (output).
- **IMPORTANT:** Do NOT include the code itself in your response.
- **YOUR FINAL ANSWER MUST BE ONLY IN KOREAN.**
"""

# --- 2. Ollama 작업을 위한 'Worker' 스레드 ---

class OllamaWorker(QObject):
    """
    Ollama API 호출은 시간이 오래 걸리므로,
    별도 스레드에서 실행하여 GUI가 멈추지 않도록 합니다.
    """
    # ⭐️ 작업 완료 시그널: 결과(dict)를 메인 스레드로 전달
    finished = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.korean_explain_prompt = KOREAN_EXPLAIN_PROMPT_TEMPLATE
        self.refactor_prompts = REFACTOR_PROMPTS

    def clean_llm_response(self, response_text: str) -> str:
        """LLM 응답에서 Markdown 코드 블록을 제거합니다."""
        cleaned_text = re.sub(r'^```[a-zA-Z]*\n', '', response_text.strip())
        cleaned_text = re.sub(r'\n```$', '', cleaned_text)
        return cleaned_text.strip()

    def refactor_code(self, code_snippet: str, language: str) -> (str, str):
        """코드를 리팩토링합니다."""
        system_prompt = self.refactor_prompts.get(language)
        if not system_prompt:
            return None, f"'{language}' 언어는 지원되지 않습니다."
        try:
            response = ollama.chat(
                model='llama3:8b',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': code_snippet}
                ]
            )
            return self.clean_llm_response(response['message']['content']), None
        except Exception as e:
            return None, f"Ollama API 호출 중 오류 (리팩토링): {e}"

    def explain_code_in_korean(self, code_snippet: str, language: str) -> (str, str):
        """코드를 한국어로 설명합니다."""
        system_prompt = self.korean_explain_prompt.format(language=language.capitalize())
        try:
            response = ollama.chat(
                model='llama3:8b',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': code_snippet}
                ]
            )
            return response['message']['content'].strip(), None
        except Exception as e:
            return None, f"Ollama API 호출 중 오류 (한국어 설명): {e}"

    def run_analysis(self, code: str, language: str):
        """
        메인 분석 로직 (리팩토링 -> 한국어 설명)
        """
        result = {'refactored_code': '', 'korean_explanation': '', 'error': None}
        try:
            # 1단계: 리팩토링
            ref_code, err_ref = self.refactor_code(code, language)
            if err_ref:
                raise Exception(err_ref)
            result['refactored_code'] = ref_code

            # 2단계: 한국어 설명 (리팩토링된 코드를 기반으로 생성)
            kor_text, err_kor = self.explain_code_in_korean(ref_code, language)
            if err_kor:
                raise Exception(err_kor)
            result['korean_explanation'] = kor_text

            # ⭐️ 성공 시 결과물을 메인 스레드로 전송
            self.finished.emit(result)

        except Exception as e:
            result['error'] = str(e)
            # ⭐️ 실패 시에도 에러 메시지를 메인 스레드로 전송
            self.finished.emit(result)


# --- 3. 메인 윈도우 (GUI) ---

class CodeRefactorApp(QMainWindow):
    # ⭐️ Worker 스레드를 시작시킬 시그널 (str: code, str: language)
    start_analysis_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.korean_explanation = "" # 다운로드할 한국어 설명을 저장
        self.initUI()
        self.initThreads()

    def initUI(self):
        self.setWindowTitle('🤖 AI 코드 리팩토링 & 문서화 (PyQt6)')
        self.setGeometry(100, 100, 800, 600) # (x, y, width, height)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. 언어 선택
        lang_layout = QHBoxLayout()
        lang_label = QLabel("1. 언어를 선택하세요:")
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "JavaScript", "C"])
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch() # 공백 추가
        main_layout.addLayout(lang_layout)

        # 2. 원본 코드 입력
        main_layout.addWidget(QLabel("2. 원본 코드를 입력하세요:"))
        self.input_text = QTextEdit()
        self.input_text.setFont(QFont("Courier", 10)) # 고정폭 글꼴
        main_layout.addWidget(self.input_text)

        # 3. 분석 시작 버튼
        self.run_button = QPushButton("✨ AI로 분석하기")
        self.run_button.clicked.connect(self.start_analysis) # 버튼 클릭 시 함수 연결
        main_layout.addWidget(self.run_button)

        # 4. 리팩토링된 코드 출력
        main_layout.addWidget(QLabel("3. AI가 리팩토링한 코드:"))
        self.output_text = QTextEdit()
        self.output_text.setFont(QFont("Courier", 10))
        self.output_text.setReadOnly(True) # 읽기 전용
        main_layout.addWidget(self.output_text)

        # 5. 다운로드 버튼
        self.download_button = QPushButton("🇰🇷 한국어 설명 (.txt) 다운로드")
        self.download_button.clicked.connect(self.download_explanation)
        self.download_button.setEnabled(False) # 처음에는 비활성화
        main_layout.addWidget(self.download_button)

    def initThreads(self):
        """백그라운드 스레드 및 Worker 객체 설정"""
        self.worker_thread = QThread()
        self.worker = OllamaWorker()
        self.worker.moveToThread(self.worker_thread)

        # 시그널 연결
        self.start_analysis_signal.connect(self.worker.run_analysis) # 1
        self.worker.finished.connect(self.on_analysis_finished) # 2

        self.worker_thread.start()

    def start_analysis(self):
        """'분석하기' 버튼 클릭 시 호출됩니다."""
        code = self.input_text.toPlainText()
        language = self.lang_combo.currentText().lower()

        if not code.strip():
            QMessageBox.warning(self, "입력 오류", "코드를 입력하세요.")
            return

        # ⭐️ UI를 멈추지 않기 위해 시그널을 '방출'합니다.
        #    그러면 백그라운드 스레드에서 self.worker.run_analysis가 실행됩니다.
        print("🤖 AI 분석 시작...")
        self.run_button.setEnabled(False)
        self.run_button.setText("분석 중... 🤖")
        self.download_button.setEnabled(False)
        self.output_text.setPlainText("")
        
        self.start_analysis_signal.emit(code, language)

    def on_analysis_finished(self, result: dict):
        """Worker 스레드에서 작업이 완료되면 호출됩니다."""
        print("✅ AI 분석 완료.")
        self.run_button.setEnabled(True)
        self.run_button.setText("✨ AI로 분석하기")

        if result['error']:
            # 에러 발생 시
            QMessageBox.critical(self, "API 오류", f"오류 발생:\n{result['error']}")
            self.output_text.setPlainText("")
        else:
            # 성공 시
            self.output_text.setPlainText(result['refactored_code'])
            self.korean_explanation = result['korean_explanation']
            self.download_button.setEnabled(True) # 다운로드 버튼 활성화

    def download_explanation(self):
        """'다운로드' 버튼 클릭 시 호출됩니다."""
        if not self.korean_explanation:
            return

        # ⭐️ 파일 저장 대화상자 열기
        # 'options = QFileDialog.Options()' 줄을 삭제하고,
        # getSaveFileName 호출에서 'options=options' 인수를 제거했습니다.
        fileName, _ = QFileDialog.getSaveFileName(
            self,
            "한국어 설명 저장",
            "code_explanation_ko.txt", # 기본 파일명
            "Text Files (*.txt);;All Files (*)" # 파일 필터
            # options 인수는 여기에서 필요하지 않으므로 삭제합니다.
        )

        if fileName:
            try:
                with open(fileName, 'w', encoding='utf-8') as f:
                    f.write(self.korean_explanation)
            except Exception as e:
                QMessageBox.critical(self, "파일 저장 오류", f"파일을 저장하는 중 오류 발생:\n{e}")

    def closeEvent(self, event):
        """
        (중요) 앱이 닫힐 때 백그라운드 스레드도 같이 종료합니다.
        """
        print("애플리케이션 종료...")
        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept()

# --- 4. 애플리케이션 실행 ---

if __name__ == '__main__':
    # (Ollama 서버가 실행 중인지 확인하세요!)
    try:
        ollama.list()
    except Exception as e:
        print("❌ Ollama 서버가 실행 중이지 않습니다.")
        print("Ollama를 먼저 실행한 후 이 프로그램을 다시 시작하세요.")
        sys.exit(1)
        
    app = QApplication(sys.argv)
    window = CodeRefactorApp()
    window.show()
    sys.exit(app.exec())