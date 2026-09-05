# CLAUDE.md — shtlrs.com tech blog

This file gives Claude context about this project. Update it when important decisions, patterns, or gotchas are discovered.

---

## Project overview

Hugo static site deployed to GitHub Pages. Theme: HugoTeX. Source at `/Users/shtlrs/dev/tech-blog`. Live at `https://shtlrs.com`.

Posts live in `content/posts/`. Each post is either a single `index.md` inside a named folder (bundle, supports local images) or a standalone `.md` file.

Frontmatter is TOML (`+++` delimiters), not YAML.

Config: `config/_default/config.toml`. Key params:
- `kitFormUrl` — Kit subscribe form URL; controls whether subscribe UI renders at all
- `customCSS = ["css/styles.css"]` — loads `assets/css/styles.css`
- `[markup.goldmark.renderer] unsafe = true` — allows raw HTML in markdown

---

## Layout customizations

All overrides live in `layouts/`, taking precedence over the HugoTeX theme.

### `layouts/_default/baseof.html`
Base template for every page. Includes sticky subscribe bar before footer:
```
{{- partial "sticky-subscribe.html" . -}}
{{- partial "footer.html" . -}}
```

### `layouts/_default/single.html`
Single post template. Adds:
- Tags displayed as pill links at the bottom of the post
- Inline subscribe form (`{{ partial "subscribe.html" . }}`) after the article

### `layouts/_default/rss.xml`
Overrides Hugo's default RSS template to add `<content:encoded>{{ .Content | html }}</content:encoded>` — full rendered post HTML per item. Also adds `xmlns:content="http://purl.org/rss/1.0/modules/content/"` namespace. Hugo's built-in RSS only outputs summaries; this override is required for the email pipeline.

### `layouts/partials/nav.html`
Custom nav bar with:
- Home link + menu items from `config.toml` (`[[menus.main]]`)
- Subscribe link (red, `#c33`) — only shown if `kitFormUrl` is set; scrolls to inline form on post pages, shows sticky bar on other pages
- Dark/light theme toggle button (absolute-positioned right)

### `layouts/partials/subscribe.html`
Inline subscribe form rendered at the bottom of every post. Email input + submit button POSTing to Kit form URL.

### `layouts/partials/sticky-subscribe.html`
Fixed bottom bar on every page. Dismissed per page load only (no localStorage — refresh = bar reappears). Contains `dismissSticky()` and `showSubscribe(e)` JS functions used by the nav Subscribe link.

### `layouts/shortcodes/code.html`
Collapsible code block shortcode. Usage in markdown:
```
{{< code lang "optional highlight options" >}}
your code here
{{< /code >}}
```
Renders as a `<details>/<summary>` block with syntax highlighting via Hugo's `highlight` function.

### `layouts/404.html`
Custom 404 page.

---

## Assets

### `assets/css/styles.css`
Custom CSS loaded via `customCSS` config param. Covers:
- Navbar layout (flexbox, separator pipes, hover states)
- Collapsible code block styling (`.collapsible-code`)
- Base font sizes (`body: 22px`, `p: 24px`)
- Theme toggle button positioning and hover animation

### `static/js/theme-toggle.js`
Dark/light theme toggle. Reads/writes `theme-preference` key in localStorage. Applies `latex-dark` class to `<body>` for dark mode. Defaults to system preference (`prefers-color-scheme`) if no saved preference.

---

## Subscribe feature

### Entry points

Three ways subscribers reach the form:
- **Inline form** — bottom of every post (`layouts/partials/subscribe.html`)
- **Sticky bar** — fixed bottom of every page, dismissed per page load (`layouts/partials/sticky-subscribe.html`)
- **Nav link** — red "Subscribe" in nav; scrolls to inline form on posts, shows sticky bar elsewhere

All conditional on `kitFormUrl` in config. Kit form endpoint: `https://app.kit.com/forms/9885985/subscriptions`

Confirmation email: Kit dashboard → Forms → your form → Settings → Incentive email.

### Auto-email on new post (GitHub Actions)

Files: `.github/workflows/hugo.yaml`, `scripts/send_email.py`

Three jobs: `build` → `deploy` → `notify`

**`build` job:**
- Runs `hugo --minify --baseURL ...` → produces `public/`
- Uploads `public/` as GitHub Pages artifact
- Also uploads `public/index.xml` as a separate reusable artifact (`rss-feed`)

**`notify` job:**
- Downloads `rss-feed` artifact to `/tmp/rss/index.xml`
- Detects newly added `.md` files via `git diff --diff-filter=A HEAD~1 HEAD -- 'content/posts/'`
- Skips if no new post or if `draft = true` in frontmatter
- Derives slug from file path (see slug detection below)
- Calls `python3 scripts/send_email.py <slug> <KIT_API_SECRET>`

**`scripts/send_email.py`:**
- Reads RSS from `/tmp/rss/index.xml` if present (CI), else fetches `https://shtlrs.com/index.xml` (local fallback)
- Finds matching item by slug in `<link>` field
- Reads title, URL, and full HTML from RSS item
- Applies inline styles (email clients strip external CSS)
- POSTs to Kit v4 API with `send_at: now`

**Slug detection (bash):**
```bash
[[ "$NEW_POST" == */index.md ]] \
  && SLUG=$(basename "$(dirname "$NEW_POST")") \
  || SLUG=$(basename "$NEW_POST" .md)
```
Bundle post `content/posts/my-post/index.md` → `my-post` (dirname).
Standalone `content/posts/my-post.md` → `my-post` (basename strip ext).

### Kit API details

- Base URL: `https://api.kit.com/v4/`
- Auth: `X-Kit-Api-Key: <secret>` header (NOT `Authorization: Bearer`)
- Send broadcast: `POST /v4/broadcasts` with `send_at` = current UTC ISO timestamp
- `send_at` triggers email delivery. `published_at` only publishes to web archive.
- Email body in `content` field — must be self-contained HTML with inline styles

### GitHub secrets required

- `KIT_API_SECRET` — only secret needed

### Sending domain

Kit → Settings → Email → `blog@shtlrs.com`. DKIM DNS records must be set on `shtlrs.com`. Without DKIM, emails land in spam.

---

## Known gotchas

**Hugo default RSS has no full content** — only summaries in `<description>`. `layouts/_default/rss.xml` overrides this.

**RSS `<content:encoded>` is namespaced** — ElementTree needs `{'content': 'http://purl.org/rss/1.0/modules/content/'}` or `find('content:encoded')` returns None.

**Python inline in bash: never use `-c "..."`** — regex `?` (e.g. `https?://`) gets glob-expanded by bash/zsh. Always write Python to a file.

**Inline `<code>` needs explicit style** — email clients strip CSS classes. Applied in `scripts/send_email.py`. Undone inside `<pre>` blocks (pre has its own dark background).

**`[markup.goldmark.renderer] unsafe = true`** — required to allow raw HTML in post markdown. Without it Hugo strips HTML tags.

---

## Testing

**Locally — subscribe form:**
```bash
hugo server
# visit a post → scroll to bottom → submit email
# verify in Kit dashboard → Subscribers
```

**Locally — email sending:**
```bash
export KIT_API_SECRET=your_secret_here
python3 scripts/send_email.py "diet-tracking-application" "$KIT_API_SECRET"
# reads live https://shtlrs.com/index.xml since /tmp/rss/index.xml won't exist
```

**CI end-to-end:**
Push a new non-draft post to `main`. Check GitHub Actions → `notify` job logs. Email arrives ~1 min after job completes.

**Verify new post detection:**
```bash
git diff --name-only --diff-filter=A HEAD~1 HEAD -- 'content/posts/'
```
Empty output = CI won't send.

---

## Self-update instruction

Update this file when:
- Layout files are added or modified
- Kit API usage changes
- New gotchas found in email rendering or CI pipeline
- Secrets, sending domain, or Kit form URL change
- New Hugo config params added
