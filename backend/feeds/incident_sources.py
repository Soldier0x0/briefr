"""Config for Case Studies incident/news RSS sources."""

INCIDENT_RSS_SOURCES: list[dict[str, str]] = [
    {
        "id": "hackernews",
        "label": "The Hacker News",
        "url": "https://feeds.feedburner.com/TheHackersNews",
    },
    {
        "id": "krebs",
        "label": "Krebs on Security",
        "url": "https://feeds.feedburner.com/KrebsOnSecurity",
        "fallback_url": "https://krebsonsecurity.com/feed/",
    },
    {
        "id": "darkreading",
        "label": "Dark Reading",
        "url": "https://www.darkreading.com/rss.xml",
    },
    {
        "id": "schneier",
        "label": "Schneier on Security",
        "url": "https://www.schneier.com/feed/atom/",
    },
    {
        "id": "cisa-news",
        "label": "CISA Advisories",
        "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
    },
]
