import requests
import logging
import time
import re
from bs4 import BeautifulSoup
from odoo import models, fields, api
from urllib.parse import urljoin

_logger = logging.getLogger(__name__)

class OdooPartnerScraper(models.AbstractModel):
    _name = 'azk_odoo_partner_monitor.scraper'
    _description = 'Scraping Engine'

    @api.model
    def run_daily_scrape(self):

        base_url = "https://www.odoo.com/fr_FR/partners"
        actual_partner_counts = self.get_actual_partner_counts(base_url)

        if not actual_partner_counts:
            _logger.error("Could not fetch global partner counts. Aborting to prevent data corruption.")
            return

        # Deactivate countries no longer in the dropdown
        all_countries = self.env['azk_odoo_partner_monitor.country'].search([])
        for country in all_countries:
            if country.name not in actual_partner_counts:
                if country.active:
                    country.write({'active': False})
                    _logger.info(f"Deactivated country {country.name} (no longer in dropdown).")

        
        Country = self.env['azk_odoo_partner_monitor.country']
        

        
        countries = Country.search([('active', '=', True)])

        for country in countries:
            try:
                expected = actual_partner_counts.get(country.name, {}).get('count', 0)
                country.action_validate_country_scrape(expected)

                if country.to_reprocess_partners:
                    self._scrape_country(country, base_url)

                time.sleep(2)
            except Exception as e:
                _logger.error(f"Failed to scrape {country.name}: {str(e)}")

    def _slugify(self, text):
        """Helper to convert string to URL-friendly slug"""
        if not text:
            return ""
        text = text.lower()
        return re.sub(r'[^a-z0-9]+', '-', text).strip('-')

    def _scrape_country(self, country, base_url):

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) azk_monitor/1.0'}
        country_slug = self._slugify(country.name)

        page = 1
        seen_partner_urls=set()
        scraped_count = 0
        while True:
            # Correct URL format: /country/afghanistan-3 with ?page=N for pagination
            url = f"{base_url.rstrip('/')}/country/{country_slug}-{country.country_code}"
            if page > 1:
                url += f"/page/{page}"

            _logger.info(f"Scraping {country.name} - Page {page} - URL: {url}")

            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code != 200:
                    _logger.warning(f"Got status {response.status_code} for {country.name} page {page}, stopping.")
                    break

                soup = BeautifulSoup(response.content, 'html.parser')
                partner_cards = soup.select('div.col-12.mb-4')

                if not partner_cards:
                    _logger.info(f"No partner cards found for {country.name} page {page}, stopping.")
                    break
                current_page_ids = []
                for card in partner_cards:
                  link = card.find('a', href=True)
                  if link:
                    current_page_ids.append(link['href'])

            
                if current_page_ids and all(pid in seen_partner_urls for pid in current_page_ids):
                 _logger.info(f"Duplicate content detected on page {page}. Finalizing.")
                 break
                seen_partner_urls.update(current_page_ids)

                
                
                

               

                

                for card in partner_cards:
                    partner = self._process_partner_data(card, country)
                    scraped_count += 1
                    partner_link = card.find('a', href=True)
                    partner_url = partner_link['href'] if partner_link else None

                    if partner_url and partner.to_reprocess_references:
                        self._scrape_partner_references(partner_url, partner)
                        time.sleep(1)
                        
                        
                    self.env.cr.commit()
                
                time.sleep(1.5)
                
                page += 1
            
        
            except Exception as e:
                _logger.error(f"Error on page {page} for {country.name}: {e}")

                break
        country.write({
        'total_partner_count': scraped_count,
        'to_reprocess_partners': False,
    })

    def _process_partner_data(self, card, country):
        name_elem = card.find('h5')
        partner_name = name_elem.text.strip() if name_elem else "Unknown Partner"

        badge_elem = card.select_one('.badge')
        status_raw = badge_elem.text.strip().lower() if badge_elem else 'unrated'
        number_of_avg_size, number_of_largest_size = self._extract_project_sizes(card)

        partner = self.env['azk_odoo_partner_monitor.partner'].search([
            ('name', '=', partner_name),
            ('country_id', '=', country.id)
        ], limit=1)

        if not partner:
            partner = self.env['azk_odoo_partner_monitor.partner'].create({
                'name': partner_name,
                'current_status': status_raw,
                'largest_project_size': number_of_largest_size,
                'average_project_size': number_of_avg_size,
                'country_id': country.id,
                'first_seen_on': fields.Date.today(),
            })
            self._create_history(partner, None, status_raw, 'unrated')
        else:
            if partner.current_status != status_raw:
                change_type = self._determine_change_type(partner.current_status, status_raw)
                self._create_history(partner, partner.current_status, status_raw, change_type)
                partner.current_status = status_raw

        return partner

    def _extract_project_sizes(self, soup):
        avg_size = None
        largest_size = None

        size_elems = soup.find_all('small', class_='text-muted')
        for elem in size_elems:
            text = elem.get_text(strip=True).lower()

            if 'projet moyen' in text:
                digits = re.findall(r'\d+', text)
                if digits:
                    avg_size = int(digits[0])

            elif 'grand projet' in text:
                digits = re.findall(r'\d+', text)
                if digits:
                    largest_size = int(digits[0])

        return avg_size, largest_size

    def _create_history(self, partner, old_status, new_status, change_type):
        self.env['azk_odoo_partner_monitor.status.history'].create({
            'partner_id': partner.id,
            'previous_status': old_status or False,
            'new_status': new_status,
            'change_type': change_type,
        })

    def _determine_change_type(self, old, new):
        rank = {'gold': 3, 'silver': 2, 'ready': 1, 'unrated': 0}
        if rank.get(new, 0) > rank.get(old, 0):
            return 'promoted'
        return 'demoted'

    def _scrape_partner_references(self, rest_url_ref, partner):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) azk_monitor/1.0'}
            url = urljoin("https://www.odoo.com", rest_url_ref)

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return

            soup = BeautifulSoup(response.content, 'html.parser')
            reference_cards = soup.find_all('div', class_='card-body')

            expected_ref_count = len(reference_cards)
            scraped_ref_names = [
                card.find('span').text.strip()
                for card in reference_cards
                if card.find('span')
            ]

            partner.action_validate_partner_scrape(expected_ref_count)

            if partner.to_reprocess_references:
                self._sync_references(partner, scraped_ref_names)

        except Exception as e:
            _logger.error(f"Failed to scrape references for {partner.name}: {e}")

    def _sync_references(self, partner, scraped_names):
        Reference = self.env['azk_odoo_partner_monitor.reference']
        existing_refs = Reference.search([
            ('partner_id', '=', partner.id),
            ('is_active', '=', True)
        ])

        existing_names = set(existing_refs.mapped('name'))
        scraped_names_set = set(scraped_names)

        # Create new references
        for name in (scraped_names_set - existing_names):
            Reference.create({
                'partner_id': partner.id,
                'name': name,
                'is_active': True,
                'added_on': fields.Date.today(),
            })

        # Archive removed references
        for ref in existing_refs:
            if ref.name not in scraped_names_set:
                ref.write({'is_active': False, 'removed_on': fields.Date.today()})

    def get_actual_partner_counts(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) azk_monitor/1.0'
        }
        counts_dict = {}

        _logger.info("Starting scraping partner counts from URL: %s", url)

        try:
            response = requests.get(url, headers=headers, timeout=10)
            _logger.debug("HTTP Status Code: %s", response.status_code)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all(
                'a',
                class_='dropdown-item d-flex justify-content-between'
            )

            _logger.info("Found %s country items in dropdown", len(items))

            for item in items:
                try:
                    # Extract the numeric Odoo country ID from the href
                    # e.g. href="/fr_FR/partners/country/afghanistan-3"
                    href = item.get('href', '')
                    match = re.search(r'-(\d+)$', href)
                    odoo_id = int(match.group(1)) if match else None

                    badge = item.find('span', class_='badge')
                    if not badge:
                        _logger.debug("Skipping item without badge: %s", item)
                        continue

                    count_str = badge.get_text(strip=True)
                    badge.extract()  # Remove badge to isolate country name
                    country_name = item.get_text(strip=True)
                    clean_count = ''.join(filter(str.isdigit, count_str))

                    if clean_count and country_name and odoo_id is not None:
                        counts_dict[country_name] = {
                            'count': int(clean_count),
                            'odoo_id': odoo_id,
                        }
                        _logger.debug(
                            "Parsed country: %s -> %s partners (odoo_id=%s)",
                            country_name, clean_count, odoo_id
                        )
                    else:
                        _logger.warning(
                            "Invalid data parsed. Country: %s | Count: %s | odoo_id: %s",
                            country_name, count_str, odoo_id
                        )

                except Exception as parse_item_error:
                    _logger.error(
                        "Error parsing item: %s | Error: %s",
                        item, parse_item_error
                    )

            _logger.info("Finished scraping. Total countries parsed: %s", len(counts_dict))
            return counts_dict

        except requests.exceptions.Timeout:
            _logger.error("Timeout error while requesting URL: %s", url)
        except requests.exceptions.HTTPError as http_err:
            _logger.error("HTTP error occurred: %s | URL: %s", http_err, url)
        except requests.exceptions.RequestException as req_err:
            _logger.error("Request exception: %s | URL: %s", req_err, url)
        except Exception as e:
            _logger.exception("Unexpected parsing error: %s", e)

        return {}