# 📊 Financial News RAG Market Analysis

최근 경제 뉴스와 주가 데이터를 함께 활용하여  
사용자의 질문에 대해 **이슈 요약 + 종목 흐름 + 근거 출처**를 제공하는 RAG 기반 시스템입니다.

예시 질문
> 삼성전자 최근 일주일 뉴스와 주가 흐름 같이 설명해줘

---

# 🧩 Project Overview

LLM이 최신 금융 정보를 활용할 수 있도록  
**뉴스 데이터 + 주가 데이터**를 함께 검색하여 답변을 생성합니다.

✔ 최신 뉴스 기반 정보 제공  
✔ 실제 시장 데이터 활용  
✔ 근거 기반 응답 생성  
✔ 자연어 질문 처리 가능  

---

# 🧠 Tech Stack

### Data
- RSS Crawling
- News Crawling
- Market Data API

### Database
- Supabase (PostgreSQL)

### Programming Language
- Python
- SQL

### RAG
- Embedding Model
- Vector Search
- LLM API

---

# 📁 프로젝트 구조

```text
src/
├─ analysis/
│  └─ 데이터 테스트 및 실험 코드
│
├─ common/
│  ├─ 공통 코드 및 공통 파일
│  ├─ *_const.py      # 공통 상수, 변수 정의
│  ├─ *_utils.py      # 공통 함수
│  └─ *_logger.py     # 로그 설정
│
├─ config/
│  └─ 환경설정 파일
│
├─ data_access/
│  └─ DB 접근 계층(SQL 작성 및 실행)
│     ├─ insert_news()
│     └─ get_news_list()
│
├─ database/
│  ├─ DB 연결 관리 파일
│  └─ models/
│     └─ SQLAlchemy 모델 정의
│
└─ collector/
   └─ 데이터 수집 코드
      ├─ 뉴스 RSS 수집
      └─ 주가 API 호출
```

# 📝 Blog

## 프로젝트 관련 정리 내용

👉 RAG 개념 정리 - https://yooninging.tistory.com/124  
👉 LangChain의 개념 - https://ejji.tistory.com/20  
