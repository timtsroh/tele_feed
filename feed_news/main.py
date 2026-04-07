import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from sheets_reader import get_companies, get_companies_with_tickers
import news_fetcher
from telegram_sender import build_combined_message, build_empty_message, send_message
from sheets_writer import write_news_to_sheet


KST = ZoneInfo("Asia/Seoul")

# Naver 검색 피드 (한국 기업)
NAVER_FEEDS = [
    {"sheet_name": "Light", "col": 2, "chat_id_env": "TELEGRAM_NEWS_ID_Light", "title": "📌 등대 포트폴리오 뉴스피드 (국내)", "log_sheet": "News1"},
    {"sheet_name": "Atom",  "col": 2, "chat_id_env": "TELEGRAM_NEWS_ID_Atom",  "title": "📌 김아톰 포트폴리오 뉴스피드",      "log_sheet": "News2"},
]

# NewsAPI 검색 피드 (외국 기업) — Light 채널로 전송
NEWSAPI_FEEDS = [
    {"sheet_name": "ENG", "col": 2, "chat_id_env": "TELEGRAM_NEWS_ID_Light", "title": "📌 등대 포트폴리오 뉴스피드 (해외)", "log_sheet": "News3"},
]


def run_feed(sheet_id: str, sheet_name: str, col: int, chat_id_env: str, search_fn, title: str, log_sheet: str = ""):
    print(f"\n{'='*50}")
    print(f"[{sheet_name}] 피드 시작")
    print(f"{'='*50}")

    # 1. 회사 목록 로드
    print(f"\n[1] {sheet_name} 시트에서 회사 목록 로드 중...")
    try:
        companies = get_companies(sheet_id, sheet_name, col)
    except Exception as e:
        print(f"[ERROR] 회사 목록 로드 실패: {e}")
        return

    print(f"  → {len(companies)}개 회사 로드: {', '.join(companies)}")

    if not companies:
        print("[INFO] 회사 목록이 비어 있어 스킵합니다.")
        return

    # 2. 각 회사별 뉴스 검색
    print(f"\n[2] 뉴스 검색 중...")
    seen_urls: set = set()
    company_news: dict = {}
    total_articles = 0

    for company in companies:
        print(f"  → [{company}] 검색 중...")
        news_items = search_fn(company, seen_urls)
        if news_items:
            company_news[company] = news_items
            total_articles += len(news_items)
            print(f"     {len(news_items)}건 수집")
        else:
            print(f"     관련 뉴스 없음, 스킵")

    # 3. 통합 메시지 전송
    print(f"\n[3] Telegram 전송 중... ({chat_id_env} / 총 {total_articles}건)")
    if not company_news:
        message = build_empty_message(title)
    else:
        message = build_combined_message(company_news, title)
    success = send_message(message, chat_id_env)
    print(f"     {'전송 완료' if success else '전송 실패'}")

    # 4. 구글 시트 기록
    if log_sheet and company_news:
        print(f"\n[4] 구글 시트 기록 중... ({log_sheet})")
        write_news_to_sheet(sheet_id, log_sheet, company_news)


def run_eng_feed(sheet_id: str, sheet_name: str, chat_id_env: str, title: str, log_sheet: str = ""):
    print(f"\n{'='*50}")
    print(f"[{sheet_name}] 피드 시작")
    print(f"{'='*50}")

    print(f"\n[1] {sheet_name} 시트에서 회사 목록 로드 중...")
    try:
        companies = get_companies_with_tickers(sheet_id, sheet_name)
    except Exception as e:
        print(f"[ERROR] 회사 목록 로드 실패: {e}")
        return

    print(f"  → {len(companies)}개 회사 로드: {', '.join(f'{n}({t})' for n, t in companies)}")
    if not companies:
        print("[INFO] 회사 목록이 비어 있어 스킵합니다.")
        return

    print(f"\n[2] 뉴스 검색 중...")
    seen_urls: set = set()
    company_news: dict = {}
    total_articles = 0

    for name, ticker in companies:
        print(f"  → [{name} ({ticker})] 검색 중...")
        news_items = news_fetcher.search_eng(ticker, seen_urls)
        if news_items:
            company_news[name] = news_items
            total_articles += len(news_items)
            print(f"     {len(news_items)}건 수집")
        else:
            print(f"     관련 뉴스 없음, 스킵")

    print(f"\n[3] Telegram 전송 중... ({chat_id_env} / 총 {total_articles}건)")
    if not company_news:
        message = build_empty_message(title)
    else:
        message = build_combined_message(company_news, title)
    success = send_message(message, chat_id_env)
    print(f"     {'전송 완료' if success else '전송 실패'}")

    # 4. 구글 시트 기록
    if log_sheet and company_news:
        print(f"\n[4] 구글 시트 기록 중... ({log_sheet})")
        write_news_to_sheet(sheet_id, log_sheet, company_news)


def main():
    load_dotenv()

    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "1sfDjoKbrEbKvA0qwMA1nPdcEu628YgNX0A_JLLOB4WA")

    start_time = datetime.now(KST)
    print(f"=== 뉴스 피드 시작: {start_time.strftime('%Y-%m-%d %H:%M KST')} ===")

    # 1단계: 한국 기업 뉴스 (Naver)
    print(f"\n{'#'*50}")
    print(f"# [1단계] 한국 기업 뉴스 — Naver")
    print(f"{'#'*50}")
    for feed in NAVER_FEEDS:
        run_feed(
            sheet_id=sheet_id,
            sheet_name=feed["sheet_name"],
            col=feed["col"],
            chat_id_env=feed["chat_id_env"],
            search_fn=news_fetcher.search_naver,
            title=feed["title"],
            log_sheet=feed["log_sheet"],
        )

    # 2단계: 외국 기업 뉴스 (Marketaux + Alpha Vantage)
    print(f"\n{'#'*50}")
    print(f"# [2단계] 외국 기업 뉴스 — Marketaux + Alpha Vantage")
    print(f"{'#'*50}")
    for feed in NEWSAPI_FEEDS:
        run_eng_feed(
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
