"""Refresh the profile images using only information visible without signing in."""
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import json
import re
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
LOGIN = 'vishesh381'

def fetch(url):
    request = Request(url, headers={'User-Agent': 'vishesh381-profile-activity'})
    with urlopen(request, timeout=45) as response:
        return response.read().decode('utf-8')

class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}
        self.tooltips = {}
        self.current_tip = None
        self.tip_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'td' and attrs.get('data-date'):
            self.days[attrs['id']] = {'date': attrs['data-date'], 'level': int(attrs['data-level'])}
        if tag == 'tool-tip' and attrs.get('for', '').startswith('contribution-day-component'):
            self.current_tip = attrs['for']
            self.tip_text = []

    def handle_data(self, data):
        if self.current_tip is not None:
            self.tip_text.append(data)

    def handle_endtag(self, tag):
        if tag == 'tool-tip' and self.current_tip:
            text = ''.join(self.tip_text).strip()
            count = re.match(r'([\d,]+) contributions?', text)
            if count:
                self.tooltips[self.current_tip] = int(count[1].replace(',', ''))
            elif text.startswith('No contributions'):
                self.tooltips[self.current_tip] = 0
            self.current_tip = None

def get_data():
    document = fetch(f'https://github.com/users/{LOGIN}/contributions')
    total = re.search(r'([\d,]+)\s+contributions\s+in the last year', document)
    if not total:
        raise ValueError('Public calendar total is missing; keep the previous images.')
    calendar = Calendar()
    calendar.feed(document)
    if not 350 <= len(calendar.days) <= 380:
        raise ValueError('Public calendar has an unexpected number of days.')
    if calendar.days.keys() - calendar.tooltips.keys():
        raise ValueError('A contribution day has no matching count.')
    days = sorted([dict(day, count=calendar.tooltips[key]) for key, day in calendar.days.items()], key=lambda x: x['date'])
    public_total = int(total[1].replace(',', ''))
    # The rendered grid can include days before the rolling year starts.
    if abs(sum(day['count'] for day in days) - public_total) > sum(day['count'] for day in days[:7]):
        raise ValueError('The public calendar counts do not match its total.')
    account = json.loads(fetch(f'https://api.github.com/users/{LOGIN}'))
    if account['login'].lower() != LOGIN:
        raise ValueError('Unexpected GitHub account.')
    return {'source': f'https://github.com/users/{LOGIN}/contributions', 'updated': datetime.now(timezone.utc).date().isoformat(), 'total': public_total, 'publicRepositories': account['public_repos'], 'days': days}

def render(data, theme, mobile):
    w, h = (560, 541) if mobile else (1120, 372)
    fg, muted, bg, line = ('#edf3ff', '#adbedc', '#101c30', '#2c405f') if theme == 'dark' else ('#1b2b4c', '#536585', '#f3f7ff', '#d2dcec')
    colors = [('#1b2a43' if theme == 'dark' else '#e2e9f4'), '#32667f', '#3fa5bb', '#57cfc4', '#a8f0bd']
    active = sum(day['count'] > 0 for day in data['days'])
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{data["total"]} public contributions and {data["publicRepositories"]} public repositories. Updated {data["updated"]}."><title>Public GitHub contribution activity</title><style>text{{font-family:Segoe UI,Arial,sans-serif}}.scan{{animation:scan 13s linear infinite}}.dot{{animation:pulse 2s ease-in-out infinite}}@keyframes scan{{from{{transform:translateX(0)}}to{{transform:translateX({476 if mobile else 1040}px)}}}}@keyframes pulse{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}@media(prefers-reduced-motion:reduce){{*{{animation:none!important}}}}</style><defs><linearGradient id="stripe"><stop stop-color="#45dddc"/><stop offset="1" stop-color="#ad91ff"/></linearGradient></defs>', f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="20" fill="{bg}" stroke="{line}"/><path d="M24 2H{w-24}" stroke="url(#stripe)" stroke-width="3"/>']
    parts += [f'<circle class="dot" cx="30" cy="33" r="5" fill="#50d9b5"/><text x="44" y="38" font-size="14" letter-spacing="1" fill="{muted}">GITHUB / PUBLIC ACTIVITY</text>']
    for x, value, label in [(28, data['total'], 'contributions'), (210 if mobile else 340, data['publicRepositories'], 'public repositories'), (389 if mobile else 685, active, 'active days')]:
        if mobile and label == 'public repositories':
            label = 'repositories'
        parts += [f'<text x="{x}" y="99" font-size="{43 if mobile else 47}" font-weight="750" fill="{fg}">{value:,}</text><text x="{x}" y="125" font-size="{20 if mobile else 17}" fill="{muted}">{label}</text>']
    days = data['days']
    start = date.fromisoformat(days[0]['date'])
    weeks = {}
    for day in days:
        elapsed = (date.fromisoformat(day['date']) - start).days
        weeks.setdefault(elapsed//7, []).append((elapsed%7, day))
    month = None
    for week, entries in weeks.items():
        row, col = divmod(week, 27) if mobile else (0, week)
        cell = 17 if mobile else 18
        x = 30 + col*cell if mobile else 43 + col*19
        top = 183 + row*159 if mobile else 190
        date_label = date.fromisoformat(entries[0][1]['date']).strftime('%b')
        if month != date_label:
            parts.append(f'<text x="{x}" y="{top-12}" font-size="{13 if mobile else 14}" fill="{muted}">{date_label}</text>')
            month = date_label
        for weekday, day in entries:
            y = top+weekday*cell
            parts.append(f'<rect x="{x}" y="{y}" width="{cell-4}" height="{cell-4}" rx="3" fill="{colors[day["level"]]}"><title>{day["date"]}: {day["count"]} public contributions</title></rect>')
    # A moving outline adds motion without changing any contribution value.
    parts.append(f'<g transform="translate(30 {178 if mobile else 185})"><rect class="scan" width="16" height="{121 if mobile else 132}" rx="5" fill="none" stroke="#62d8d6" stroke-opacity=".32"/></g>')
    y = 482 if mobile else 338
    parts += [f'<text x="28" y="{y}" font-size="{13 if mobile else 14}" fill="{muted}">{days[0]["date"]} to {days[-1]["date"]}</text><text x="28" y="{y+26 if mobile else y}" text-anchor="start" font-size="{13 if mobile else 14}" fill="{muted}">{"Updated " if mobile else ""}{data["updated"] if mobile else ""}</text>']
    if not mobile:
        parts += [f'<text x="{w-30}" y="{y}" text-anchor="end" font-size="14" fill="{muted}">Updated {data["updated"]} / refreshed daily</text>']
    parts.append('</svg>')
    content = ''.join(parts)
    ElementTree.fromstring(content)
    return content

def main():
    data = get_data()
    outputs = {}
    for theme in ['dark', 'light']:
        for mobile in [False, True]:
            filename = f'activity-{"mobile-" if mobile else ""}{theme}.svg'
            outputs[filename] = render(data, theme, mobile)
    # Fetch and validate everything before changing an existing generated file.
    for filename, content in outputs.items():
        (ROOT/'assets'/filename).write_text(content, encoding='utf-8')
    (ROOT/'assets'/'activity.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'updated':data['updated'], 'publicContributions':data['total'], 'publicRepositories':data['publicRepositories'], 'calendarDays':len(data['days'])}))

if __name__ == '__main__':
    main()
