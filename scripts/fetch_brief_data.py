"""Fetch morning brief data: indices OHLC, forex OHLC, VIX, macro calendar, news.
Writes data/latest.json for consumption by the Claude Code routine 'Morning Brief JP'.

Sources :
- Indices + Forex + VIX : yfinance (Yahoo Finance)
- Macro calendar : Forex Factory JSON (public widget endpoint)
- News : BBC News business RSS

Failure-tolerant : si une source échoue, écrit `null` dans le JSON et continue. La routine
Claude Code marquera [?] pour les données manquantes.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import requests
import yfinance as yf

OUT_PATH = Path(__file__).parent.parent / "data" / "latest.json"
PARIS_TZ = ZoneInfo("Europe/Paris")

# Mapping symbol_name → yfinance ticker
INDICES = {
    "DAX": "^GDAXI",
    "CAC": "^FCHI",
    "FTSE": "^FTSE",
    "SPX": "^GSPC",      # S&P 500
    "NDX": "^NDX",       # Nasdaq 100
    "DJI": "^DJI",       # Dow Jones
    "N225": "^N225",     # Nikkei 225
    "HSI": "^HSI",       # Hang Seng
}

FOREX = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
}

VIX_TICKER = "^VIX"


def fetch_ohlc(ticker: str) -> dict | None:
    """Last fully-closed daily OHLC for `ticker` (skip today if session not closed)."""
    try:
        data = yf.Ticker(ticker).history(period="5d", interval="1d")
        if data.empty:
            return None
        today = datetime.now(timezone.utc).date()
        # Prefer the most recent day that is strictly before today (= a closed session)
        closed = [(idx, row) for idx, row in data.iterrows() if idx.date() < today]
        if closed:
            idx, row = closed[-1]
        else:
            idx, row = data.index[-1], data.iloc[-1]
        return {
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
        }
    except Exception as e:
        print(f"  WARN: {ticker} OHLC failed: {e}", file=sys.stderr)
        return None


def fetch_vix() -> dict | None:
    """VIX current value + 24h change %."""
    try:
        data = yf.Ticker(VIX_TICKER).history(period="5d", interval="1d")
        if len(data) < 2:
            return None
        latest = data.iloc[-1]
        previous = data.iloc[-2]
        value = float(latest["Close"])
        change_pct = (value - float(previous["Close"])) / float(previous["Close"]) * 100
        return {
            "value": round(value, 2),
            "change_24h_pct": round(change_pct, 2),
            "date": data.index[-1].strftime("%Y-%m-%d"),
        }
    except Exception as e:
        print(f"  WARN: VIX failed: {e}", file=sys.stderr)
        return None


def fetch_macro_calendar() -> list[dict]:
    """Forex Factory weekly calendar, filtered to today + EUR/USD/GBP + High/Medium impact."""
    try:
        r = requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            headers={"User-Agent": "morning-brief-data/1.0 (+github)"},
            timeout=15,
        )
        r.raise_for_status()
        events = r.json()
        today_paris = datetime.now(PARIS_TZ).date()
        wanted_countries = {"EUR", "USD", "GBP"}
        wanted_impacts = {"High", "Medium"}
        result = []
        for e in events:
            # Date format: "2026-05-20T14:30:00-04:00" or similar ISO 8601
            date_str = e.get("date", "")
            try:
                dt_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                dt_paris = dt_utc.astimezone(PARIS_TZ)
            except (ValueError, TypeError):
                continue
            if dt_paris.date() != today_paris:
                continue
            if e.get("country") not in wanted_countries:
                continue
            if e.get("impact") not in wanted_impacts:
                continue
            result.append({
                "time_paris": dt_paris.strftime("%H:%M"),
                "country": e.get("country", ""),
                "indicator": e.get("title", ""),
                "consensus": e.get("forecast", "") or "",
                "previous": e.get("previous", "") or "",
                "impact": e.get("impact", ""),
            })
        return sorted(result, key=lambda x: x["time_paris"])
    except Exception as e:
        print(f"  WARN: macro calendar failed: {e}", file=sys.stderr)
        return []


def fetch_news() -> list[dict]:
    """BBC News Business RSS, top 8 most recent headlines."""
    try:
        feed = feedparser.parse("https://feeds.bbci.co.uk/news/business/rss.xml")
        out = []
        for entry in feed.entries[:8]:
            out.append({
                "title": entry.get("title", "").strip(),
                "summary": (entry.get("summary", "") or "")[:250].strip(),
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
            })
        return out
    except Exception as e:
        print(f"  WARN: BBC RSS failed: {e}", file=sys.stderr)
        return []


def main() -> int:
    now_utc = datetime.now(timezone.utc)
    print(f"Brief data fetch at {now_utc.isoformat()}", file=sys.stderr)

    print("Fetching indices OHLC...", file=sys.stderr)
    indices = {name: fetch_ohlc(ticker) for name, ticker in INDICES.items()}

    print("Fetching forex OHLC...", file=sys.stderr)
    forex = {name: fetch_ohlc(ticker) for name, ticker in FOREX.items()}

    print("Fetching VIX...", file=sys.stderr)
    vix = fetch_vix()

    print("Fetching macro calendar...", file=sys.stderr)
    macro = fetch_macro_calendar()

    print("Fetching news...", file=sys.stderr)
    news = fetch_news()

    output = {
        "generated_at_utc": now_utc.isoformat(),
        "generated_at_paris": now_utc.astimezone(PARIS_TZ).isoformat(),
        "date_paris": now_utc.astimezone(PARIS_TZ).strftime("%Y-%m-%d"),
        "indices": indices,
        "forex": forex,
        "vix": vix,
        "macro_calendar_today": macro,
        "news_bbc": news,
        "sources_status": {
            "yfinance_indices_ok_count": sum(1 for v in indices.values() if v),
            "yfinance_indices_total": len(indices),
            "yfinance_forex_ok_count": sum(1 for v in forex.values() if v),
            "yfinance_forex_total": len(forex),
            "yfinance_vix_ok": vix is not None,
            "ff_macro_calendar_ok": len(macro) > 0,
            "bbc_news_ok": len(news) > 0,
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
