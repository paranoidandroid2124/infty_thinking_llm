# 추론 반복 프롬프팅 구현

python -r requirements.txt 로 깔고, 가상환경 .env 호출

.env에는

SECRET_KEY=my_secret_key
GOOGLE_API_KEY= YOUR GOOGLE API KEY 형식으로 입력.

아나콘다에서 frontend 디렉토리로 접근 후에 python app.py 실행하면 커널 열려서 접속 가능.

1. 메인화면, 우하단의 숫자 5는 재귀호출 횟수로, 늘리면 LLM이 생성 답변을 다시 인풋에 집어넣고 답변을 개선하는 방식으로 성능 개선
![1](https://github.com/user-attachments/assets/1047c191-c103-468a-821e-5bb5532337d1)  

2. chat.json 내부 구조. 빈 파일을 만들고 {} 적으면 초기화
![2](https://github.com/user-attachments/assets/59285afa-bfa2-4d71-b419-0ae472d45d76)  

3. prompt 부분을 지금 수학용으로 맞춰놨고, 번역 프롬프트 등 자유롭게 수정하면 됨
![3](https://github.com/user-attachments/assets/bbd4d03a-1381-4c7b-a165-dd3eaf2121d9)  

4. 예시
![4](https://github.com/user-attachments/assets/b9418fdc-56c0-4611-a532-2203720bdeb2)  
