import json
import logging
import requests

from bs4 import BeautifulSoup
from models import db, TableTrustedShopsDe, TableMailDB
from peewee import IntegrityError
from time import sleep
from threading import Thread

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class RequestBeautifulSoupMixin:
    def get(self, url, retry=0, *args, **kwargs):
        if retry > 3:
            logging.error(f"retry count {retry} for {url}. passing...")
            return None
        response = requests.get(url, **kwargs)
        if response.status_code == 200 and response.ok:
            return response
        return self.get(url, retry=retry + 1, *args, **kwargs)

    @staticmethod
    def soup(content, features):
        return BeautifulSoup(markup=content, features=features)


class TrustedShopsDe(RequestBeautifulSoupMixin):

    def __init__(self, base_url):
        self.base_url = base_url
        self.search_url = f"{self.base_url}/shops/"

    @staticmethod
    def database_operations():
        if db.is_closed():
            db.connect()
        db.create_tables([TableTrustedShopsDe])

    def category_extractor(self, url, css_path, category_name_selector):
        response = self.get(url=url)
        soup = self.soup(content=response.content, features='lxml')
        category_li_items = soup.select(css_path)
        categories = []
        for category in category_li_items:
            category_name = category.select_one(category_name_selector)
            category_name = category_name.text if category_name else ''
            url = f"{self.base_url}{category.get('href')}"
            categories.append(dict(name=category_name, url=url))
        return categories

    def save_company(self,**kwargs):
        try:
            instance = TableTrustedShopsDe(**kwargs)
            instance.save()
        except IntegrityError:
            return

    def extract_company(self, company_url, main_category_name, sub_category_name):
        response = self.get(url=company_url)
        if not response:
            return
        soup = self.soup(content=response.content, features='lxml')
        application_data = soup.select_one('script#__NEXT_DATA__')
        if application_data:
            json_data = json.loads(application_data.text)
            profile = json_data.get('props', {}).get('pageProps', {}).get('profile')
            company_name = profile.get('name')
            organization_name = profile.get('organization', {}).get('name', '')
            address = " ".join(profile.get('address', {}).values())
            phone = profile.get('contactData', {}).get('phone')
            website = profile.get('url', '')
            email = profile.get('contactData', {}).get('email')
            rate_count = str(profile.get('reviewStatistic', {}).get('allTimeReviewCount', '0'))
            rate_value = str(profile.get('reviewStatistic', {}).get('grade', '0'))

            if not email or TableMailDB.select().where(TableMailDB.email == email).exists():
                logging.warning(f"{email} exist passing")
                return
            company_data = dict(company_name=company_name, organization_name=organization_name, address=address,
                                phone=phone, website=website, email=email, rate_count=rate_count, rate_value=rate_value,
                                main_category=main_category_name, sub_category=sub_category_name)
            self.save_company(**company_data)

    def extract_companies(self, company_items, main_category_name, sub_category_name):
        threads = []
        for company_item in company_items:
            company_url = company_item.get('href')
            process = Thread(target=self.extract_company, args=(company_url, main_category_name, sub_category_name),
                             daemon=True)
            process.start()
            threads.append(process)

        for thread in threads:
            thread.join()

    def extract_sub_category(self, main_category_name, sub_category_name, sub_category_url, log_text, page=1):
        while True:

            params = {
                "page": page
            }
            response = self.get(url=sub_category_url, params=params)
            if not response:
                break
            soup = self.soup(content=response.content, features='lxml')
            page_count = soup.select('div.Paginationstyles__Pagination-sc-1uibxtv-0 a')[-3]
            page_count = page_count.text if page_count else '???'
            company_items = soup.select('main a.ShopResultItemstyles__ResultItem-sc-3gooul-0')
            logging.info(f"{log_text}\n"
                         f"Page: {page}/{page_count}")
            self.extract_companies(company_items, main_category_name, sub_category_name)
            page += 1

    def extract_main_categories(self, main_categories):
        for index, main_category in enumerate(main_categories, start=1):
            main_category_name = main_category.get('name')
            main_category_url = main_category.get('url')
            sub_categories = self.category_extractor(url=main_category_url,
                                                     css_path='aside ul.CategoryFilterstyles__Category-sc-vu79ja-1 li a',
                                                     category_name_selector='span.categoryName')
            for sub_category_index, sub_category in enumerate(sub_categories, start=1):
                sub_category_name = sub_category.get('name')
                sub_category_url = sub_category.get('url')
                log_text = (f"Main Category Process: {index}/{len(main_categories)} - {main_category_name}\n"
                            f"Sub Category Process: {sub_category_index}/{len(sub_categories)} - {sub_category_name}")
                self.extract_sub_category(main_category_name, sub_category_name, sub_category_url, log_text)

    def run(self):
        self.database_operations()
        main_categories = self.category_extractor(url=self.search_url,
                                                  css_path='ul.CategoryFilterstyles__Category-sc-vu79ja-1 li a',
                                                  category_name_selector='div.categoryName')
        self.extract_main_categories(main_categories[:1])


if __name__ == '__main__':
    tsd = TrustedShopsDe(
        base_url="https://www.trustedshops.de"
    )
    tsd.run()
