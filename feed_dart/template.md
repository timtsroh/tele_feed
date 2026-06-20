# Telegram 출력 템플릿

## 기본 구조

```
{title}

<b>{회사명} ({YYYY-MM-DD})</b>
{보고서명} [{비고}]
{공시 상세 링크}
제출인: {제출인명}

<b>{회사명} ({YYYY-MM-DD})</b>
...
```

---

## 채널별 제목 (title)

| 채널 | 제목 |
|---|---|
| Light1 | `📋 등대 포트폴리오 DART 공시피드` |
| Atom1 | `📋 김아톰 포트폴리오 DART 공시피드` |

---

## 실제 출력 예시

### 공시가 있는 경우

```
📋 등대 포트폴리오 DART 공시피드

HD현대중공업 (2026-03-25)
주요사항보고서(자기주식취득결정)
https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260325000234
제출인: HD현대중공업

디케이락 (2026-03-25)
임원ㆍ주요주주특정증권등소유상황보고서
https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260325000456
제출인: 홍길동

임원ㆍ주요주주특정증권등소유상황보고서
https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260325000457
제출인: 김철수
```

### 비고(rm)가 있는 경우 (정정공시 등)

```
📋 등대 포트폴리오 DART 공시피드

삼성중공업 (2026-03-25)
주요사항보고서(유상증자결정) [정정]
https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260325000789
제출인: 삼성중공업
```

### 공시가 없는 경우

전송하지 않음 (메시지 미발송)

---

## 필드 설명

| 필드 | 소스 | 형식 |
|---|---|---|
| `title` | `main.py` DART_FEEDS 설정 | 고정 문자열 |
| 회사명 + 날짜 | DART API `corp_name` + `rcept_dt` | HTML `<b>회사명 (YYYY-MM-DD)</b>` |
| 보고서명 | DART API `report_nm` | 일반 텍스트 |
| 비고 | DART API `rm` | 있을 때만 `[비고내용]` 추가 |
| 링크 | DART API `rcept_no` 조합 | `https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}` |
| 제출인 | DART API `flr_nm` | 일반 텍스트 |
| 접수일 | DART API `rcept_dt` (YYYYMMDD) | `YYYY-MM-DD` 로 변환 |

---

## 전송 규칙

- 공시가 있는 회사만 메시지에 포함 (없는 회사 생략)
- 회사당 최대 3건
- 전체 공시 0건이면 메시지 미전송
- `parse_mode`: HTML (회사명 볼드 처리)
- `disable_web_page_preview`: True (링크 미리보기 비활성)

---

## 실행 스케줄

매일 **00:01 KST** 실행 → 전날 하루 공시 조회
