import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from sheets_reader import get_companies_with_corp_code
from dart_fetcher import fetch_disclosures
from telegram_sender import build_combined_message, send_message
from sheets_writer import write_disclosures_to_sheet


KST = ZoneInfo("Asia/Seoul")
KR_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def get_yesterday_str() -> str:
    yesterday = datetime.now(KST) - timedelta(days=1)
    yy = yesterday.strftime("%y")
    m = str(yesterday.month)
    d = str(yesterday.day)
    wd = KR_WEEKDAYS[yesterday.weekday()]
    return f"'{yy}.{m}.{d}{wd}"

DART_FEEDS = [
    {
        "sheet_name": "Light",
        "chat_id_env": "TELEGRAM_DART_ID_Light",
        "title": "📋 등대 포트폴리오 DART 공시피드",
        "log_sheet": "DART1",
    },
    {
        "sheet_name": "Atom",
        "chat_id_env": "TELEGRAM_DART_ID_Atom",
        "title": "📋 김아톰 포트폴리오 DART 공시피드",
        "log_sheet": "DART2",
    },
]


def run_feed(sheet_id: str, sheet_name: str, chat_id_env: str, title: str, log_sheet: str = ""):
    print(f"\n{'='*50}")
    print(f"[{sheet_name}] DART 공시 피드 시작")
    print(f"{'='*50}")

    # 1. 회사 목록 + corp_code 로드
    print(f"\n[1] {sheet_name} 시트에서 회사 목록 로드 중...")
    try:
        companies = get_companies_with_corp_code(sheet_id, sheet_name)
    except Exception as e:
        print(f"[ERROR] 회사 목록 로드 실패: {e}")
        return

    print(f"  → {len(companies)}개 회사 로드: {', '.join(f'{n}({c})' for n, c in companies)}")
    if not companies:
        print("[INFO] 회사 목록이 비어 있어 스킵합니다.")
        return

    # 2. 각 회사별 공시 조회
    print(f"\n[2] DART 공시 조회 중...")
    seen_rcept_nos: set = set()
    company_disclosures: dict = {}
    total_items = 0

    for corp_name, corp_code in companies:
        print(f"  → [{corp_name} ({corp_code})] 조회 중...")
        items = fetch_disclosures(corp_code, seen_rcept_nos)
        if items:
            company_disclosures[corp_name] = items
            total_items += len(items)
            print(f"     {len(items)}건 수집")
        else:
            print(f"     신규 공시 없음, 스킵")

    # 3. 통합 메시지 전송
    print(f"\n[3] Telegram 전송 중... ({chat_id_env} / 총 {total_items}건)")
    date_str = get_yesterday_str()
    message = build_combined_message(company_disclosures, title, date_str)
    success = send_message(message, chat_id_env)
    print(f"     {'전송 완료' if success else '전송 실패'}")

    # 4. 구글 시트 기록
    if log_sheet and company_disclosures:
        print(f"\n[4] 구글 시트 기록 중... ({log_sheet})")
        write_disclosures_to_sheet(sheet_id, log_sheet, company_disclosures)


def main():
    load_dotenv()

    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "1sfDjoKbrEbKvA0qwMA1nPdcEu628YgNX0A_JLLOB4WA")

    start_time = datetime.now(KST)
    print(f"=== DART 공시 피드 시작: {start_time.strftime('%Y-%m-%d %H:%M KST')} ===")

    for feed in DART_FEEDS:
        run_feed(
            sheet_id=sheet_id,
            sheet_name=feed["sheet_name"],
            chat_id_env=feed["chat_id_env"],
            title=feed["title"],
            log_sheet=feed["log_sheet"],
        )

    end_time = datetime.now(KST)
    elapsed = (end_time - start_time).seconds
    print(f"\n=== 전체 완료: {end_time.strftime('%Y-%m-%d %H:%M KST')} | 소요 {elapsed}초 ===")


if __name__ == "__main__":
    main()
