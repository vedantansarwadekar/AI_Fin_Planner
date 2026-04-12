import requests
from datetime import date, timedelta
from src.config import FINNHUB_API_KEY

def get_company_news(symbol: str, days: int = 7):
    to_date = date.today()
    from_date = to_date - timedelta(days=days)

    url = (
        "https://finnhub.io/api/v1/company-news"
        f"?symbol={symbol}&from={from_date}&to={to_date}&token={FINNHUB_API_KEY}"
    )
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()

    return [
        {
            "headline": item.get("headline"),
            "source": item.get("source"),
            "url": item.get("url"),
            "summary": item.get("summary"),
        }
        for item in data[:5]
    ]
