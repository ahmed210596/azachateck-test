from odoo import models, fields, api


class OdooPartnerCountry(models.Model):
    _name = 'azk_odoo_partner_monitor.country'
    _description = 'Odoo Partner Country'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    
    country_code = fields.Integer(string="Odoo Country ID")

    # Stored count from the last scrape (updated after scraping, not computed)
    total_partner_count = fields.Integer(string="Last Scrape Count", default=0)

    to_reprocess_partners = fields.Boolean(default=True)

    partner_ids = fields.One2many('azk_odoo_partner_monitor.partner', 'country_id')

    def action_validate_country_scrape(self, actual_count):
        
        for record in self:
            if actual_count != record.total_partner_count:
                record.to_reprocess_partners = True
            else:
                record.to_reprocess_partners = False            