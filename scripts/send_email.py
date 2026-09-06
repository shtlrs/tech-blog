"""
Fetches the latest post from the Hugo RSS feed, applies inline styles,
and sends it as a Kit broadcast to all subscribers.

Usage: python3 scripts/send_email.py <slug> <kit_api_key>
"""

import sys
import re
import json
import datetime
import urllib.request
import xml.etree.ElementTree as ET

CONTENT_NS = {'content': 'http://purl.org/rss/1.0/modules/content/'}

RSS_FILE = '/tmp/rss/index.xml'   # written by CI artifact download
RSS_URL  = 'https://shtlrs.com/index.xml'  # fallback for local testing
KIT_API_URL = 'https://api.kit.com/v4/broadcasts'

INLINE_STYLES = [
    (r'<p(?= |>)',          '<p style="margin:16px 0;font-size:16px;line-height:24px;font-family:sans-serif;color:#111;"'),
    (r'<h1(?= |>)',         '<h1 style="font-size:24px;font-weight:700;line-height:30px;margin:24px 0 12px;font-family:sans-serif;color:#111;"'),
    (r'<h2(?= |>)',         '<h2 style="font-size:20px;font-weight:700;line-height:26px;margin:20px 0 10px;font-family:sans-serif;color:#111;"'),
    (r'<h3(?= |>)',         '<h3 style="font-size:18px;font-weight:700;line-height:24px;margin:18px 0 8px;font-family:sans-serif;color:#111;"'),
    (r'<ul(?= |>)',         '<ul style="margin:16px 0;padding-left:1.5em;font-family:sans-serif;"'),
    (r'<ol(?= |>)',         '<ol style="margin:16px 0;padding-left:1.5em;font-family:sans-serif;"'),
    (r'<li(?= |>)',         '<li style="margin:8px 0;font-size:16px;line-height:24px;color:#111;"'),
    (r'<blockquote(?= |>)', '<blockquote style="margin:16px 0;padding:16px 20px;background:#f5f5f5;border-radius:6px;color:#555;font-family:sans-serif;"'),
    (r'<pre(?= |>)',        '<pre style="background:#f5f5f5;color:#333;padding:1em;border-radius:4px;font-size:14px;line-height:20px;overflow-x:auto;white-space:pre-wrap;"'),
    (r'<a href',            '<a style="color:#0069ff;text-decoration:underline;" href'),
    (r'<hr(?= |>|/)',       '<hr style="border:none;border-top:2px solid #eaeaea;max-width:300px;margin:32px auto;"'),
    (r'<img(?= |>)',        '<img style="max-width:100%;display:block;margin:16px 0;"'),
]


def find_post(slug: str):
    import os
    if os.path.exists(RSS_FILE):
        tree = ET.parse(RSS_FILE)
    else:
        with urllib.request.urlopen(RSS_URL) as r:
            tree = ET.fromstring(r.read())

    for item in tree.findall('.//item'):
        link = item.findtext('link') or ''
        if f'/{slug}/' in link:
            node = item.find('content:encoded', CONTENT_NS)
            return {
                'title': item.findtext('title') or '',
                'url': link,
                'html': node.text if node is not None else '',
            }
    return None


def apply_inline_styles(html):
    for pattern, replacement in INLINE_STYLES:
        html = re.sub(pattern, replacement, html)
    # Inline code style; undo inside pre blocks
    html = re.sub(r'<code(?= |>)', '<code style="background:#eee;color:#333;padding:2px 5px;border-radius:3px;font-size:14px;"', html)
    html = re.sub(r'(<pre[^>]*>)<code style="[^"]*">', r'\1<code>', html)
    return html


def build_email(post_url, title, body_html):
    tracked_url = post_url.rstrip('/') + '/?ref=email'
    return f"""
<div style="max-width:600px;margin:0 auto;padding:20px;background:#ffffff;font-family:sans-serif;">
  <p style="margin:0 0 24px;font-size:13px;color:#666;">
    <a href="{tracked_url}" style="color:#0069ff;text-decoration:underline;">Read it on shtlrs.com</a>
  </p>
  <h1 style="font-size:26px;font-weight:900;line-height:30px;margin:0 0 8px;color:#111;">
    <a href="{tracked_url}" style="color:inherit;text-decoration:none;">{title}</a>
  </h1>
  <p style="margin:0 0 32px;font-size:12px;color:#737373;text-transform:uppercase;letter-spacing:0.05em;">Amrou Bellalouna</p>
  <hr style="border:none;border-top:1px solid #eaeaea;margin:0 0 24px;">
  {body_html}
</div>
"""


def send_broadcast(title: str, post_content: str, kit_api_key: str):
    payload = json.dumps({
        'subject': title,
        'content': post_content,
        'public': False,
        'send_at': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00'),
    }).encode()
    req = urllib.request.Request(
        KIT_API_URL,
        data=payload,
        headers={'X-Kit-Api-Key': kit_api_key, 'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req) as r:
        print(f'HTTP {r.status}: {r.read().decode()}')


if __name__ == '__main__':
    preview = '--preview' in sys.argv
    args = [a for a in sys.argv[1:] if a != '--preview']

    if preview:
        slug = args[0]
        api_key = None
    else:
        slug, api_key = args[0], args[1]

    post = find_post(slug)
    if not post:
        print(f'Post not found in RSS feed: {slug}')
        sys.exit(1)

    html = apply_inline_styles(post['html'])
    content = build_email(post['url'], post['title'], html)

    if preview:
        out = '/tmp/email_preview.html'
        with open(out, 'w') as f:
            f.write(content)
        print(f'Preview saved to {out}')
        print('Open with: open /tmp/email_preview.html')
    else:
        send_broadcast(post['title'], content, api_key)
