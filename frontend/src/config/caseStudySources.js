/** Config-driven incident/news sources for the Case Studies tab. */

export const CASE_STUDY_SOURCES = [
  // RSS — proxied via allorigins.win to avoid CORS
  {
    id: 'hackernews',
    label: 'The Hacker News',
    type: 'rss',
    url: 'https://feeds.feedburner.com/TheHackersNews',
  },
  {
    id: 'krebs',
    label: 'Krebs on Security',
    type: 'rss',
    url: 'https://krebsonsecurity.com/feed/',
  },
  {
    id: 'darkreading',
    label: 'Dark Reading',
    type: 'rss',
    url: 'https://www.darkreading.com/rss.xml',
  },
  {
    id: 'schneier',
    label: 'Schneier on Security',
    type: 'rss',
    url: 'https://www.schneier.com/feed/atom/',
  },
  {
    id: 'cisa-news',
    label: 'CISA Advisories',
    type: 'rss',
    url: 'https://www.cisa.gov/cybersecurity-advisories/all.xml',
  },
  // ATLAS case studies — backend corpus (refreshed from MITRE ATLAS data)
  {
    id: 'atlas',
    label: 'MITRE ATLAS',
    type: 'atlas',
    url: 'https://atlas.mitre.org/api/data',
  },
]

export const RSS_PROXY_BASE = 'https://api.allorigins.win/raw?url='

export const ATLAS_YAML_FALLBACK =
  'https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml'
