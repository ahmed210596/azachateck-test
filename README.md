# azachateck-test-odoo version 14
Exercise 1 – Odoo Partner Monitor (azk_odoo_partner_monitor)
Objective: Scrape partner data from the official Odoo Partners page, store historical changes, and provide dashboards for analysis.

Testing Approach:

Scraping Validation

Ran the scraper against the live Odoo Partners page.

Verified that partner records (name, country, website, certification level) were correctly extracted.

Checked resilience by simulating page layout changes and ensuring the scraper still returned structured data.

Data Storage & History

Confirmed that new runs appended changes instead of overwriting existing records.

Validated historical tracking by comparing snapshots across multiple runs.

Analytics & Dashboards

Tested dashboard filters ( certification level, partner name,referefrence).

Verified that charts updated dynamically when new scraped data was added.

Resilience & Error Handling               

Simulated network failures and invalid HTML responses.

Ensured the module logged errors gracefully without breaking Odoo.

Exercise 2 – Trial Balance Reports (azk_report)
Objective: Provide a wizard-driven trial balance report with PDF, HTML preview, and XLSX export.

Testing Approach:

Wizard Options

Tested all combinations: include unposted entries, hierarchy subtotals, parent-only mode, account prefix filters, skip zero balances, and currency grouping.

Verified that each option correctly influenced the report output.

PDF/HTML Reports

Generated reports with different filters.

Checked that subtotals, detail rows, and totals matched accounting data.

Confirmed that applied filters appeared in the header and badges.

XLSX Reports

Exported trial balance to Excel.

Validated formatting: alternating row colors, subtotal highlights, grand total footer.

Ensured numeric values matched the PDF/HTML report.

Data Consistency

Cross-checked totals against Odoo’s native trial balance.

Verified consistency across PDF, HTML, and XLSX outputs.

Edge Cases

Tested with no accounts matching filters → report returned empty with a clear message.

Tested with multiple currencies → verified correct grouping and currency symbols.

Tested with hierarchy depth limits → confirmed parent-only levels were respected                      <img width="1556" height="427" alt="image" src="https://github.com/user-attachments/assets/2c360c91-eb62-45e0-99f8-2512ba58ee7d" />

<img width="1889" height="652" alt="image" src="https://github.com/user-attachments/assets/b61b7507-f18e-49e7-9530-027070d3f672" />

