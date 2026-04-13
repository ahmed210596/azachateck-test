from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    azk_admin_user_id = fields.Many2one(
        'res.users', 
        string="Partner Scraper Admin", 
        config_parameter="azk_odoo_partner_monitor.admin_user_id",
        help="The user who will receive failure notifications in their chatter."
    )