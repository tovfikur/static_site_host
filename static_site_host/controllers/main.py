# -*- coding: utf-8 -*-
import logging
import mimetypes
import os

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# Extend mimetypes with common web asset types not always present on all OSes
_EXTRA_TYPES = {
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.otf': 'font/otf',
    '.eot': 'application/vnd.ms-fontobject',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.avif': 'image/avif',
    '.ico': 'image/x-icon',
    '.json': 'application/json',
    '.webmanifest': 'application/manifest+json',
    '.map': 'application/json',
}
for ext, mime in _EXTRA_TYPES.items():
    mimetypes.add_type(mime, ext)


class StaticSiteController(http.Controller):
    """Serve files from deployed static sites."""

    # ------------------------------------------------------------------ #
    #  Route: /sites/<slug>/                                              #
    # ------------------------------------------------------------------ #

    @http.route(
        '/sites/<string:slug>',
        auth='public',
        type='http',
        website=False,
        csrf=False,
        save_session=False,
    )
    def site_root_redirect(self, slug, **kwargs):
        """Redirect bare slug URL to the trailing-slash version."""
        return request.redirect(f'/sites/{slug}/', code=301)

    @http.route(
        [
            '/sites/<string:slug>/',
            '/sites/<string:slug>/<path:file_path>',
        ],
        auth='public',
        type='http',
        website=False,
        csrf=False,
        save_session=False,
    )
    def serve_site(self, slug, file_path='', **kwargs):
        """
        Serve a file from the deployed static site identified by *slug*.

        Resolution order
        ----------------
        1. If *file_path* is empty → serve the site's entry point (index.html).
        2. If *file_path* matches a file on disk → serve it directly.
        3. If *file_path* matches a directory that contains an index.html → serve that.
        4. Otherwise → 404.
        """
        site = request.env['static.site'].sudo().search(
            [('slug', '=', slug), ('state', '=', 'deployed'), ('active', '=', True)],
            limit=1,
        )
        if not site:
            return self._not_found(f'No deployed site found for slug: {slug}')

        site_path = site.deploy_path
        if not site_path or not os.path.isdir(site_path):
            return self._not_found(f'Site directory missing for: {slug}')

        # Determine the true base directory of the site's content
        if site.entry_point:
            base_path = os.path.dirname(os.path.join(site_path, site.entry_point))
        else:
            base_path = site_path

        # Resolve the requested path
        if not file_path:
            # Serve entry point
            if site.entry_point:
                abs_path = os.path.join(site_path, site.entry_point)
            else:
                abs_path = os.path.join(base_path, 'index.html')
        else:
            abs_path = os.path.join(base_path, file_path)

        # Security: prevent path traversal
        real_site = os.path.realpath(base_path)
        real_file = os.path.realpath(abs_path)
        if not real_file.startswith(real_site + os.sep) and real_file != real_site:
            return self._forbidden()

        # If it's a directory, look for index.html inside
        if os.path.isdir(real_file):
            candidate = os.path.join(real_file, 'index.html')
            if os.path.isfile(candidate):
                real_file = candidate
            else:
                return self._not_found(f'No index.html in directory: {file_path}')

        if not os.path.isfile(real_file):
            return self._not_found(f'File not found: {file_path}')

        return self._serve_file(real_file)

    # ------------------------------------------------------------------ #
    #  File serving                                                        #
    # ------------------------------------------------------------------ #

    def _serve_file(self, abs_path):
        """Read *abs_path* from disk and return an HTTP response."""
        mime, _ = mimetypes.guess_type(abs_path)
        if not mime:
            mime = 'application/octet-stream'

        try:
            with open(abs_path, 'rb') as fh:
                data = fh.read()
        except OSError as exc:
            _logger.warning('Cannot read file %s: %s', abs_path, exc)
            return self._not_found(str(exc))

        headers = [
            ('Content-Type', mime),
            ('Content-Length', str(len(data))),
            # Light caching for assets (1 hour), no-cache for HTML
            ('Cache-Control', 'no-cache' if mime == 'text/html' else 'public, max-age=3600'),
        ]
        return Response(data, status=200, headers=headers)

    # ------------------------------------------------------------------ #
    #  Error helpers                                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _not_found(detail=''):
        body = (
            '<!DOCTYPE html><html><head><title>404 Not Found</title>'
            '<style>body{font-family:sans-serif;text-align:center;padding:60px}'
            'h1{font-size:3rem;color:#c00}p{color:#555}</style></head>'
            f'<body><h1>404</h1><p>Page not found.</p>'
            f'<p style="font-size:.8rem;color:#aaa">{detail}</p></body></html>'
        )
        return Response(body, status=404, content_type='text/html')

    @staticmethod
    def _forbidden():
        body = (
            '<!DOCTYPE html><html><head><title>403 Forbidden</title>'
            '<style>body{font-family:sans-serif;text-align:center;padding:60px}'
            'h1{font-size:3rem;color:#c00}p{color:#555}</style></head>'
            '<body><h1>403</h1><p>Access denied.</p></body></html>'
        )
        return Response(body, status=403, content_type='text/html')
