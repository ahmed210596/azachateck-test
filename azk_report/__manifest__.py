{
    'name': 'Custom Trial Balance',
    'version': '14.0',
    'category': 'Accounting',
    'summary': 'Trial Balance with XLSX and PDF Export',
    'depends': ['account', 'report_xlsx', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/trial_balance_wizard_view.xml',
        'views/menu_action_wizard_view.xml',
        'report/trial_balance_report.xml',
        'report/trial_balance_report_template.xml',
        
    ],
    

   
    
           # remove demo.xml from here
    'demo': [
        #'data/demo_trial_balance.xml',
    ],

    'installable': True,
    'application': False,
}