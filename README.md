# Static Site Host — Odoo 17 Module

Host any static website (HTML / CSS / JS) directly from Odoo without touching
a web server.  Upload a ZIP → click Deploy → your site is live.

---

## Installation

1. Copy the `static_site_host` folder into your Odoo **addons path**.
2. Restart the Odoo service.
3. In the backend, go to **Settings → Technical → Activate Developer Mode**.
4. Open **Apps**, click **Update Apps List**, search for **Static Site Host**,
   and install it.

---

## Usage

### 1 — Prepare your ZIP

```
my-site.zip
├── index.html          ← must be at the root
├── style.css
├── app.js
└── images/
    └── hero.webp
```

All **relative** asset paths inside your HTML/CSS work automatically.

> **GitHub / CLI ZIP quirk:** Some tools wrap everything in a subdirectory
> (e.g. `my-site-main/index.html`).  The module detects this automatically
> as long as there is only one top-level directory.

### 2 — Create a site record

Navigate to **Static Sites → All Sites → New**.

| Field      | Description |
|------------|-------------|
| **Name**   | Human-readable label |
| **Slug**   | URL segment — only lowercase letters, digits, hyphens.  Auto-filled from the name. |
| **ZIP File** | Your archive |

### 3 — Deploy

Click **Deploy**.  The module will:

1. Validate the ZIP (path traversal check, format check).
2. Extract files to `<odoo_data_dir>/static_sites/<slug>/`.
3. Mark the record as **Deployed**.

### 4 — Visit the site

```
https://your-odoo.example.com/sites/<slug>/
```

Click **Open Site ↗** in the form header for a shortcut.

### Updating the site

Upload a new ZIP and click **Re-deploy**.  The old files are replaced atomically.

---

## URL Structure

| URL | Resolves to |
|-----|-------------|
| `/sites/<slug>/` | `index.html` (or detected entry point) |
| `/sites/<slug>/about.html` | `about.html` |
| `/sites/<slug>/images/logo.png` | `images/logo.png` |
| `/sites/<slug>/docs/` | `docs/index.html` |

---

## Security

* **Path traversal protection** — ZIP entries with `../` or absolute paths are
  rejected at deploy time and at serve time.
* **Access control** — only Odoo *Administrators* can create / deploy / delete
  sites; regular users can only read the records.
* **Public serving** — the `/sites/` route is `auth='public'` so visitors do
  not need an Odoo login.

---

## File Storage

Extracted files are stored in:

```
<odoo_data_dir>/static_sites/<slug>/
```

`data_dir` is the value of `data_dir` in your `odoo.conf`
(default: `~/.local/share/Odoo`).

---

## Supported Asset Types

HTML, CSS, JavaScript, JSON, Web Manifest, WOFF/WOFF2/TTF/OTF/EOT fonts,
SVG, PNG, JPEG, WebP, AVIF, GIF, ICO, source maps — anything the browser can
load.  Unsupported MIME types fall back to `application/octet-stream`.

---

## Caching

| Type   | Cache-Control |
|--------|---------------|
| HTML   | `no-cache` (always fresh) |
| Other  | `public, max-age=3600` (1 hour) |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| 404 on `/sites/<slug>/` | Check state is **Deployed** and the slug matches exactly |
| Blank page | Ensure `index.html` is at the ZIP root (not inside a sub-folder) |
| CSS/JS not loading | Use relative paths (`./style.css`, not `/style.css`) |
| Deploy error | Read the **Error Details** field on the record |

---

## License

LGPL-3
