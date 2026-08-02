#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tech Info Gap Collector
一键抓取多渠道科技信息（国内媒体 / 海外媒体 / X / 官方博客 / YouTube / Reddit / Bluesky），
按时间窗口过滤并输出 Markdown 报告 + JSON 原始数据。

用法：
  python collect.py                 # 抓取最近 30 小时并输出报告
  python collect.py --hours 12      # 自定义窗口
  python collect.py --no-fetch      # 复用缓存，不重新抓取
  python collect.py --out x.md      # 自定义输出文件

纯标准库实现（urllib + xml + json），无需安装依赖。
"""

import argparse
import html
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(ROOT, 'cache')
REPORT_DIR = r'C:\AI-Tech-Radar\reports\output'
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/126.0 Safari/537.36'),
    'Accept': 'application/rss+xml, application/xml, text/xml, application/json, */*',
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

CST = timezone(timedelta(hours=8))

# ---------------------------------------------------------------- sources

DOMESTIC_FEEDS = {
    'ithome': 'https://www.ithome.com/rss/',
    '36kr': 'https://36kr.com/feed',
    'geekpark': 'https://www.geekpark.net/rss',
    'ifanr': 'https://www.ifanr.com/feed',
    'sspai': 'https://sspai.com/feed',
    'huxiu': 'https://www.huxiu.com/rss/0.xml',
    'tmtpost': 'https://www.tmtpost.com/rss.xml',
    'cnbeta': 'https://www.cnbeta.com.tw/backend.php',
}

INTL_FEEDS = {
    'techcrunch': 'https://techcrunch.com/feed/',
    'arstechnica': 'https://feeds.arstechnica.com/arstechnica/index',
    'theregister': 'https://www.theregister.com/headlines.atom',
    'theverge': 'https://www.theverge.com/rss/index.xml',
    'engadget': 'https://www.engadget.com/rss.xml',
    'hn': 'https://hnrss.org/frontpage?points=100',
}

X_ACCOUNTS = {
    'elonmusk': 'elonmusk',
    'sama': 'sama',
    'OpenAI': 'OpenAI',
    'AnthropicAI': 'AnthropicAI',
    'ylecun': 'ylecun',
    'hwchase17': 'hwchase17',
    'dhh': 'dhh',
    'gdb': 'gdb',
    'JimFan': 'JimFan',
    'deepseek_ai': 'deepseek_ai',
    'GoogleDeepMind': 'GoogleDeepMind',
    'AIatMeta': 'AIatMeta',
    'nvidia': 'nvidia',
    'karpathy': 'karpathy',
    'TheTuringPost': 'TheTuringPost',
    'coinbase': 'coinbase',
}

NITTER_INSTANCES = ('https://nitter.net/', 'https://nitter.poast.org/', 'https://nitter.1d4.us/')

BLOG_FEEDS = {
    'openai': ['https://openai.com/news/rss.xml'],
    'google_ai': ['https://blog.google/technology/ai/rss/'],
    'googledeepmind': ['https://deepmind.google/blog/rss.xml'],
    'nvidia': ['https://blogs.nvidia.com/feed/'],
    'google_technology': ['https://blog.google/technology/rss/'],
}

YOUTUBE_FEEDS = {
    'yt_ltt': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCXuqSBlHAE6Xw-yeJA0Tunw',
    'yt_fireship': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCsBjURrPoezykLs9EqgamOA',
    'yt_mkbhd': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCBJycsmduvYEL83R_U4JriQ',
}

REDDIT_SUBS = ('technology', 'LocalLLaMA', 'hardware', 'singularity')

BLUESKY_QUERIES = ('openai', 'anthropic claude', 'deepseek', 'nvidia AI')

# ---------------------------------------------------------------- helpers


def fetch_raw(url, timeout=25, retries=2, delay=2):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(delay)
    raise last


def cache_path(name):
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', name)
    return os.path.join(CACHE_DIR, safe + '.bin')


def load_cache(name):
    p = cache_path(name)
    if os.path.exists(p):
        return open(p, 'rb').read()
    return None


def save_cache(name, data):
    with open(cache_path(name), 'wb') as f:
        f.write(data)


def strip_html(s):
    if not s:
        return ''
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


NS = {'a': 'http://www.w3.org/2005/Atom'}


def parse_xml(text):
    """Return (kind, items). kind in {'rss','atom','html','json','none'}."""
    s = text.lstrip()
    if s.startswith('{'):
        return 'json', None
    if s.startswith('<'):
        try:
            root = ET.fromstring(text)
        except Exception:
            return 'html', None
        items = []
        if root.tag == 'feed':
            for e in root.findall('a:entry', NS):
                title = (e.findtext('a:title', default='', namespaces=NS) or '').strip()
                link = ''
                for l in e.findall('a:link', NS):
                    href = l.get('href')
                    if href:
                        link = href
                        break
                pub = (e.findtext('a:published', default='', namespaces=NS)
                       or e.findtext('a:updated', default='', namespaces=NS) or '').strip()
                summary = strip_html(e.findtext('a:summary', default='', namespaces=NS) or '')
                items.append({'title': title, 'link': link, 'pub': pub, 'summary': summary})
            return 'atom', items
        for e in root.findall('.//item'):
            title = (e.findtext('title') or '').strip()
            link = (e.findtext('link') or '').strip()
            pub = (e.findtext('pubDate') or '').strip()
            summary = strip_html(e.findtext('description') or '')
            items.append({'title': title, 'link': link, 'pub': pub, 'summary': summary})
        return 'rss', items
    return 'none', None


def to_ts(pub):
    if not pub:
        return None
    txt = pub.strip()
    for fmt in ('%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S %z',
                '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%d %H:%M:%S'):
        try:
            dt = datetime.strptime(txt, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def stamp(ts, pub):
    if ts:
        return ts.astimezone(CST).strftime('%m-%d %H:%M')
    return (pub or '?')[:16]


# ---------------------------------------------------------------- fetch tasks


def task_feed(name, url):
    try:
        data = fetch_raw(url)
        save_cache(name, data)
        return {'name': name, 'ok': True, 'bytes': len(data), 'error': None}
    except Exception as e:  # noqa: BLE001
        return {'name': name, 'ok': False, 'bytes': 0, 'error': str(e)[:120]}


def task_x(handle):
    name = 'x_' + handle
    for inst in NITTER_INSTANCES:
        try:
            data = fetch_raw(inst + handle + '/rss', timeout=20)
            save_cache(name, data)
            return {'name': name, 'ok': True, 'bytes': len(data), 'error': None}
        except Exception as e:  # noqa: BLE001
            last = str(e)[:100]
    return {'name': name, 'ok': False, 'bytes': 0, 'error': last}


def task_blog(name, urls):
    for u in urls:
        try:
            data = fetch_raw(u, timeout=20)
            if b'<' in data[:2000]:
                save_cache(name, data)
                return {'name': name, 'ok': True, 'bytes': len(data), 'error': None}
        except Exception as e:  # noqa: BLE001
            last = str(e)[:100]
    return {'name': name, 'ok': False, 'bytes': 0, 'error': last}


def task_reddit(sub):
    name = 'reddit_' + sub
    url = 'https://old.reddit.com/r/%s/hot/.rss?limit=25' % sub
    try:
        data = fetch_raw(url, timeout=25)
        kind, _ = parse_xml(data.decode('utf-8', errors='replace'))
        if kind in ('rss', 'atom'):
            save_cache(name, data)
            return {'name': name, 'ok': True, 'bytes': len(data), 'error': None}
        return {'name': name, 'ok': False, 'bytes': len(data), 'error': 'not rss (blocked page?)'}
    except Exception as e:  # noqa: BLE001
        return {'name': name, 'ok': False, 'bytes': 0, 'error': str(e)[:100]}


def task_bsky(q):
    name = 'bsky_' + re.sub(r'\W+', '_', q.strip())[:30]
    url = ('https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q='
           + urllib.parse.quote(q) + '&limit=15')
    try:
        data = fetch_raw(url, timeout=20)
        save_cache(name, data)
        return {'name': name, 'ok': True, 'bytes': len(data), 'error': None}
    except Exception as e:  # noqa: BLE001
        return {'name': name, 'ok': False, 'bytes': 0, 'error': str(e)[:100]}


# ---------------------------------------------------------------- report


def load_items(name):
    data = load_cache(name)
    if data is None:
        return [], 'missing'
    text = data.decode('utf-8', errors='replace')
    kind, items = parse_xml(text)
    if kind == 'json':
        try:
            j = json.loads(text)
            items = []
            for item in j.get('feed', []):
                post = item.get('post', {})
                rec = post.get('record', {})
                author = post.get('author', {}).get('handle', '')
                items.append({'title': author + ': ' + rec.get('text', '')[:400],
                              'link': post.get('uri', ''), 'pub': rec.get('createdAt', ''),
                              'summary': ''})
            return items, 'json'
        except Exception:  # noqa: BLE001
            return [], 'json-error'
    if kind in ('rss', 'atom'):
        return items, kind
    return [], 'blocked/unknown'


def recent_items(name, cutoff):
    items, kind = load_items(name)
    out = []
    for it in items:
        ts = to_ts(it.get('pub', ''))
        if ts is None or ts >= cutoff:
            out.append((it, ts))
    return out, kind


def build_report(hours, statuses, group_order, cutoff):
    now = datetime.now(CST)
    lines = []
    lines.append('# 科技信息差采集报告')
    lines.append('')
    lines.append('- 生成时间：%s' % now.strftime('%Y-%m-%d %H:%M'))
    lines.append('- 时间窗口：最近 %d 小时（北京时间）' % hours)
    lines.append('- 生成方式：%s' % os.path.abspath(__file__))
    lines.append('')

    lines.append('## 抓取状态')
    lines.append('')
    lines.append('| 源 | 状态 | 大小/说明 |')
    lines.append('| --- | --- | --- |')
    for st in statuses:
        info = st['error'] if not st['ok'] else '%d B' % st['bytes']
        lines.append('| %s | %s | %s |' % (st['name'], 'OK' if st['ok'] else 'FAIL', info))
    lines.append('')

    for group, names in group_order:
        lines.append('## %s' % group)
        lines.append('')
        for name in names:
            items, kind = recent_items(name, cutoff)
            if not items:
                lines.append('### %s（无近期条目）' % name)
                lines.append('')
                continue
            lines.append('### %s（%d 条%s）' % (name, len(items), '' if kind == 'rss' else '/' + kind))
            lines.append('')
            for it, ts in items:
                title = (it.get('title') or '').replace('\n', ' ').strip()
                if not title:
                    continue
                lines.append('- [%s] %s' % (stamp(ts, it.get('pub', '')), title[:260]))
                if it.get('link'):
                    lines.append('  %s' % it['link'])
                if it.get('summary'):
                    lines.append('  %s' % it['summary'][:240])
            lines.append('')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description='Tech info gap collector')
    ap.add_argument('--hours', type=int, default=30, help='time window in hours (default 30)')
    ap.add_argument('--out', default=None, help='output markdown path (default <report-dir>/<date>.md)')
    ap.add_argument('--report-dir', default=REPORT_DIR,
                    help='output directory (default C:\\AI-Tech-Radar\\reports\\output)')
    ap.add_argument('--no-fetch', action='store_true', help='reuse cache only')
    args = ap.parse_args()

    cutoff = datetime.now(CST) - timedelta(hours=args.hours)

    out_dir = args.report_dir
    os.makedirs(out_dir, exist_ok=True)

    statuses = []
    if args.no_fetch:
        names = ([n for n in DOMESTIC_FEEDS] + [n for n in INTL_FEEDS]
                 + ['x_' + h for h in X_ACCOUNTS] + [n for n in BLOG_FEEDS]
                 + [n for n in YOUTUBE_FEEDS] + ['reddit_' + s for s in REDDIT_SUBS]
                 + ['bsky_' + re.sub(r'\W+', '_', q.strip())[:30] for q in BLUESKY_QUERIES])
        for n in names:
            data = load_cache(n)
            if data is not None:
                statuses.append({'name': n, 'ok': True, 'bytes': len(data), 'error': None})
            else:
                statuses.append({'name': n, 'ok': False, 'bytes': 0, 'error': 'no cache'})
    else:
        feeds = {**DOMESTIC_FEEDS, **INTL_FEEDS, **YOUTUBE_FEEDS}
        jobs = []
        with ThreadPoolExecutor(max_workers=10) as ex:
            jobs += [ex.submit(task_feed, n, u) for n, u in feeds.items()]
            for r in as_completed(jobs):
                statuses.append(r.result())
        for handle in X_ACCOUNTS:
            statuses.append(task_x(handle))
            time.sleep(1.5)
        for name, urls in BLOG_FEEDS.items():
            statuses.append(task_blog(name, urls))
        for sub in REDDIT_SUBS:
            statuses.append(task_reddit(sub))
        for q in BLUESKY_QUERIES:
            statuses.append(task_bsky(q))
    statuses.sort(key=lambda s: s['name'])

    group_order = [
        ('国内媒体', list(DOMESTIC_FEEDS)),
        ('海外媒体与社区', list(INTL_FEEDS)),
        ('X / 推特', ['x_' + h for h in X_ACCOUNTS]),
        ('官方博客', list(BLOG_FEEDS)),
        ('YouTube', list(YOUTUBE_FEEDS)),
        ('Reddit', ['reddit_' + s for s in REDDIT_SUBS]),
        ('Bluesky', ['bsky_' + re.sub(r'\W+', '_', q.strip())[:30] for q in BLUESKY_QUERIES]),
    ]

    report = build_report(args.hours, statuses, group_order, cutoff)
    out = args.out or os.path.join(out_dir, datetime.now(CST).strftime('%Y-%m-%d') + '.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(report)

    print('保存报告：%s' % out)
    print('抓取状态：%d 成功 / %d 失败' % (
        sum(1 for s in statuses if s['ok']), sum(1 for s in statuses if not s['ok'])))
    for s in statuses:
        flag = 'OK  ' if s['ok'] else 'FAIL'
        detail = s['error'] if not s['ok'] else '%d B' % s['bytes']
        print('  [%s] %-22s %s' % (flag, s['name'], detail))


if __name__ == '__main__':
    main()
