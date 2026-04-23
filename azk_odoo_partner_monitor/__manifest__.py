{
    'name': 'AZK Odoo Partner Monitor',
    'version': '14.0',
    'summary': 'Scraping and monitoring Odoo partners by country',
    'description': 'Tracks Odoo partners, references, and status history with automated scraping.',
    'author': 'Ahmed',
    'category': 'Tools',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        
        'views/views.xml',
        'views/dashbord.xml',
        
        'data/cron_data.xml',
        'data/country_data.xml'
    ],
    'installable': True,
    'application': True,
}
