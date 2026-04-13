from odoo import models
import io
import xlsxwriter


class TrialBalanceXlsx(models.AbstractModel):
    _name = 'report.azk_report.trial_balance_xlsx'
    _description = 'Trial Balance XLSX Report'

    def create_xlsx_report(self, docids, data):
        wizard = self.env['trial.balance.wizard'].browse(docids)
        report_lines = wizard._get_report_data()

        output   = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # ── Formats ──────────────────────────────────────────────────────────

        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14,
            'align': 'center', 'valign': 'vcenter',
        })
        subtitle_fmt = workbook.add_format({
            'italic': True, 'font_size': 10,
            'align': 'center', 'font_color': '#555555',
        })
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#2E4057', 'font_color': '#FFFFFF',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 10,
        })
        info_fmt = workbook.add_format({
            'italic': True, 'font_size': 8, 'font_color': '#777777',
        })

        # Detail rows – normal and alternating
        text_fmt = workbook.add_format({
            'border': 1, 'align': 'left', 'valign': 'vcenter', 'font_size': 9,
        })
        num_fmt = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter', 'font_size': 9,
            'num_format': '#,##0.00;(#,##0.00);-',
        })
        num_pos_fmt = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter', 'font_size': 9,
            'num_format': '#,##0.00',
        })
        row_alt_fmt = workbook.add_format({
            'border': 1, 'align': 'left', 'valign': 'vcenter',
            'font_size': 9, 'bg_color': '#F2F2F2',
        })
        num_alt_fmt = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter',
            'font_size': 9, 'num_format': '#,##0.00;(#,##0.00);-',
            'bg_color': '#F2F2F2',
        })
        num_pos_alt_fmt = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter',
            'font_size': 9, 'num_format': '#,##0.00', 'bg_color': '#F2F2F2',
        })

        # Subtotal / hierarchy group rows
        subtotal_text_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'left', 'valign': 'vcenter',
            'font_size': 9, 'bg_color': '#E8F0FE', 'font_color': '#1A237E',
        })
        subtotal_num_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'right', 'valign': 'vcenter',
            'font_size': 9, 'num_format': '#,##0.00;(#,##0.00);-',
            'bg_color': '#E8F0FE', 'font_color': '#1A237E',
        })

        # Grand total footer row
        total_label_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'left', 'valign': 'vcenter',
            'bg_color': '#2E4057', 'font_color': '#FFFFFF', 'font_size': 9,
        })
        total_num_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'right', 'valign': 'vcenter',
            'bg_color': '#2E4057', 'font_color': '#FFFFFF', 'font_size': 9,
            'num_format': '#,##0.00;(#,##0.00);-',
        })

        # ── Column definitions ────────────────────────────────────────────────

        if wizard.show_amount_currency:
            
            col_widths = [12, 40, 10, 18, 18, 18, 18, 18]
            headers    = [
                'Code', 'Account Name', 'Currency', 'Amount Currency',
                'Initial Balance', 'Debit', 'Credit', 'Ending Balance',
            ]
        else:
            
            col_widths = [12, 40, 18, 18, 18, 18]
            headers    = [
                'Code', 'Account Name',
                'Initial Balance', 'Debit', 'Credit', 'Ending Balance',
            ]

        # ── Sheet setup ───────────────────────────────────────────────────────

        sheet = workbook.add_worksheet('Trial Balance')
        sheet.set_landscape()
        sheet.set_paper(9)       # A4
        sheet.fit_to_pages(1, 0)

        for col, w in enumerate(col_widths):
            sheet.set_column(col, col, w)

        sheet.set_row(0, 28)
        sheet.set_row(1, 18)
        sheet.set_row(2, 18)
        sheet.set_row(4, 22)

        # ── Title block ───────────────────────────────────────────────────────

        last_col = len(headers) - 1
        company  = wizard.env.company

        sheet.merge_range(0, 0, 0, last_col, company.name, title_fmt)
        sheet.merge_range(1, 0, 1, last_col, 'Trial Balance', subtitle_fmt)
        sheet.merge_range(
            2, 0, 2, last_col,
            f"From {wizard.date_from.strftime('%d/%m/%Y')} to {wizard.date_to.strftime('%d/%m/%Y')}",
            subtitle_fmt,
        )

        # ── Column headers ────────────────────────────────────────────────────

        for col, h in enumerate(headers):
            sheet.write(4, col, h, header_fmt)

        # ── Data rows ─────────────────────────────────────────────────────────

        row    = 5
        totals = {'initial': 0.0, 'debit': 0.0, 'credit': 0.0, 'ending': 0.0}
        detail_row_idx = 0   # separate counter for alternating colour on detail lines only

        for line in report_lines:
            line_type = line.get('line_type', 'detail')

            if line_type == 'subtotal':
                # ── Hierarchy group / subtotal row ──────────────────────────
                label = f"{line['code']}  {line.get('name', '')}".strip()
                sheet.write(row, 0, line['code'], subtotal_text_fmt)
                sheet.write(row, 1, line.get('name', ''), subtotal_text_fmt)

                if wizard.show_amount_currency:
                    # Currency and Amount Currency columns left blank for subtotals
                    sheet.write(row, 2, '', subtotal_text_fmt)
                    sheet.write(row, 3, '', subtotal_text_fmt)
                    sheet.write(row, 4, line['initial'], subtotal_num_fmt)
                    sheet.write(row, 5, line['debit'],   subtotal_num_fmt)
                    sheet.write(row, 6, line['credit'],  subtotal_num_fmt)
                    sheet.write(row, 7, line['ending'],  subtotal_num_fmt)
                else:
                    sheet.write(row, 2, line['initial'], subtotal_num_fmt)
                    sheet.write(row, 3, line['debit'],   subtotal_num_fmt)
                    sheet.write(row, 4, line['credit'],  subtotal_num_fmt)
                    sheet.write(row, 5, line['ending'],  subtotal_num_fmt)

            else:
                # ── Detail account row ───────────────────────────────────────
                is_alt = detail_row_idx % 2 != 0
                t_fmt  = row_alt_fmt     if is_alt else text_fmt
                n_fmt  = num_alt_fmt     if is_alt else num_fmt
                np_fmt = num_pos_alt_fmt if is_alt else num_pos_fmt

                sheet.write(row, 0, line['code'], t_fmt)
                sheet.write(row, 1, line['name'], t_fmt)

                if wizard.show_amount_currency:
                    sheet.write(row, 2, line.get('currency', ''),        t_fmt)
                    sheet.write(row, 3, line.get('amount_currency', 0.0), np_fmt)
                    sheet.write(row, 4, line['initial'], n_fmt)
                    sheet.write(row, 5, line['debit'],   np_fmt)
                    sheet.write(row, 6, line['credit'],  np_fmt)
                    sheet.write(row, 7, line['ending'],  n_fmt)
                else:
                    sheet.write(row, 2, line['initial'], n_fmt)
                    sheet.write(row, 3, line['debit'],   np_fmt)
                    sheet.write(row, 4, line['credit'],  np_fmt)
                    sheet.write(row, 5, line['ending'],  n_fmt)

                
                for k in totals:
                    totals[k] += line[k]

                detail_row_idx += 1

            row += 1

        # ── Grand total row ───────────────────────────────────────────────────

        sheet.merge_range(row, 0, row, 1, 'TOTAL', total_label_fmt)

        if wizard.show_amount_currency:
            sheet.write(row, 2, '', total_label_fmt)   # Currency – blank
            sheet.write(row, 3, '', total_label_fmt)   # Amount Currency – blank
            sheet.write(row, 4, totals['initial'], total_num_fmt)
            sheet.write(row, 5, totals['debit'],   total_num_fmt)
            sheet.write(row, 6, totals['credit'],  total_num_fmt)
            sheet.write(row, 7, totals['ending'],  total_num_fmt)
        else:
            sheet.write(row, 2, totals['initial'], total_num_fmt)
            sheet.write(row, 3, totals['debit'],   total_num_fmt)
            sheet.write(row, 4, totals['credit'],  total_num_fmt)
            sheet.write(row, 5, totals['ending'],  total_num_fmt)

        # ── Filters summary ───────────────────────────────────────────────────

        filters = []
        if wizard.journal_id:
            filters.append(f"Journal: {wizard.journal_id.display_name}")
        if wizard.analytic_account_id:
            filters.append(f"Analytic Account: {wizard.analytic_account_id.display_name}")
        if wizard.account_ids_text:
            filters.append(f"Account Prefixes: {wizard.account_ids_text}")
        if wizard.include_unposted:
            filters.append("Includes unposted entries")
        if wizard.skip_zero_balance:
            filters.append("Zero-balance accounts hidden")
        if wizard.show_amount_currency:
            filters.append("Grouped by currency")
        if wizard.hierarchy_subtotals:
            label = "Hierarchy + Subtotals"
            if wizard.hierarchy_only_parents:
                label += f" (Parents only – level {wizard.account_level_up_to})"
            filters.append(label)

        if filters:
            sheet.merge_range(
                row + 2, 0, row + 2, last_col,
                "Filters: " + " | ".join(filters),
                info_fmt,
            )

        workbook.close()
        output.seek(0)
        return (
            output.read(),
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )