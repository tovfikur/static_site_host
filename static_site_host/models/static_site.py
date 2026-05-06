# -*- coding: utf-8 -*-
import base64
import io
import logging
import os
import re
import shutil
import zipfile

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def _safe_slug(value):
    """Convert a string to a safe URL slug."""
    value = value.lower().strip()
    value = re.sub(r'[^\w\s-]', '', value)
    value = re.sub(r'[\s_-]+', '-', value)
    value = value.strip('-')
    return value or 'site'


class StaticSite(models.Model):
    _name = 'static.site'
    _description = 'Static Site'
    _order = 'name'

    name = fields.Char(
        string='Site Name',
        required=True,
    )
    slug = fields.Char(
        string='URL Slug',
        required=True,
        help='The URL path segment used to reach this site: /sites/<slug>/',
    )
    zip_file = fields.Binary(
        string='ZIP Archive',
        attachment=True,
        help='Upload a ZIP file containing your HTML/CSS/JS assets. '
             'The archive should have an index.html at its root.',
    )
    zip_filename = fields.Char(string='ZIP Filename')
    state = fields.Selection(
        selection=[
            ('draft', 'Not Deployed'),
            ('deployed', 'Deployed'),
            ('error', 'Error'),
        ],
        default='draft',
        string='Status',
        readonly=True,
    )
    deploy_path = fields.Char(
        string='Deploy Path',
        readonly=True,
        help='Absolute filesystem path where the site assets are extracted.',
    )
    entry_point = fields.Char(
        string='Entry Point',
        readonly=True,
        help='Relative path to the root HTML file inside the extracted archive.',
    )
    site_url = fields.Char(
        string='Site URL',
        compute='_compute_site_url',
    )
    file_count = fields.Integer(
        string='Files Deployed',
        readonly=True,
    )
    error_message = fields.Text(
        string='Error Details',
        readonly=True,
    )
    notes = fields.Text(string='Notes')
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------ #
    #  Constraints / Compute                                               #
    # ------------------------------------------------------------------ #

    @api.constrains('slug')
    def _check_slug(self):
        for rec in self:
            if not re.match(r'^[a-z0-9][a-z0-9\-]*$', rec.slug):
                raise ValidationError(_(
                    'The URL slug "%s" is invalid. Use only lowercase letters, '
                    'digits, and hyphens, and start with a letter or digit.', rec.slug
                ))
            duplicate = self.search([('slug', '=', rec.slug), ('id', '!=', rec.id)], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'The slug "%s" is already used by "%s". Choose a unique slug.',
                    rec.slug, duplicate.name,
                ))

    @api.depends('slug')
    def _compute_site_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for rec in self:
            rec.site_url = f'{base}/sites/{rec.slug}/' if rec.slug else ''

    # ------------------------------------------------------------------ #
    #  Onchange helpers                                                    #
    # ------------------------------------------------------------------ #

    @api.onchange('name')
    def _onchange_name(self):
        if self.name and not self.slug:
            self.slug = _safe_slug(self.name)

    # ------------------------------------------------------------------ #
    #  Deploy / Undeploy                                                   #
    # ------------------------------------------------------------------ #

    def _get_sites_root(self):
        """Return the base directory where all sites are stored."""
        data_dir = tools.config['data_dir']
        root = os.path.join(data_dir, 'static_sites')
        os.makedirs(root, exist_ok=True)
        return root

    def _get_site_path(self, slug):
        return os.path.join(self._get_sites_root(), slug)

    def action_deploy(self):
        """Extract the uploaded ZIP and mark the site as deployed."""
        self.ensure_one()
        if not self.zip_file:
            raise UserError(_('Please upload a ZIP archive before deploying.'))

        site_path = self._get_site_path(self.slug)

        # Wipe any previous deployment
        if os.path.exists(site_path):
            shutil.rmtree(site_path)
        os.makedirs(site_path)

        try:
            zip_bytes = base64.b64decode(self.zip_file)
            zip_buffer = io.BytesIO(zip_bytes)

            if not zipfile.is_zipfile(zip_buffer):
                raise UserError(_('The uploaded file is not a valid ZIP archive.'))

            zip_buffer.seek(0)
            file_count = 0

            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                # Security: reject absolute paths and path traversal
                for member in zf.infolist():
                    member_path = os.path.realpath(
                        os.path.join(site_path, member.filename)
                    )
                    if not member_path.startswith(os.path.realpath(site_path)):
                        raise UserError(_(
                            'ZIP archive contains unsafe path: %s', member.filename
                        ))

                zf.extractall(site_path)
                file_count = len([m for m in zf.infolist() if not m.is_dir()])

            # Detect entry point (index.html at root or one level deep)
            entry_point = self._find_entry_point(site_path)

            self.write({
                'state': 'deployed',
                'deploy_path': site_path,
                'entry_point': entry_point,
                'file_count': file_count,
                'error_message': False,
            })

            _logger.info(
                'Static site "%s" deployed to %s (%d files)',
                self.name, site_path, file_count
            )

        except UserError:
            raise
        except Exception as e:
            shutil.rmtree(site_path, ignore_errors=True)
            self.write({
                'state': 'error',
                'deploy_path': False,
                'entry_point': False,
                'file_count': 0,
                'error_message': str(e),
            })
            _logger.exception('Failed to deploy static site "%s"', self.name)
            raise UserError(_('Deployment failed: %s') % str(e))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Deployed!'),
                'message': _(
                    '%(count)d files deployed. Visit %(url)s',
                    count=file_count,
                    url=self.site_url,
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_undeploy(self):
        """Remove deployed files from disk."""
        self.ensure_one()
        if self.deploy_path and os.path.exists(self.deploy_path):
            shutil.rmtree(self.deploy_path, ignore_errors=True)
        self.write({
            'state': 'draft',
            'deploy_path': False,
            'entry_point': False,
            'file_count': 0,
            'error_message': False,
        })

    def action_open_site(self):
        """Open the deployed site in a new browser tab."""
        self.ensure_one()
        if self.state != 'deployed':
            raise UserError(_('Please deploy the site first.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.site_url,
            'target': 'new',
        }

    def action_redeploy(self):
        """Shortcut to re-deploy (undeploy + deploy)."""
        self.action_undeploy()
        return self.action_deploy()

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _find_entry_point(self, site_path):
        """
        Try to locate the best index.html entry point inside the extracted site.

        Priority:
        1. index.html at the root of site_path
        2. index.html inside a single top-level directory (common in GitHub ZIPs)
        3. Any *.html file at the root
        4. None (caller must handle)
        """
        # Direct index.html
        if os.path.isfile(os.path.join(site_path, 'index.html')):
            return 'index.html'

        # Single top-level directory (e.g. mysite-main/index.html)
        top_entries = os.listdir(site_path)
        if len(top_entries) == 1:
            candidate_dir = os.path.join(site_path, top_entries[0])
            if os.path.isdir(candidate_dir):
                candidate_index = os.path.join(candidate_dir, 'index.html')
                if os.path.isfile(candidate_index):
                    return os.path.join(top_entries[0], 'index.html')

        # Any HTML file at root
        for f in top_entries:
            if f.lower().endswith('.html') and os.path.isfile(os.path.join(site_path, f)):
                return f

        return None

    @api.model
    def _cleanup_orphaned_sites(self):
        """Cron job: remove site directories that no longer have a DB record."""
        root = self._get_sites_root()
        known_slugs = set(self.search([]).mapped('slug'))
        try:
            for entry in os.listdir(root):
                full_path = os.path.join(root, entry)
                if os.path.isdir(full_path) and entry not in known_slugs:
                    shutil.rmtree(full_path, ignore_errors=True)
                    _logger.info('Removed orphaned site directory: %s', full_path)
        except Exception:
            _logger.exception('Error during orphaned site cleanup')

    def unlink(self):
        for rec in self:
            if rec.deploy_path and os.path.exists(rec.deploy_path):
                shutil.rmtree(rec.deploy_path, ignore_errors=True)
        return super().unlink()
