# PRD: 주식 뉴스 텔레그램 피드 봇

## 1. 개요

Google Sheets에 등록된 기업 목록을 기반으로 국내·해외 뉴스를 수집하고, 매일 2회(오전 6시 / 오후 6시 KST) Telegram 채널로 자동 발송하는 파이프라인.

- **국내 기업**: Naver 뉴스 OpenAPI
- **해외 기업**: Marketaux → Finnhub → Alpha Vantage (순차 보완)

---

## 2. 목표

- 관심 기업 목록의 최신 뉴스를 수동 검색 없이 자동 수집
- Telegram 채널을 통해 팀/개인에게 뉴스 알림 전달
- GitHub Actions로 완전 자동화 (서버 불필요)

---

## 3. 주요 구성 요소

| 구성 요소 | 역할 | 세부 내용 |
|---|---|---|
| Google Sheets | 기업 목록 소스 | Light1·Atom1 시트 B열(국내), Light2 시트 B열(회사명)·D열(티커) |
| Naver 뉴스 OpenAPI | 국내 뉴스 수집 | 회사명 키워드 검색 |
| Marketaux | 해외 뉴스 수집 (주) | 티커 심볼 검색, 100 req/일 |
| Finnhub | 해외 뉴스 수집 (보조1) | 티커 심볼 검색, 60 req/분 |
| Alpha Vantage | 해외 뉴스 수집 (보조2) | 티커 심볼 검색, 25 req/일 |
| Telegram Bot | 뉴스 발송 | Light1/Atom1/Light2 각각 채널로 전송 |
| GitHub Actions | 스케줄 실행 | 매일 06:00, 18:00 KST |

---

## 4. 외부 연동 정보

| 항목 | 값 |
|---|---|
| Google Sheets URL | `https://docs.google.com/spreadsheets/d/1sfDjoKbrEbKvA0qwMA1nPdcEu628YgNX0A_JLLOB4WA/edit` |
| Light1 시트 | B열: 국내 기업명 |
| Atom1 시트 | B열: 국내 기업명 |
| Light2 시트 | B열: 해외 기업명, D열: 티커 심볼 |
| GitHub 레포 | `https://github.com/timtsroh/tele_feed` |
| 코드 경로 | `feed_news/` |

---

## 5. 기능 요구사항

### 5.1 Google Sheets 기업 목록 읽기 (`sheets_reader.py`)

- gspread 라이브러리 사용
- 국내: Light1·Atom1 시트 B열에서 회사명 읽기
- 해외: Light2 시트 B열(회사명) + D열(티커) 쌍으로 읽기
- 첫 행(헤더) 항상 스킵, 빈 셀 스킵
- 인증: 서비스 계정(Service Account) JSON → GitHub Secret `GOOGLE_SERVICE_ACCOUNT_JSON`

### 5.2 국내 뉴스 수집 — Naver 뉴스 OpenAPI (`news_fetcher.py`)

- 각 회사명으로 Naver 뉴스 OpenAPI 호출
- 파라미터: `display=10`, `sort=date` (최신순)
- 시간 필터: 실행 시점 기준 **12시간 이내** 기사만 수집
- 관련성 필터: 제목+본문 요약에 회사명 **2회 이상** 등장 시만 수집
- 회사당 최대 3건, 중복 URL 제외

### 5.3 해외 뉴스 수집 — Marketaux + Finnhub + Alpha Vantage (`news_fetcher.py`)

- Light2 시트의 티커 심볼로 검색
- 시간 필터: 실행 시점 기준 **12시간 이내** 기사만 수집
- 관련성 필터: 제목+본문 요약에 회사명 **1회 이상** 등장 시만 수집
- 수집 순서: Marketaux → (부족 시) Finnhub → (부족 시) Alpha Vantage
- 회사당 최대 3건, 중복 URL 제외

### 5.4 Telegram 발송 (`telegram_sender.py`)

- 피드별 모든 회사 뉴스를 하나의 메시지로 통합 전송
- Light → `TELEGRAM_NEWS_ID_Light` 채널 (국내 + 해외)
- Atom → `TELEGRAM_NEWS_ID_Atom` 채널 (국내만)
- HTML `parse_mode` 사용 (회사명 볼드 + 번호)

**메시지 형식:**

```
{title}
🕐 {YYYY-MM-DD요일} {6am|6pm} (최근 12시간 뉴스)

<b>1. {회사명}</b>
{기사 제목}
{기사 URL}
{언론사} | {YYYY-MM-DD HH:MM KST}

{기사 제목}
{기사 URL}
{언론사} | {YYYY-MM-DD HH:MM KST}


<b>2. {회사명}</b>
{기사 제목}
{기사 URL}
{YYYY-MM-DD HH:MM KST}

```

- 타임스탬프: 실행 시각이 정오 이전이면 `6am`, 정오 이후이면 `6pm`
- 요일: KST 기준 한글 (월/화/수/목/금/토/일)
- 언론사명이 없는 경우 날짜만 표시
- 회사 간 빈 줄 2개 (마지막 기사 빈 줄 + 회사 구분 빈 줄)

**실제 출력 예시 (Light1 국내 채널, 오전 실행):**

```
📌 등대 포트폴리오 뉴스피드 (국내)
🕐 2026-03-30월 6am (최근 12시간 뉴스)

<b>1. 에스티팜</b>
에스티팜, 올리고 원료의약품 수출 계약 체결
https://www.hankyung.com/article/...
한국경제 | 2026-03-30 05:32 KST

에스티팜 1분기 실적 전망 상향 조정
https://www.mk.co.kr/article/...
매일경제 | 2026-03-30 02:15 KST


<b>2. 올릭스</b>
올릭스, RNAi 치료제 기술 수출 계약
https://www.edaily.co.kr/article/...
이데일리 | 2026-03-30 04:20 KST

```

**실제 출력 예시 (Light1 국내 채널, 오후 실행):**

```
📌 등대 포트폴리오 뉴스피드 (국내)
🕐 2026-03-30월 6pm (최근 12시간 뉴스)

<b>1. 에스티팜</b>
...
```

**피드별 제목:**

| 채널 | 피드 | 제목 |
|---|---|---|
| Light1 | 국내 (Naver) | `📌 등대 포트폴리오 뉴스피드 (국내)` |
| Atom1 | 국내 (Naver) | `📌 김아톰 포트폴리오 뉴스피드` |
| Light2 | 해외 | `📌 등대 포트폴리오 뉴스피드 (해외)` |

### 5.5 구글 시트 기록 (`sheets_writer.py`)

- 피드 실행 후 수집된 뉴스를 로그 시트 **2행에 삽입** (기존 데이터 아래로 밀림)
- Light1 국내 → `News1` 시트, Atom1 국내 → `News2` 시트, Light2 해외 → `News3` 시트
- 기록 컬럼: `날짜(YYYY-MM-DD)` | `시간(HH:MM)` | `언론사` | `링크` | `회사명` | `제목`

### 5.6 실행 로직 흐름

```
main.py 실행
  │
  ├─ [1단계] 국내 기업 뉴스 — Naver
  │     ├─ [Light1] Light1 시트 B열 회사 목록 로드
  │     │         → Naver 검색 → TELEGRAM_NEWS_ID_Light 전송 → News1 시트 기록
  │     └─ [Atom1]  Atom1 시트 B열 회사 목록 로드
  │                → Naver 검색 → TELEGRAM_NEWS_ID_Atom 전송 → News2 시트 기록
  │
  └─ [2단계] 해외 기업 뉴스 — Marketaux + Finnhub + Alpha Vantage
        └─ [Light2] Light2 시트 B열(회사명) + D열(티커) 로드
                 → Marketaux → Finnhub → Alpha Vantage 순 검색
                 → TELEGRAM_NEWS_ID_Light 전송 → News3 시트 기록
```

---

## 6. 비기능 요구사항

- **Rate Limiting**: 회사별 API 호출 사이 0.5초 딜레이
- **에러 처리**: API 호출 실패 시 해당 회사 스킵, 로그 출력 후 계속 진행
- **타임존**: 모든 시간 표시는 KST (UTC+9), `zoneinfo.ZoneInfo("Asia/Seoul")` 사용
- **로그**: 실행 시작/종료, 처리 회사 수, 전송 건수 출력

---

## 7. 파일 구조

```
tele_feed/
├── .github/
│   └── workflows/
│       ├── feed_dart.yml
│       └── feed_news.yml
├── feed_news/
│   ├── PRD.md
│   ├── main.py               # 실행 진입점
│   ├── sheets_reader.py      # Google Sheets 읽기
│   ├── news_fetcher.py       # Naver / Marketaux / Finnhub / Alpha Vantage 검색
│   ├── telegram_sender.py    # Telegram 메시지 포맷 + 전송
│   ├── sheets_writer.py      # 뉴스 결과 Google Sheets 기록
│   ├── template.md           # 출력 양식 참고
│   ├── requirements.txt
│   ├── .gitignore
│   ├── .env.example
│   └── .env                  (gitignore)
└── feed_dart/
```

---

## 8. 환경 변수 / GitHub Secrets

| 변수명 | 설명 | GitHub Secret명 |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google 서비스 계정 JSON | `GOOGLE_SERVICE_ACCOUNT_JSON` |
| `GOOGLE_SHEET_ID` | 스프레드시트 ID | `GOOGLE_SHEET_ID` |
| `NAVER_CLIENT_ID` | Naver OpenAPI Client ID | `NAVER_CLIENT_ID` |
| `NAVER_CLIENT_SECRET` | Naver OpenAPI Client Secret | `NAVER_CLIENT_SECRET` |
| `MARKETAUX_API_KEY` | Marketaux API 토큰 (해외 뉴스 주) | `MARKETAUX_API_KEY` |
| `FINNHUB_API_KEY` | Finnhub API 키 (해외 뉴스 보조1) | `FINNHUB_API_KEY` |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage API 키 (해외 뉴스 보조2) | `ALPHA_VANTAGE_API_KEY` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | `TELEGRAM_BOT_TOKEN` |
| `TELEGRAM_NEWS_ID_Light` | Light 포트폴리오 Telegram 채널 ID | `TELEGRAM_NEWS_ID_LIGHT` |
| `TELEGRAM_NEWS_ID_Atom` | Atom 포트폴리오 Telegram 채널 ID | `TELEGRAM_NEWS_ID_ATOM` |

---

## 9. GitHub Actions 스케줄

```yaml
# .github/workflows/feed_news.yml
on:
  schedule:
    - cron: '0 21 * * *'   # KST 06:00 (UTC 21:00 전날), 매일 1회
    - cron: '0 9 * * *'    # KST 18:00 (UTC 09:00), 매일 1회
  workflow_dispatch:          # 수동 트리거 (테스트용)
```
