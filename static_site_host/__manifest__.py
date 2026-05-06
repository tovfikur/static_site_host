# -*- coding: utf-8 -*-
{
    'name': 'Static Site Host',
    'version': '17.0.1.0.0',
    'category': 'Website',
    'summary': 'Upload a ZIP of HTML/CSS/JS assets and serve them as a live website.',
    'description': """
Static Site Host
================
Upload any ZIP archive containing HTML, CSS, JavaScript, images, or any static
web assets and the module will extract them and serve the site at a clean URL.

Usage
-----
1. Go to **Static Sites** menu in the backend.
2. Click **New**, give your site a name and an optional URL slug.
3. Upload your ZIP file and click **Deploy**.
4. Visit ``/sites/<slug>/`` to see your site live.

Tips
----
- Your ZIP should contain an ``index.html`` at the root.
- All relative asset paths (CSS, JS, images) work automatically.
- Re-upload a new ZIP at any time to update the site.
    """,
    'author': 'Custom',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/static_site_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'static_site_host/static/src/css/static_site.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
