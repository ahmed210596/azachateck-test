from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestTrialBalance(TransactionCase):

    # -------------------------------------------------------------------------
    # Shared fixtures
    # -------------------------------------------------------------------------

    def setUp(self):
        super().setUp()

        # ------------------------------------------------------------------
        # 1. Isolated company → zero pollution from other modules' data
        # ------------------------------------------------------------------
        self.test_company = self.env['res.company'].create({
            'name': 'AZK Test Company',
        })
        self.test_company.currency_id = self.env.ref('base.TND') 
        self.env.user.write({
            'company_ids': [(4, self.test_company.id)],
            'company_id':  self.test_company.id,
        })
        # Ensure every ORM call below uses the isolated company
        self.env = self.env(context=dict(
            self.env.context,
            allowed_company_ids=[self.test_company.id],
        ))

        # ------------------------------------------------------------------
        # 2. Currencies
        # ------------------------------------------------------------------
        self.usd = self.env.ref('base.USD')
        self.eur = self.env.ref('base.EUR')

        # ------------------------------------------------------------------
        # 3. Account types
        # ------------------------------------------------------------------
        type_liquidity  = self.env.ref('account.data_account_type_liquidity')
        type_receivable = self.env.ref('account.data_account_type_receivable')
        type_payable    = self.env.ref('account.data_account_type_payable')
        type_revenue    = self.env.ref('account.data_account_type_revenue')

        # ------------------------------------------------------------------
        # 4. Accounts
        # ------------------------------------------------------------------
        self.account_cash = self.env['account.account'].create({
            'code':         '101',
            'name':         'Cash',
            'user_type_id': type_liquidity.id,
            'company_id':   self.test_company.id,
        })
        self.account_receivable = self.env['account.account'].create({
            'code':         '102',
            'name':         'Accounts Receivable',
            'user_type_id': type_receivable.id,
            'reconcile':    True,
            'company_id':   self.test_company.id,
        })
        self.account_payable = self.env['account.account'].create({
            'code':         '201',
            'name':         'Accounts Payable',
            'user_type_id': type_payable.id,
            'reconcile':    True,
            'company_id':   self.test_company.id,
        })
        self.account_sales = self.env['account.account'].create({
            'code':         '501',
            'name':         'Sales Revenue',
            'user_type_id': type_revenue.id,
            'company_id':   self.test_company.id,
        })

        # ------------------------------------------------------------------
        # 5. Journals
        # ------------------------------------------------------------------
        self.journal_bank = self.env['account.journal'].create({
            'name':       'Bank Journal (Test)',
            'code':       'TBNK',
            'type':       'bank',
            'company_id': self.test_company.id,
        })
        self.journal_sales = self.env['account.journal'].create({
            'name':       'Sales Journal (Test)',
            'code':       'TSAL',
            'type':       'sale',
            'company_id': self.test_company.id,
        })

        # ------------------------------------------------------------------
        # 6. Analytic accounts
        # ------------------------------------------------------------------
        self.analytic_marketing = self.env['account.analytic.account'].create({
            'name':       'Marketing Dept',
            'company_id': self.test_company.id,
        })
        self.analytic_it = self.env['account.analytic.account'].create({
            'name':       'IT Dept',
            'company_id': self.test_company.id,
        })

        # ------------------------------------------------------------------
        # 7. Account groups (for hierarchy tests)
        # ------------------------------------------------------------------
        self.env['account.group'].create([
            {'name': 'Assets',              'code_prefix_start': '1',  'code_prefix_end': '1'},
            {'name': 'Current Assets',      'code_prefix_start': '10', 'code_prefix_end': '10'},
            {'name': 'Liabilities',         'code_prefix_start': '2',  'code_prefix_end': '2'},
            {'name': 'Current Liabilities', 'code_prefix_start': '20', 'code_prefix_end': '20'},
            {'name': 'Revenue',             'code_prefix_start': '5',  'code_prefix_end': '5'},
            {'name': 'Sales Revenue',       'code_prefix_start': '50', 'code_prefix_end': '50'},
        ])

        # ------------------------------------------------------------------
        # 8. Moves
        # ------------------------------------------------------------------

        # --- 8a. Initial balance move (Dec 2025 → before date_from) -------
        #   DR Cash 101    1000
        #   CR Sales 501   1000
        move_init = self.env['account.move'].create({
            'journal_id': self.journal_sales.id,
            'date':       '2025-12-01',
            'company_id': self.test_company.id,
            'line_ids': [
                (0, 0, {
                    'account_id': self.account_cash.id,
                    'debit':      1000.0,
                    'credit':     0.0,
                    'name':       'Initial Cash – company currency',
                }),
                (0, 0, {
                    'account_id': self.account_sales.id,
                    'debit':      0.0,
                    'credit':     1000.0,
                    'name':       'Initial Sales Revenue',
                }),
            ],
        })
        move_init.action_post()

        # --- 8b. Posted USD move (Jan 2026, sales journal, marketing) -----
        #   DR Cash 101    3200   (USD 1000)
        #   CR Sales 501   3200   (USD -1000)
        move_usd = self.env['account.move'].create({
            'journal_id': self.journal_sales.id,
            'date':       '2026-01-10',
            'company_id': self.test_company.id,
            'line_ids': [
                (0, 0, {
                    'account_id':          self.account_cash.id,
                    'debit':               3200.0,
                    'credit':              0.0,
                    'currency_id':         self.usd.id,
                    'amount_currency':     1000.0,
                    'name':                'Cash receipt USD',
                    'analytic_account_id': self.analytic_marketing.id,
                }),
                (0, 0, {
                    'account_id':          self.account_sales.id,
                    'debit':               0.0,
                    'credit':              3200.0,
                    'currency_id':         self.usd.id,
                    'amount_currency':     -1000.0,
                    'name':                'Sales USD',
                    'analytic_account_id': self.analytic_marketing.id,
                }),
            ],
        })
        move_usd.action_post()

        # --- 8c. Posted EUR move (Feb 2026, bank journal, IT) -------------
        #   DR Receivable 102   1600   (EUR 500)
        #   CR Cash 101         1600   (EUR -500)
        move_eur = self.env['account.move'].create({
            'journal_id': self.journal_bank.id,
            'date':       '2026-02-20',
            'company_id': self.test_company.id,
            'line_ids': [
                (0, 0, {
                    'account_id':          self.account_receivable.id,
                    'debit':               1600.0,
                    'credit':              0.0,
                    'currency_id':         self.eur.id,
                    'amount_currency':     500.0,
                    'name':                'Receivable EUR',
                    'analytic_account_id': self.analytic_it.id,
                }),
                (0, 0, {
                    'account_id':          self.account_cash.id,
                    'debit':               0.0,
                    'credit':              1600.0,
                    'currency_id':         self.eur.id,
                    'amount_currency':     -500.0,
                    'name':                'Cash payment EUR',
                    'analytic_account_id': self.analytic_it.id,
                }),
            ],
        })
        move_eur.action_post()

        # --- 8d. Draft EUR move (Mar 2026, bank journal, IT) --------------
        #   DR Payable 201   500   (EUR 500)
        #   CR Cash 101      500   (EUR -500)
        self.move_draft = self.env['account.move'].create({
            'journal_id': self.journal_bank.id,
            'date':       '2026-03-05',
            'company_id': self.test_company.id,
            'line_ids': [
                (0, 0, {
                    'account_id':          self.account_payable.id,
                    'debit':               500.0,
                    'credit':              0.0,
                    'currency_id':         self.eur.id,
                    'amount_currency':     500.0,
                    'name':                'Draft Payable EUR',
                    'analytic_account_id': self.analytic_it.id,
                }),
                (0, 0, {
                    'account_id':          self.account_cash.id,
                    'debit':               0.0,
                    'credit':              500.0,
                    'currency_id':         self.eur.id,
                    'amount_currency':     -500.0,
                    'name':                'Draft Cash EUR',
                    'analytic_account_id': self.analytic_it.id,
                }),
            ],
            # state remains 'draft' – do NOT call action_post()
        })

    # -------------------------------------------------------------------------
    # Wizard factory
    # -------------------------------------------------------------------------

    def _create_wizard(self, **kwargs):
        """Create a TrialBalanceWizard with sensible defaults."""
        defaults = {
            'date_from': '2026-01-01',
            'date_to':   '2026-12-31',
        }
        defaults.update(kwargs)
        return self.env['trial.balance.wizard'].create(defaults)

    # =========================================================================
    # test_01 – Basic trial balance (posted only, no options)
    # =========================================================================
    def test_01_basic_trial_balance(self):
        """Posted accounts appear; unposted account 201 is absent."""
        wizard = self._create_wizard()
        lines  = wizard._get_report_data()
        codes  = [l['code'] for l in lines]

        self.assertIn('101', codes, "Cash account must be present")
        self.assertIn('501', codes, "Sales account must be present")
        self.assertNotIn('201', codes, "Payable must be hidden (draft only)")

    # =========================================================================
    # test_02 – Include unposted entries
    # =========================================================================
    def test_02_include_unposted(self):
        """With include_unposted, the draft payable entry must appear."""
        wizard = self._create_wizard(include_unposted=True)
        lines  = wizard._get_report_data()
        codes  = [l['code'] for l in lines]

        self.assertIn('201', codes, "Payable must appear when unposted is included")

        payable_line = next(l for l in lines if l['code'] == '201')
        self.assertAlmostEqual(
            payable_line['debit'], 500.0, places=2,
            msg="Payable debit must be 500.0 from the draft EUR entry",
        )

    # =========================================================================
    # test_03 – Initial balance calculation
    # =========================================================================
    def test_03_initial_balance(self):
        """
        move_init is dated 2025-12-01 → before date_from 2026-01-01.
        Cash account 101 must carry an initial balance of exactly +1000.0.
        No other moves exist in this isolated company before 2026-01-01.
        """
        wizard = self._create_wizard()
        lines  = wizard._get_report_data()

        cash_line = next(
            (l for l in lines
             if l['code'] == '101' and l.get('line_type') == 'detail'),
            None,
        )
        self.assertIsNotNone(cash_line, "Cash detail line must exist")
        self.assertAlmostEqual(
            cash_line['initial'], 1000.0, places=2,
            msg="Cash initial balance must be exactly 1000.0",
        )

    # =========================================================================
    # test_04 – Skip zero balance
    # =========================================================================
    def test_04_skip_zero_balance(self):
        """
        All detail lines returned must have at least one non-zero value
        when skip_zero_balance=True.
        """
        wizard = self._create_wizard(skip_zero_balance=True)
        lines  = wizard._get_report_data()

        detail_lines = [l for l in lines if l.get('line_type') == 'detail']
        for line in detail_lines:
            has_value = any([
                line['initial'],
                line['debit'],
                line['credit'],
                line['ending'],
            ])
            self.assertTrue(
                has_value,
                f"Account {line['code']} has all-zero values but was not skipped",
            )

    # =========================================================================
    # test_05 – Multi-currency breakdown (show_amount_currency)
    # =========================================================================
    def test_05_multi_currency_breakdown(self):
        """
        Account 101 must appear twice: once for USD (+1000.0) and once
        for EUR (-500.0).
        """
        wizard = self._create_wizard(show_amount_currency=True)
        lines  = wizard._get_report_data()

        usd_line = next(
            (l for l in lines
             if l['code'] == '101' and l.get('currency_name') == 'USD'),
            None,
        )
        eur_line = next(
            (l for l in lines
             if l['code'] == '101' and l.get('currency_name') == 'EUR'),
            None,
        )

        self.assertIsNotNone(usd_line, "Cash/USD line must exist")
        self.assertIsNotNone(eur_line, "Cash/EUR line must exist")

        self.assertAlmostEqual(
            usd_line['amount_currency'], 1000.0, places=2,
            msg="USD amount_currency must be +1000.0",
        )
        self.assertAlmostEqual(
            eur_line['amount_currency'], -500.0, places=2,
            msg="EUR amount_currency must be -500.0",
        )

    # =========================================================================
    # test_06 – Analytic account filter
    # =========================================================================
    def test_06_analytic_filter(self):
        """
        Filtering by analytic_marketing must include 101 and 501 (USD move),
        but NOT 102 (IT Dept only).
        """
        wizard = self._create_wizard(
            analytic_account_id=self.analytic_marketing.id,
        )
        lines = wizard._get_report_data()
        codes = [l['code'] for l in lines]

        self.assertIn('101',    codes, "Cash must appear (marketing USD move)")
        self.assertIn('501',    codes, "Sales must appear (marketing USD move)")
        self.assertNotIn('102', codes, "Receivable is IT only – must be absent")

    # =========================================================================
    # test_07 – Hierarchy subtotals (with detail lines)
    # =========================================================================
    def test_07_hierarchy_subtotals(self):
        """
        With hierarchy_subtotals=True both subtotal rows and detail rows
        must be present.  Subtotal '10' must aggregate accounts 101 and 102.
        """
        wizard = self._create_wizard(hierarchy_subtotals=True)
        lines  = wizard._get_report_data()

        subtotal_codes = [l['code'] for l in lines if l.get('line_type') == 'subtotal']
        detail_codes   = [l['code'] for l in lines if l.get('line_type') == 'detail']

        self.assertIn('10',  subtotal_codes, "Subtotal for prefix '10' must exist")
        self.assertIn('101', detail_codes,   "Detail line for 101 must still be present")
        self.assertIn('102', detail_codes,   "Detail line for 102 must still be present")

        subtotal_10 = next(l for l in lines
                           if l['code'] == '10' and l.get('line_type') == 'subtotal')
        detail_101  = next(l for l in lines
                           if l['code'] == '101' and l.get('line_type') == 'detail')
        detail_102  = next(l for l in lines
                           if l['code'] == '102' and l.get('line_type') == 'detail')

        expected_debit = detail_101['debit'] + detail_102['debit']
        self.assertAlmostEqual(
            subtotal_10['debit'], expected_debit, places=2,
            msg="Subtotal '10' debit must equal sum of its children",
        )

    # =========================================================================
    # test_08 – Hierarchy only parents with account_level_up_to
    # =========================================================================
    def test_08_hierarchy_only_parents_level(self):
        """
        With hierarchy_only_parents=True and account_level_up_to='2',
        only subtotal rows with code length ≤ 2 must appear.
        No detail lines must be present.
        """
        wizard = self._create_wizard(
            hierarchy_subtotals=True,
            hierarchy_only_parents=True,
            account_level_up_to='2',
            include_unposted=True

        )
        lines = wizard._get_report_data()

        detail_lines = [l for l in lines if l.get('line_type') == 'detail']
        self.assertFalse(detail_lines,
                         "No detail lines must appear in parents-only mode")

        for line in lines:
            self.assertLessEqual(
                len(line['code']), 2,
                f"Code '{line['code']}' exceeds level 2",
            )

        subtotal_codes    = [l['code'] for l in lines]
        expected_prefixes = ['1', '10', '2', '20', '5', '50']
        for prefix in expected_prefixes:
            self.assertIn(
                prefix, subtotal_codes,
                f"Prefix '{prefix}' must exist in parents-only mode",
            )

    # =========================================================================
    # test_09 – Journal filter
    # =========================================================================
    def test_09_journal_filter(self):
        """
        Filtering by journal_sales must return only accounts touched by
        that journal.  Account 102 lives only in journal_bank.
        """
        wizard = self._create_wizard(journal_id=self.journal_sales.id)
        lines  = wizard._get_report_data()
        codes  = [l['code'] for l in lines]

        self.assertIn('101',    codes, "Cash appears in sales journal (USD move)")
        self.assertNotIn('102', codes, "Receivable is bank journal only")

    # =========================================================================
    # test_10 – Ending balance integrity
    # =========================================================================
    def test_10_ending_balance_integrity(self):
        """
        For every detail line: ending = initial + debit − credit.
        """
        wizard = self._create_wizard()
        lines  = wizard._get_report_data()

        for line in lines:
            if line.get('line_type') != 'detail':
                continue
            expected = line['initial'] + line['debit'] - line['credit']
            self.assertAlmostEqual(
                line['ending'], expected, places=2,
                msg=(
                    f"Ending balance mismatch on account {line['code']}: "
                    f"expected {expected}, got {line['ending']}"
                ),
            )