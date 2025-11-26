import sys
import subprocess
import time

# --- 0. 설치할 항목 정의 ---
MODEL_TO_DOWNLOAD = 'llama3:8b'
LIBRARIES_TO_INSTALL = ['ollama', 'PyQt6']
CHECK_FILE_NAME = 'AICodeRefactorer.exe' # 메인 프로그램 이름

print("--- AI 모델 및 라이브러리 자동 설치 ---")
print(f"'{CHECK_FILE_NAME}'에 필요한 항목들을 설치합니다.")
print("이 작업은 인터넷 속도와 컴퓨터 성능에 따라 몇 분에서 몇십 분까지 걸릴 수 있습니다.")
print("설치가 완료될 때까지 절대로 이 창을 닫지 마세요...\n")
print("-" * 60)

# --- 1. 필수 Python 라이브러리 설치 ---
print(f"\n1. 필수 Python 라이브러리 설치를 시작합니다...")
print(f"   설치 대상: {', '.join(LIBRARIES_TO_INSTALL)}")

# sys.executable은 현재 실행 중인 파이썬의 경로를 사용합니다.
# 이렇게 하면 가상환경 등에서도 정확한 pip를 찾아 실행합니다.
try:
    command = [sys.executable, "-m", "pip", "install"] + LIBRARIES_TO_INSTALL
    
    # check=True: 설치 실패 시 예외를 발생시킵니다.
    # encoding='utf-8': 한글 출력이 깨지지 않도록 합니다.
    subprocess.run(command, check=True, encoding='utf-8')
    
    print("\n   [성공] 모든 라이브러리가 성공적으로 설치/확인되었습니다.")

except subprocess.CalledProcessError as e:
    print("\n   [치명적 오류] Python 라이브러리 설치에 실패했습니다!")
    print("   인터넷 연결을 확인하세요.")
    print(f"   오류 상세: {e}")
    print("-" * 60)
    input("   엔터 키를 누르면 창이 닫힙니다...")
    sys.exit(1)
except FileNotFoundError:
    print("\n   [치명적 오류] 'pip' 명령을 찾을 수 없습니다.")
    print("   Python이 올바르게 설치되었는지 확인하세요.")
    print("-" * 60)
    input("   엔터 키를 누르면 창이 닫힙니다...")
    sys.exit(1)

# --- 라이브러리 설치가 성공한 후에 ollama를 import 합니다. ---
try:
    import ollama
except ImportError:
    print("\n   [오류] 'ollama' 라이브러리를 import할 수 없습니다.")
    print("   설치가 완료되었으나, 스크립트를 다시 실행해야 할 수도 있습니다.")
    input("   엔터 키를 누르면 창이 닫힙니다...")
    sys.exit(1)


# --- 2. Ollama 서버 확인 ---
print("\n2. Ollama 서버에 연결을 시도 중입니다...")
try:
    ollama.list()
    print("   [성공] Ollama 서버가 응답했습니다.")
    
except Exception as e:
    print("\n   [치명적 오류] Ollama 서버에 연결할 수 없습니다!")
    print("   Ollama 프로그램이 설치되어 있고 실행 중인지 확인하세요.")
    print("   프로그램을 종료합니다.")
    print("-" * 60)
    input("   엔터 키를 누르면 창이 닫힙니다...")
    sys.exit(1)

# --- 3. 모델 다운로드 ---
print(f"\n3. '{MODEL_TO_DOWNLOAD}' 모델 다운로드를 시작합니다...")
try:
    stream = ollama.pull(MODEL_TO_DOWNLOAD, stream=True)
    last_status = ""
    last_percent = -1

    for chunk in stream:
        if 'status' in chunk:
            status = chunk['status']
            if status != last_status:
                print(f"\n   [상태] {status}")
                last_status = status

        if 'total' in chunk and 'completed' in chunk:
            total = chunk['total']
            completed = chunk['completed']
            percent = round((completed / total) * 100)
            
            if percent != last_percent:
                gb_completed = completed / (1024**3)
                gb_total = total / (1024**3)
                print(f"   [진행] {gb_completed:.2f} GB / {gb_total:.2f} GB ({percent}%)", end='\r')
                last_percent = percent

    print("\n\n" + "-" * 60)
    print("🎉 [설치 완료] 모든 라이브러리와 AI 모델이 성공적으로 설치되었습니다.")
    print(f"이제 이 창을 닫고, '{CHECK_FILE_NAME}'을 실행해 주세요.")
    print("-" * 60)

except Exception as e:
    print(f"\n   [오류] 모델 다운로드 중 문제가 발생했습니다: {e}")
    print("   인터넷 연결을 확인하거나 Ollama를 재시작해 보세요.")
    print("-" * 60)
    input("   엔터 키를 누르면 창이 닫힙니다...")
    sys.exit(1)

input("   엔터 키를 누르면 창이 닫힙니다...")
sys.exit(0)