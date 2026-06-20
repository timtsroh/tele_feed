# PRD: DART 전자공시 텔레그램 피드 봇

## 1. 개요

Google Sheets에 등록된 한국 기업 목록(Light1, Atom1 시트)을 기반으로 금융감독원 DART(전자공시시스템) OpenAPI를 통해 전날 공시를 수집하고, 매일 오전 6시 / 오후 6시 KST Telegram 채널로 자동 발송하는 파이프라인.
`feed_news` 프로젝트와 동일한 기업 목록 및 채널 구조를 재사용하며, 뉴스가 아닌 공식 공시 정보를 피드한다.

---

## 2. 목표

- 관심 기업의 신규 공시(사업보고서, 수시공시, 주요사항보고 등)를 수동 확인 없이 자동 수집
- Telegram 채널을 통해 공시 알림 전달
- GitHub Actions로 완전 자동화 (서버 불필요)
- `feed_news`와 동일한 Google Sheets 기업 목록 공유

---

## 3. DART OpenAPI 개요

| 항목 | 내용 |
|---|---|
| 제공 기관 | 금융감독원 (FSS) |
| API 포털 | https://opendart.fss.or.kr |
| 인증 방식 | API Key (쿼리 파라미터 `crtfc_key`) |
| 기업 식별자 | `corp_code` (8자리 고유 번호) |
| 공시목록 엔드포인트 | `GET https://opendart.fss.or.kr/api/list.json` |

### 3.1 corp_code 조회 전략

Google Sheets의 **D열**에 각 기업의 DART `corp_code`가 미리 기재되어 있다.
실행 시 회사명(B열)과 corp_code(D열)를 함께 읽어 사용한다. 별도 매핑 테이블 구성 불필요.

### 3.2 공시목록 조회 파라미터

| 파라미터 | 설명 | 사용 값 |
|---|---|---|
| `crtfc_key` | API 인증키 | 환경 변수 `DART_API_KEY` |
| `corp_code` | 기업 고유 코드 | 시트 D열에서 읽은 값 |
| `bgn_de` | 시작일 (YYYYMMDD) | 전날 날짜 |
| `end_de` | 종료일 (YYYYMMDD) | 전날 날짜 |
| `last_reprt_at` | 최종보고서 여부 | `N` (전체) |
| `page_count` | 페이지당 건수 | `10` |

### 3.3 주요 공시 유형 (pblntf_ty)

모든 유형 수집 (`pblntf_ty` 파라미터 생략)

| 코드 | 분류 |
|---|---|
| `A` | 정기공시 (사업보고서, 반기보고서 등) |
| `B` | 주요사항보고 (유상증자, 자기주식 등) |
| `C` | 발행공시 |
| `D` | 지분공시 |
| `E` | 기타공시 |
| `F` | 외부감사 관련 |

---

## 4. 주요 구성 요소

| 구성 요소 | 역할 | 세부 내용 |
|---|---|---|
| Google Sheets | 기업 목록 + corp_code 소스 | Light1/Atom1 시트 B열(회사명), D열(corp_code) |
| DART OpenAPI | 공시 수집 | `opendart.fss.or.kr/api/list.json` |
| Telegram Bot | 공시 발송 | Light1 → DART 전용 채널 / Atom1 → DART 전용 채널 |
| GitHub Actions | 스케줄 실행 | 매일 06:00, 18:00 KST 각 1회 |

---

## 5. 외부 연동 정보

| 항목 | 값 |
|---|---|
| Google Sheets URL | `https://docs.google.com/spreadsheets/d/1sfDjoKbrEbKvA0qwMA1nPdcEu628YgNX0A_JLLOB4WA/edit` |
| Light1 시트 | B열(회사명), D열(corp_code) |
| Atom1 시트 | B열(회사명), D열(corp_code) |
| DART API 포털 | `https://opendart.fss.or.kr` |
| DART 공시목록 엔드포인트 | `https://opendart.fss.or.kr/api/list.json` |
| 공시 상세 링크 | `https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}` |
| GitHub 레포 | `https://github.com/timtsroh/tele_feed` |
| 코드 경로 | `feed_dart/` |

---

## 6. 기능 요구사항

### 6.1 Google Sheets 기업 목록 읽기 (`sheets_reader.py`)

- `get_companies_with_corp_code(sheet_id, sheet_name)` 함수
- B열(name_col=2): 회사명, D열(corp_code_col=4): DART corp_code
- 첫 행(헤더) 항상 스킵, 빈 셀 스킵
- `corp_code`가 없는 행은 경고 로그 출력 후 스킵
- 반환 형태: `[(corp_name, corp_code), ...]`

### 6.2 DART 공시 조회 (`dart_fetcher.py`)

- 각 기업의 `corp_code`로 `/api/list.json` 호출
- 조회 기간: **전날 하루** (`bgn_de` = `end_de` = 어제 날짜)
  - `_get_query_date()`: `datetime.now(KST) - timedelta(days=1)` 반환
- 회사당 최대 3건 (`MAX_PER_COMPANY = 3`)
- API 호출 간 0.5초 딜레이 (`DELAY = 0.5`)
- 중복 접수번호(`rcept_no`) 필터링 (동일 실행 내 `seen_rcept_nos` set 공유)
- API status `013` (조회 결과 없음)은 정상으로 처리

**응답 필드 활용:**

| 필드 | 설명 | 활용 |
|---|---|---|
| `rcept_no` | 접수번호 | 상세 링크 생성, 중복 제거 키 |
| `corp_name` | 회사명 | 표시용 |
| `report_nm` | 보고서명 | 공시 제목 |
| `rcept_dt` | 접수일자 (YYYYMMDD) | 회사 헤더에 YYYY-MM-DD 형식으로 표시 |
| `flr_nm` | 공시 제출인 | 표시용 |
| `rm` | 비고 | 정정/첨부 여부 (있을 경우 보고서명 뒤에 `[비고]` 형태로 표시) |

### 6.3 Telegram 발송 (`telegram_sender.py`)

- 한 피드(Light1 또는 Atom1)의 모든 회사 공시를 하나의 메시지로 통합 전송
- Light1 → 환경 변수 `TELEGRAM_DART_ID_Light`
- Atom1 → 환경 변수 `TELEGRAM_DART_ID_Atom`
- HTML `parse_mode` 사용
- 공시가 0건인 회사는 메시지에서 생략
- 전체 공시가 0건이면 메시지 미전송

**메시지 형식:**

```
{title}

<b>{회사명} ({YYYY-MM-DD})</b>
{보고서명}
{공시 상세 링크}
제출인: {제출인명}

<b>{회사명} ({YYYY-MM-DD})</b>
{보고서명} [{비고}]
{공시 상세 링크}
제출인: {제출인명}

```

**실제 출력 예시 (Light1 채널):**

```
📋 등대 포트폴리오 DART 공시피드

<b>HD현대중공업 (2026-03-25)</b>
주요사항보고서(자기주식취득결정)
https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260325000234
제출인: HD현대중공업

<b>디케이락 (2026-03-25)</b>
임원ㆍ주요주주특정증권등소유상황보고서
https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260325000456
제출인: 홍길동

임원ㆍ주요주주특정증권등소유상황보고서
https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260325000457
제출인: 김철수

```

**비고(rm)가 있는 경우 (정정공시 등):**

```
📋 등대 포트폴리오 DART 공시피드

<b>삼성중공업 (2026-03-25)</b>
주요사항보고서(유상증자결정) [정정]
https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260325000789
제출인: 삼성중공업

```

**피드별 제목:**

| 채널 | 제목 |
|---|---|
| Light1 | `📋 등대 포트폴리오 DART 공시피드` |
| Atom1 | `📋 김아톰 포트폴리오 DART 공시피드` |

### 6.4 구글 시트 기록 (`sheets_writer.py`)

- 피드 실행 후 수집된 공시를 로그 시트에 `append_rows`로 추가
- Light1 피드 → `DART1` 시트, Atom1 피드 → `DART2` 시트
- 기록 컬럼: `회사` | `날짜(YYYY.MM.DD)` | `보고자` | `공시번호` | `링크` | `제목`

### 6.5 실행 로직 흐름

```
main.py 실행
  │
  ├─ 환경 변수 로드 (.env 또는 GitHub Secrets)
  │
  ├─ [Light1 피드]
  │     ├─ Light1 시트 B열(회사명) + D열(corp_code) 로드
  │     ├─ 각 회사 DART 공시 조회 (전날 하루, 최대 3건)
  │     ├─ 공시 있는 회사만 메시지 구성
  │     ├─ 통합 메시지 → TELEGRAM_DART_ID_Light 전송
  │     └─ 공시 결과 → DART1 시트 기록
  │
  └─ [Atom1 피드]
        ├─ Atom1 시트 B열(회사명) + D열(corp_code) 로드
        ├─ 각 회사 DART 공시 조회 (전날 하루, 최대 3건)
        ├─ 공시 있는 회사만 메시지 구성
        ├─ 통합 메시지 → TELEGRAM_DART_ID_Atom 전송
        └─ 공시 결과 → DART2 시트 기록
```

---

## 7. 비기능 요구사항

- **Rate Limiting**: 회사별 DART API 호출 사이 0.5초 딜레이
- **에러 처리**: API 호출 실패 시 해당 회사 스킵, 로그 출력 후 계속 진행
- **타임존**: 모든 시간 표시는 KST (UTC+9), `zoneinfo.ZoneInfo("Asia/Seoul")` 사용
- **로그**: 실행 시작/종료, 처리 회사 수, 수집 공시 수, 전송 여부 출력

---

## 8. 파일 구조

```
tele_feed/
├── .github/
│   └── workflows/
│       ├── feed_dart.yml
│       └── feed_news.yml
├── feed_dart/
│   ├── PRD.md
│   ├── main.py             # 진입점 및 오케스트레이션
│   ├── sheets_reader.py    # Google Sheets 연동 (B열 + D열 읽기)
│   ├── dart_fetcher.py     # DART API 연동 (공시 조회)
│   ├── telegram_sender.py  # 메시지 포맷 + Telegram 전송
│   ├── sheets_writer.py    # 공시 결과 Google Sheets 기록
│   ├── template.md         # 출력 양식 참고
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                (gitignore)
└── feed_news/
```

---

## 9. 환경 변수 / GitHub Secrets

| 변수명 | 설명 | GitHub Secret명 |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google 서비스 계정 JSON | `GOOGLE_SERVICE_ACCOUNT_JSON` |
| `GOOGLE_SHEET_ID` | 스프레드시트 ID | `GOOGLE_SHEET_ID` |
| `DART_API_KEY` | DART OpenAPI 인증키 | `DART_API_KEY` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | `TELEGRAM_BOT_TOKEN` |
| `TELEGRAM_DART_ID_Light` | Light 포트폴리오 DART 채널 ID | `TELEGRAM_DART_ID_LIGHT` |
| `TELEGRAM_DART_ID_Atom` | Atom 포트폴리오 DART 채널 ID | `TELEGRAM_DART_ID_ATOM` |

---

## 10. GitHub Actions 스케줄

```yaml
# .github/workflows/feed_dart.yml
on:
  schedule:
    - cron: '0 21 * * *'   # KST 06:00 (UTC 21:00 전날), 매일 1회
    - cron: '0 9 * * *'    # KST 18:00 (UTC 09:00), 매일 1회
  workflow_dispatch:          # 수동 트리거 (테스트용)
```

---

## 11. 의존성 (requirements.txt)

```
gspread==6.1.4
google-auth==2.38.0
requests==2.32.3
python-dotenv==1.1.0
pytz==2024.2
```
