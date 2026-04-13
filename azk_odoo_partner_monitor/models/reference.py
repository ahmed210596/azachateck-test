from odoo import models, fields
class OdooPartnerReference(models.Model):
    _name = 'azk_odoo_partner_monitor.reference'
    
    partner_id = fields.Many2one('azk_odoo_partner_monitor.partner', ondelete='cascade')
    name = fields.Char(required=True)
    is_active = fields.Boolean(default=True)
    added_on = fields.Date(default=fields.Date.today)
    removed_on = fields.Date()