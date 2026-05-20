# Morning Brief Data

Données financières auto-fetchées pour la routine Claude Code `Morning Brief JP`.

**URL raw consommée par la routine** :
```
https://raw.githubusercontent.com/chatelainyoann-pixel/morning-brief-data/main/data/latest.json
```

## Fonctionnement

GitHub Actions tourne lun-ven à 5h et 6h UTC (= 7h-8h Paris selon DST) et fetch :

- **Indices OHLC J-1** : DAX, CAC 40, FTSE 100, S&P 500, Nasdaq 100, Dow Jones, Nikkei 225, Hang Seng (via yfinance / Yahoo Finance)
- **Forex OHLC J-1** : EUR/USD, GBP/USD (via yfinance)
- **VIX** : valeur courante + variation 24h (via yfinance)
- **Calendrier macro EU+US** du jour, high/medium impact (via Forex Factory JSON public)
- **News BBC Business** : top 8 headlines (via RSS)

Le résultat est écrit dans `data/latest.json` puis commit + push.

La routine Claude Code `Morning Brief JP` (cron 30 6 * * 1-5 UTC) fait un `WebFetch` sur l'URL raw, compose le brief HTML à partir du JSON, et drafte l'email via le MCP Gmail.

## Structure du JSON

```json
{
  "generated_at_utc": "2026-05-21T05:00:23+00:00",
  "generated_at_paris": "2026-05-21T07:00:23+02:00",
  "date_paris": "2026-05-21",
  "indices": {
    "DAX": {"open": 24300, "high": 24450, "low": 24280, "close": 24400, "date": "2026-05-20"},
    "CAC": {...},
    ...
  },
  "forex": {
    "EURUSD": {"open": 1.1620, "high": 1.1640, "low": 1.1610, "close": 1.1625, "date": "2026-05-20"},
    "GBPUSD": {...}
  },
  "vix": {"value": 18.4, "change_24h_pct": -2.1, "date": "2026-05-20"},
  "macro_calendar_today": [
    {"time_paris": "11:00", "country": "EUR", "indicator": "Flash PMI", "consensus": "...", "previous": "...", "impact": "High"}
  ],
  "news_bbc": [
    {"title": "...", "summary": "...", "url": "...", "published": "..."}
  ],
  "sources_status": {
    "yfinance_indices_ok_count": 8,
    "yfinance_indices_total": 8,
    ...
  }
}
```

Si une source échoue, le champ correspondant est `null` (indices/forex/vix) ou `[]` (calendar/news). La routine marque alors `[?]` dans le brief.

## Trigger manuel

GitHub → Actions → **Daily Brief Data Fetch** → **Run workflow** → branch `main`.

Le 1er run peut être déclenché manuellement après le push initial pour générer `data/latest.json`.

## Maintenance

Si yfinance casse (changement Yahoo Finance) : remplacer par appel à `stooq.com/q/l/?s=...` en CSV.
Si Forex Factory bouge l'endpoint : alternative `tradingeconomics.com/calendar` ou clé Finnhub free tier.

## Licence

MIT. Sources publiques (Yahoo Finance, Forex Factory, BBC). Aucun secret commit dans ce repo.
