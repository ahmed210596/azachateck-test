from odoo import models, fields, api
from odoo.osv import expression

class TrialBalanceWizard(models.TransientModel):
    _name = 'trial.balance.wizard'
    _description = 'Trial Balance Wizard'

    # -------------------------------------------------------------------------
    # Options
    # -------------------------------------------------------------------------
    include_unposted = fields.Boolean(string="Include Unposted Entries")
    hierarchy_subtotals = fields.Boolean(string="Hierarchy and Subtotals")
    hierarchy_only_parents = fields.Boolean(string="Hierarchy Only Parents")
    account_level_up_to = fields.Selection([
        ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')
    ], string="Account Level Up To", default='1')

    # -------------------------------------------------------------------------
    # Filters
    # -------------------------------------------------------------------------
    account_ids_text = fields.Char(
        string="Accounts",
        help="Specify account prefixes separated by commas e.g. 101, 201. Leave empty for all accounts."
    )
    journal_id = fields.Many2one(
        'account.journal',
        string="Journal",
        help="Filter by a specific journal, or leave empty for all."
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string="Analytic Account",
        help="Filter by a specific analytic account, or leave empty for all."
    )

    # -------------------------------------------------------------------------
    # Display Options
    # -------------------------------------------------------------------------
    skip_zero_balance = fields.Boolean(
        string="Skip Zero Balance",
        help="Hide accounts with no initial balance and no transactions."
    )
    show_amount_currency = fields.Boolean(
        string="Show Amount Currency",
        help=(
            "Enable this option to group the report by Account, followed by Amount Currency. "
            "This will show the sum of the Amount Currency for each account in its respective "
            "currency. Essentially, this option provides a breakdown of account balances by "
            "the transaction currency used."
        )
    )

    # -------------------------------------------------------------------------
    # Date Range
    # -------------------------------------------------------------------------
    date_from = fields.Date(string='Start Date', required=True)
    date_to   = fields.Date(string='End Date',   required=True)

    # -------------------------------------------------------------------------
    # Core Report Data
    # -------------------------------------------------------------------------

    def _get_report_data(self):
        self.ensure_one()

        # ------------------------------------------------------------------
        # 1. Base domain
        # ------------------------------------------------------------------
        base_domain = [('company_id', '=', self.env.company.id)]
        states = ['posted', 'draft'] if self.include_unposted else ['posted']
        base_domain.append(('move_id.state', 'in', states))   
        if self.journal_id:
            base_domain.append(('journal_id', '=', self.journal_id.id))
        if self.analytic_account_id:
            base_domain.append(('analytic_account_id', '=', self.analytic_account_id.id))

        # ------------------------------------------------------------------
        # 2. Fetch leaf accounts
        # ------------------------------------------------------------------
        account_domain = self._build_account_domain()
        accounts = self.env['account.account'].search(account_domain, order='code asc')

        if not accounts:
            return []

        # ------------------------------------------------------------------
        # 3. Helper: normalise currency_id from read_group result
        # ------------------------------------------------------------------
        def _currency_key(group):
            raw = group.get('currency_id')
            if isinstance(raw, (list, tuple)):
                return raw[0]   # numeric id
            return raw or False

        # ------------------------------------------------------------------
        # 4. Aggregation Fields
        # ------------------------------------------------------------------
        group_fields = ['account_id']
        agg_fields   = ['debit', 'credit']
        if self.show_amount_currency:
            group_fields.append('currency_id')
            agg_fields.append('amount_currency')

        # ------------------------------------------------------------------
        # 5. OPTIMIZATION: Fetch ALL Initial Data in ONE Query
        # ------------------------------------------------------------------
        initial_data_dict = {}
        if self.date_from:
            init_domain = base_domain + [
                ('account_id', 'in', accounts.ids), 
                ('date', '<', self.date_from)
            ]
            # lazy=False is REQUIRED when grouping by multiple fields
            init_groups = self.env['account.move.line'].read_group(
                init_domain, agg_fields, group_fields, lazy=False
            )
            for g in init_groups:
                acc_id = g['account_id'][0] if isinstance(g['account_id'], tuple) else g['account_id']
                initial_data_dict.setdefault(acc_id, []).append(g)
        # If not self.date_from, initial_data_dict remains empty (Initial balance is 0)

        # ------------------------------------------------------------------
        # 6. OPTIMIZATION: Fetch ALL Move Data in ONE Query
        # ------------------------------------------------------------------
        move_domain = base_domain + [('account_id', 'in', accounts.ids)]
        if self.date_from:
            move_domain.append(('date', '>=', self.date_from))
        if self.date_to:
            move_domain.append(('date', '<=', self.date_to))
            
        move_data_dict = {}
        move_groups = self.env['account.move.line'].read_group(
            move_domain, agg_fields, group_fields, lazy=False
        )
        for g in move_groups:
            acc_id = g['account_id'][0] if isinstance(g['account_id'], tuple) else g['account_id']
            move_data_dict.setdefault(acc_id, []).append(g)

        # ------------------------------------------------------------------
        # 7. Build flat detail lines
        # ------------------------------------------------------------------
        detail_lines = []

        for account in accounts:
            # Retrieve pre-fetched data (No queries inside the loop!)
            initial_data = initial_data_dict.get(account.id, [])
            move_data = move_data_dict.get(account.id, [])

            if self.show_amount_currency:
                initial_by_cur = {_currency_key(g): g for g in initial_data}
                move_by_cur    = {_currency_key(g): g for g in move_data}
                all_currencies = set(initial_by_cur) | set(move_by_cur)

                for cur_id in all_currencies:
                    ig = initial_by_cur.get(cur_id, {})
                    mg = move_by_cur.get(cur_id, {})

                    init_bal = (ig.get('debit') or 0.0) - (ig.get('credit') or 0.0)
                    debit    =  mg.get('debit')  or 0.0
                    credit   =  mg.get('credit') or 0.0
                    amt_cur  =  mg.get('amount_currency') or 0.0
                    ending   = init_bal + debit - credit

                    if self.skip_zero_balance and not any([init_bal, debit, credit, ending]):
                        continue

                    cur_rec = self.env['res.currency'].browse(cur_id) if cur_id else None
                    detail_lines.append({
                        'code':            account.code,
                        'name':            account.name,
                        'initial':         init_bal,
                        'debit':           debit,
                        'credit':          credit,
                        'ending':          ending,
                        'currency':        cur_rec.symbol if cur_rec else '',
                        'currency_name':   cur_rec.name   if cur_rec else '',
                        'amount_currency': amt_cur,
                        'line_type':       'detail',
                    })
            else:
                ig = initial_data[0] if initial_data else {}
                mg = move_data[0]    if move_data    else {}
                if not ig and not mg:
                   continue

                init_bal = (ig.get('debit') or 0.0) - (ig.get('credit') or 0.0)
                debit    =  mg.get('debit')  or 0.0
                credit   =  mg.get('credit') or 0.0
                ending   = init_bal + debit - credit

                if self.skip_zero_balance and not any([init_bal, debit, credit, ending]):
                    continue

                detail_lines.append({
                    'code':      account.code,
                    'name':      account.name,
                    'initial':   init_bal,
                    'debit':     debit,
                    'credit':    credit,
                    'ending':    ending,
                    'line_type': 'detail',
                })

        # ------------------------------------------------------------------
        # 8. Hierarchy Compilation
        # ------------------------------------------------------------------
        if not self.hierarchy_subtotals:
            return sorted(
                detail_lines,
                key=lambda x: (x['code'], x.get('currency_name', ''))
            )

        def get_prefixes(code):
            """Return all strict prefixes of *code*, shortest first."""
            return [code[:i] for i in range(1, len(code))]

        def _zero_subtotal(prefix):
            return {
                'code':      prefix,
                'name':      self._get_group_name(prefix),
                'initial':   0.0,
                'debit':     0.0,
                'credit':    0.0,
                'ending':    0.0,
                'line_type': 'subtotal',
            }

        subtotals = {}  # prefix → aggregated subtotal dict

        for line in detail_lines:
            for prefix in get_prefixes(line['code']):
                if prefix not in subtotals:
                    subtotals[prefix] = _zero_subtotal(prefix)
                subtotals[prefix]['initial'] += line['initial']
                subtotals[prefix]['debit']   += line['debit']
                subtotals[prefix]['credit']  += line['credit']
                subtotals[prefix]['ending']  += line['ending']

        max_level    = int(self.account_level_up_to or '1')
        result_lines = []

        if self.hierarchy_only_parents:
            for prefix, subtotal in sorted(subtotals.items()):
                if len(prefix) <= max_level:
                    result_lines.append(subtotal)
        else:
            detail_by_code = {}
            for ln in detail_lines:
                detail_by_code.setdefault(ln['code'], []).append(ln)

            all_codes = sorted(set(subtotals.keys()) | set(detail_by_code.keys()))

            for code in all_codes:
                if code in subtotals:
                    result_lines.append(subtotals[code])
                if code in detail_by_code:
                    result_lines.extend(
                        sorted(
                            detail_by_code[code],
                            key=lambda x: x.get('currency_name', '')
                        )
                    )

        return result_lines

    # -------------------------------------------------------------------------
    # Helper: human-readable label for a parent prefix row
    # -------------------------------------------------------------------------

    def _get_group_name(self, prefix):
        """
        Resolve a display name for a hierarchy subtotal row identified by
        *prefix*.  Resolution order:
          1. account.group with a matching code_prefix_start  (Odoo standard)
          2. account.account whose code equals the prefix exactly
          3. Generic fallback: "Group <prefix>"
        """
        # 1. Odoo account groups
        group = self.env['account.group'].search(
            [('code_prefix_start', '=', prefix)], limit=1
        )
        if group:
            return group.name

        # 2. The prefix is itself a real account code
        account = self.env['account.account'].search(
            [('code', '=', prefix)], limit=1
        )
        if account:
            return account.name

        # 3. Generic fallback
        return f'Group {prefix}'
    



    def _build_account_domain(self):
    # Always restrict to current company and non-deprecated accounts
     domain = [
        ('company_id', '=', self.env.company.id),
        
     ]

    # Filter by account code prefixes if specified
    # e.g. account_ids_text = "101, 201, 5" → match codes starting with any prefix
     if self.account_ids_text:
        prefixes = [p.strip() for p in self.account_ids_text.split(',') if p.strip()]
        if prefixes:
            prefix_domain = expression.OR([
                [('code', '=like', prefix + '%')]
                for prefix in prefixes
            ])
            domain = expression.AND([domain, prefix_domain])

     return domain

    

    def action_pdf(self):
        return self.env.ref('azk_report.action_report_trial_balance').report_action(self)

    def action_preview(self):
        return self.env.ref('azk_report.action_report_trial_balance').report_action(
            self, config={'mode': 'html'}
        )

    def action_xlsx(self):
        return self.env.ref('azk_report.action_trial_balance_xlsx').report_action(self)