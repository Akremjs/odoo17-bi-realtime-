# -*- coding: utf-8 -*-
"""
Données de démonstration Odoo pour alimenter les KPI (source Odoo / dashboards).
Idempotent : efface d'abord les enregistrements marqués (réf. partenaire / libellés BI-DEMO).
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEMO_PARTNER_REF = 'bi_demo_kpi_seed'
DEMO_VENDOR_REF = 'bi_demo_kpi_seed_vendor'
DEMO_PRODUCT_DEFAULT = 'DEMO-BI-KPI'


class BiDashboard(models.Model):
    _inherit = 'bi.dashboard'

    def _bi_demo_check_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise UserError(
                _('La génération de données démo est réservée aux administrateurs.')
            )

    def _bi_demo_income_account(self, product, company):
        """Compte de revenu pour lignes de facture (produit, catégorie ou plan comptable)."""
        tmpl = product.product_tmpl_id
        acc = tmpl.property_account_income_id
        if not acc and product.categ_id:
            acc = product.categ_id.property_account_income_categ_id
        if acc:
            return acc
        Account = self.env['account.account'].sudo()
        base_dom = [('account_type', '=', 'income'), ('deprecated', '=', False)]
        acc = Account.browse()
        if 'company_ids' in Account._fields:
            acc = Account.search(base_dom + [('company_ids', 'in', company.ids)], limit=1)
        if not acc and 'company_id' in Account._fields:
            acc = Account.search(base_dom + [('company_id', 'in', [False] + company.ids)], limit=1)
        if not acc:
            acc = Account.search(base_dom, limit=1)
        return acc

    def _bi_demo_clear_data(self):
        """Suppression interne (sans notification)."""
        SaleOrder = self.env['sale.order'].sudo()
        PurchaseOrder = self.env['purchase.order'].sudo()
        AccountMove = self.env['account.move'].sudo()
        CrmLead = self.env['crm.lead'].sudo()
        StockPicking = self.env['stock.picking'].sudo()
        CrmLead.search([('name', 'ilike', 'BI-DEMO%')]).unlink()
        if 'hr.applicant' in self.env:
            self.env['hr.applicant'].sudo().search([('name', 'ilike', 'BI-DEMO%')]).unlink()

        partner_c = self.env['res.partner'].sudo().search([('ref', '=', DEMO_PARTNER_REF)], limit=1)
        partner_v = self.env['res.partner'].sudo().search([('ref', '=', DEMO_VENDOR_REF)], limit=1)

        if partner_c:
            moves = AccountMove.search([
                ('partner_id', '=', partner_c.id),
                ('ref', 'ilike', 'BI-DEMO%'),
            ])
            for m in moves:
                if m.state == 'posted':
                    try:
                        m.button_draft()
                    except Exception:
                        try:
                            m.button_cancel()
                        except Exception:
                            _logger.warning('Facture démo %s non annulable', m.id)
                            continue
                if m.state == 'draft':
                    m.unlink()
                elif m.state == 'cancel':
                    m.unlink()

            for so in SaleOrder.search([('partner_id', '=', partner_c.id)]):
                if so.state in ('sale', 'done'):
                    so.action_cancel()
                elif so.state in ('draft', 'sent'):
                    so.action_cancel()
                try:
                    so.unlink()
                except Exception:
                    _logger.warning('Commande %s non supprimée', so.id)

            pickings = StockPicking.search([
                ('partner_id', '=', partner_c.id),
                ('origin', 'ilike', 'BI-DEMO%'),
            ])
            for pk in pickings:
                if pk.state not in ('done', 'cancel'):
                    try:
                        pk.action_cancel()
                    except Exception:
                        pass
                try:
                    if pk.state != 'done':
                        pk.unlink()
                except Exception:
                    _logger.warning('Transfert %s non supprimé', pk.id)

        if partner_v:
            for po in PurchaseOrder.search([('partner_id', '=', partner_v.id)]):
                if po.state in ('purchase', 'done'):
                    po.button_cancel()
                try:
                    po.unlink()
                except Exception:
                    _logger.warning('Achat %s non supprimé', po.id)

        for p in (partner_c, partner_v):
            if p:
                try:
                    p.unlink()
                except Exception as e:
                    _logger.warning('Partenaire démo non supprimé: %s', e)

    def _bi_demo_partner_customer(self):
        Partner = self.env['res.partner'].sudo()
        p = Partner.search([('ref', '=', DEMO_PARTNER_REF)], limit=1)
        if p:
            return p
        return Partner.create({
            'name': _('Client démo KPI BI'),
            'ref': DEMO_PARTNER_REF,
            'is_company': True,
            'customer_rank': 1,
        })

    def _bi_demo_partner_vendor(self):
        Partner = self.env['res.partner'].sudo()
        p = Partner.search([('ref', '=', DEMO_VENDOR_REF)], limit=1)
        if p:
            return p
        return Partner.create({
            'name': _('Fournisseur démo KPI BI'),
            'ref': DEMO_VENDOR_REF,
            'is_company': True,
            'supplier_rank': 1,
        })

    def _bi_demo_product(self):
        Product = self.env['product.product'].sudo()
        pr = Product.search([('default_code', '=', DEMO_PRODUCT_DEFAULT)], limit=1)
        if pr:
            return pr
        return Product.create({
            'name': _('Article démo KPI BI'),
            'default_code': DEMO_PRODUCT_DEFAULT,
            'type': 'consu',
            'sale_ok': True,
            'purchase_ok': True,
            'list_price': 100.0,
            'standard_price': 40.0,
        })

    def _bi_demo_outgoing_locations(self, picking_type, warehouse, company):
        """Emplacements source / destination pour un picking sortant (fallback si le type n’a pas les défauts)."""
        Location = self.env['stock.location'].sudo()
        src = picking_type.default_location_src_id
        if not src and warehouse:
            src = warehouse.lot_stock_id
        if not src:
            src = Location.search([
                ('usage', '=', 'internal'),
                ('company_id', 'in', [False, company.id]),
            ], limit=1)
        dest = picking_type.default_location_dest_id
        if not dest:
            dest = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not dest:
            dest = Location.search([('usage', '=', 'customer')], limit=1)
        if not dest:
            dest = Location.search([
                ('usage', '=', 'transit'),
                '|', ('company_id', '=', False), ('company_id', '=', company.id),
            ], limit=1)
        return src, dest

    @api.model
    def action_remove_odoo_demo_for_kpis(self):
        """Supprime les données de démo créées pour les KPI."""
        self._bi_demo_check_admin()
        self._bi_demo_clear_data()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Données démo supprimées'),
                'message': _('Les enregistrements marqués démo KPI ont été retirés.'),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def action_seed_odoo_demo_for_kpis(self):
        """
        Crée commandes, opportunités, factures, achats, transfert et candidature
        sur la période courante pour que les KPI Odoo affichent des valeurs lisibles.
        """
        self._bi_demo_check_admin()
        self._bi_demo_clear_data()

        partner_c = self._bi_demo_partner_customer()
        partner_v = self._bi_demo_partner_vendor()
        product = self._bi_demo_product()
        company = self.env.company
        today = fields.Date.context_today(self)
        now_dt = fields.Datetime.now()

        created = []

        # ── Ventes ─────────────────────────────────────────────
        try:
            SaleOrder = self.env['sale.order'].sudo()
            lines_specs = [
                (2, 120.0),
                (1, 450.0),
                (4, 89.5),
            ]
            for i, (qty, price) in enumerate(lines_specs):
                so = SaleOrder.create({
                    'partner_id': partner_c.id,
                    'date_order': now_dt - timedelta(days=i),
                    'client_order_ref': 'BI-DEMO-SO-%d' % (i + 1),
                    'order_line': [(0, 0, {
                        'product_id': product.id,
                        'product_uom_qty': qty,
                        'price_unit': price,
                    })],
                })
                so.action_confirm()
                created.append(_('Commande %s') % so.name)
        except Exception as e:
            _logger.exception('Seed ventes: %s', e)
            created.append(_('Ventes: erreur — %s') % e)

        # ── CRM ────────────────────────────────────────────────
        try:
            Lead = self.env['crm.lead'].sudo()
            Lead.create({
                'name': 'BI-DEMO — Opportunité pipeline',
                'type': 'opportunity',
                'partner_id': partner_c.id,
                'expected_revenue': 12500.0,
                'probability': 35.0,
                'active': True,
            })
            Lead.create({
                'name': 'BI-DEMO — Opportunité haute',
                'type': 'opportunity',
                'partner_id': partner_c.id,
                'expected_revenue': 8200.0,
                'probability': 55.0,
                'active': True,
            })
            created.append(_('2 opportunités CRM'))
        except Exception as e:
            _logger.exception('Seed CRM: %s', e)
            created.append(_('CRM: erreur — %s') % e)

        # ── Factures client ───────────────────────────────────
        try:
            journal = self.env['account.journal'].sudo().search([
                ('type', '=', 'sale'),
                ('company_id', '=', company.id),
            ], limit=1)
            income_acc = self._bi_demo_income_account(product, company)
            if journal and income_acc:
                def _inv_line(qty, price):
                    return (0, 0, {
                        'product_id': product.id,
                        'quantity': qty,
                        'price_unit': price,
                        'account_id': income_acc.id,
                    })
                move = self.env['account.move'].sudo().create({
                    'move_type': 'out_invoice',
                    'partner_id': partner_c.id,
                    'invoice_date': today,
                    'journal_id': journal.id,
                    'ref': 'BI-DEMO-INV-1',
                    'invoice_line_ids': [_inv_line(2, 330.0)],
                })
                move.action_post()
                created.append(_('Facture %s') % move.name)
                move2 = self.env['account.move'].sudo().create({
                    'move_type': 'out_invoice',
                    'partner_id': partner_c.id,
                    'invoice_date': today,
                    'journal_id': journal.id,
                    'ref': 'BI-DEMO-INV-UNPAID',
                    'invoice_line_ids': [_inv_line(1, 500.0)],
                })
                move2.action_post()
                created.append(_('Facture impayée %s') % move2.name)
            else:
                created.append(_('Factures: journal vente ou compte revenus introuvable'))
        except Exception as e:
            _logger.exception('Seed factures: %s', e)
            created.append(_('Factures: erreur — %s') % e)

        # ── Achats ─────────────────────────────────────────────
        try:
            po = self.env['purchase.order'].sudo().create({
                'partner_id': partner_v.id,
                'date_order': now_dt,
                'origin': 'BI-DEMO-PO',
                'order_line': [(0, 0, {
                    'product_id': product.id,
                    'product_qty': 25,
                    'price_unit': 22.0,
                })],
            })
            po.button_confirm()
            created.append(_('Bon de commande %s') % po.name)
        except Exception as e:
            _logger.exception('Seed achats: %s', e)
            created.append(_('Achats: erreur — %s') % e)

        # ── Transfert (savepoint : évite d’abandonner toute la transaction si stock échoue)
        try:
            with self.env.cr.savepoint():
                wh = self.env['stock.warehouse'].sudo().search([
                    ('company_id', '=', company.id),
                ], limit=1)
                if not wh:
                    created.append(_('Stock: aucun entrepôt pour cette société'))
                else:
                    picking_type = self.env['stock.picking.type'].sudo().search([
                        ('warehouse_id', '=', wh.id),
                        ('code', '=', 'outgoing'),
                    ], limit=1)
                    if not picking_type:
                        created.append(_('Stock: type de picking « sortie » introuvable'))
                    else:
                        src, dest = self._bi_demo_outgoing_locations(picking_type, wh, company)
                        if not src or not dest:
                            created.append(_(
                                'Stock: emplacements source/destination introuvables '
                                '(configurez le type de picking sortie de l’entrepôt).'
                            ))
                        else:
                            picking = self.env['stock.picking'].sudo().create({
                                'partner_id': partner_c.id,
                                'picking_type_id': picking_type.id,
                                'location_id': src.id,
                                'location_dest_id': dest.id,
                                'origin': 'BI-DEMO-PICK',
                                'move_ids': [(0, 0, {
                                    'name': product.name,
                                    'product_id': product.id,
                                    'product_uom_qty': 1,
                                    'product_uom': product.uom_id.id,
                                    'location_id': src.id,
                                    'location_dest_id': dest.id,
                                    'picking_type_id': picking_type.id,
                                })],
                            })
                            picking.action_confirm()
                            try:
                                picking.action_assign()
                            except Exception:
                                pass
                            created.append(_('Transfert %s') % picking.name)
        except Exception as e:
            _logger.exception('Seed stock: %s', e)
            created.append(_('Stock: erreur — %s') % e)

        # ── RH (si hr_recruitment installé) ────────────────────
        if 'hr.applicant' in self.env:
            try:
                job = self.env['hr.job'].sudo().search([], limit=1)
                self.env['hr.applicant'].sudo().create({
                    'name': 'BI-DEMO — Candidat test',
                    'partner_name': 'Candidat démo',
                    'active': True,
                    **({'job_id': job.id} if job else {}),
                })
                created.append(_('1 candidature'))
            except Exception as e:
                _logger.exception('Seed RH: %s', e)
                created.append(_('RH: erreur — %s') % e)

        try:
            Kpi = self.env['bi.kpi'].sudo()
            for dash in self.env['bi.dashboard'].sudo().search([]):
                Kpi.batch_refresh_by_dashboard(dash.id)
            created.append(_('KPI recalculés sur tous les dashboards.'))
        except Exception as e:
            _logger.warning('Refresh KPI après seed: %s', e)
            created.append(_('Pensez à rafraîchir les KPI depuis le dashboard BI.'))

        msg = '\n'.join(created) if created else _('Aucun enregistrement créé.')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Données démo KPI créées'),
                'message': msg,
                'type': 'success',
                'sticky': True,
            },
        }
