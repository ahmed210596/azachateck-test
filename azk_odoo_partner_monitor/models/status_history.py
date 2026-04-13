from odoo import models, fields
class OdooPartnerStatusHistory(models.Model):
    _name = 'azk_odoo_partner_monitor.status.history'
             
    partner_id = fields.Many2one('azk_odoo_partner_monitor.partner', ondelete='cascade')
    previous_status = fields.Selection([('gold', 'Gold'), ('silver', 'Silver'), ('ready', 'Ready')])
    new_status = fields.Selection([('gold', 'Gold'), ('silver', 'Silver'), ('ready', 'Ready')])
    change_date = fields.Date(default=fields.Date.today)
    change_type = fields.Selection([
        ('promoted', 'Promoted'),
        ('demoted', 'Demoted'),
        ('unrated', 'Unrated'),
        
    ])