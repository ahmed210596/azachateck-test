from odoo import models, fields, api

class OdooPartner(models.Model):
    _name = 'azk_odoo_partner_monitor.partner'
    _description = 'Odoo Partner'

    name = fields.Char(required=True)
    partner_url = fields.Char()
    current_status = fields.Selection([
        ('gold', 'Gold'),
        ('silver', 'Silver'),
        ('ready', 'Ready')
    ], string="Status")
    country_id = fields.Many2one('azk_odoo_partner_monitor.country')
    first_seen_on = fields.Date(default=fields.Date.today)
    retention_rate = fields.Float()
    total_references_count = fields.Integer(compute="_compute_reference_ids", store=True)
    largest_project_size = fields.Integer()
    average_project_size = fields.Float()
    to_reprocess_references = fields.Boolean(default=True)
    is_top_5_country = fields.Boolean(compute="_compute_dummy", search="_search_top_5")
    is_bottom_5_country = fields.Boolean(compute="_compute_dummy", search="_search_bottom_5")
    
    status_history_ids = fields.One2many('azk_odoo_partner_monitor.status.history', 'partner_id')
    reference_ids = fields.One2many('azk_odoo_partner_monitor.reference', 'partner_id')
    year_first_seen = fields.Integer(
        string="Year First Seen",
        compute="_compute_year_first_seen",
        store=True,
    )
    project_size_bucket = fields.Selection([
        ('<5', '< 5'),
        ('5-10', '5 - 10'),
        ('11-25', '11 - 25'),
        ('25+', '25+'),
    ], string="Project Size Bucket", compute="_compute_project_size_bucket", store=True)


    def action_validate_partner_scrape(self, actual_count):
        for record in self:
            if actual_count != record.total_references_count:
                record.to_reprocess_references = True
            else:
                record.to_reprocess_references = False

    @api.depends('retention_rate', 'largest_project_size', 'average_project_size')
    def _compute_reprocess_flag(self):
        
        for record in self:
            
            record.to_reprocess_references = True
    @api.depends('reference_ids')
    def _compute_reference_ids(self):
        
        for record in self:
            record.total_references_count = len(record.reference_ids)






        # === ADD THESE FIELDS (required for the dashboard) ===
    

    @api.depends('first_seen_on')
    def _compute_year_first_seen(self):
        for rec in self:
            rec.year_first_seen = rec.first_seen_on.year if rec.first_seen_on else False

    @api.depends('average_project_size')
    def _compute_project_size_bucket(self):
        for rec in self:
            size = rec.average_project_size or 0.0
            if size < 5:
                rec.project_size_bucket = '<5'
            elif 5 <= size <= 10:
                rec.project_size_bucket = '5-10'
            elif 11 <= size <= 25:
                rec.project_size_bucket = '11-25'
            else:
                rec.project_size_bucket = '25+'        
                



      











    def _compute_dummy(self):
        for rec in self: rec.is_top_5_country = rec.is_bottom_5_country = False

    def _search_top_5(self, operator, value):
        self.env.cr.execute("""
            SELECT country_id FROM azk_odoo_partner_monitor_partner 
            WHERE country_id IS NOT NULL 
            GROUP BY country_id ORDER BY COUNT(*) DESC LIMIT 5
        """)
        ids = [row[0] for row in self.env.cr.fetchall()]
        return [('country_id', 'in', ids)]

    def _search_bottom_5(self, operator, value):
        self.env.cr.execute("""
            SELECT country_id FROM azk_odoo_partner_monitor_partner 
            WHERE country_id IS NOT NULL 
            GROUP BY country_id ORDER BY COUNT(*) ASC LIMIT 5
        """)
        ids = [row[0] for row in self.env.cr.fetchall()]
        return [('country_id', 'in', ids)]        

