"""
Crawler implementation.
"""
# pylint: disable=too-many-arguments, too-many-instance-attributes, unused-import, undefined-variable
import datetime
import json
import pathlib
import re
from time import sleep
from typing import Pattern, Union

from bs4 import BeautifulSoup
import requests

from core_utils.article.article import Article
from core_utils.article.io import to_meta, to_raw
from core_utils import constants
from core_utils.config_dto import ConfigDTO


class IncorrectSeedURLError(Exception):
    """
    The seed url is not alike the pattern.
    """


class NumberOfArticlesOutOfRangeError(Exception):
    """
    The number of articles is not in range of 1 to 150.
    """


class IncorrectNumberOfArticlesError(Exception):
    """
    The article number is not integer.
    """


class IncorrectHeadersError(Exception):
    """
    The headers are not stored in a dictionary.
    """


class IncorrectEncodingError(Exception):
    """
    The encoding is not a string.
    """


class IncorrectTimeoutError(Exception):
    """
    The timeout is not an integer or is not in the range.
    """


class IncorrectVerifyError(Exception):
    """
    Verification check or Headless mode are not boolean.
    """


class Config:
    """
    Class for unpacking and validating configurations.
    """

    def __init__(self, path_to_config: pathlib.Path) -> None:
        """
        Initialize an instance of the Config class.

        Args:
            path_to_config (pathlib.Path): Path to configuration.
        """
        self.path_to_config = path_to_config
        self._validate_config_content()
        self.config = self._extract_config_content()

        self._seed_urls = self.config.seed_urls
        self._num_articles = self.config.total_articles
        self._headers = self.config.headers
        self._encoding = self.config.encoding
        self._timeout = self.config.timeout
        self._should_verify_certificate = self.config.should_verify_certificate
        self._headless_mode = self.config.headless_mode

    def _extract_config_content(self) -> ConfigDTO:
        """
        Get config values.

        Returns:
            ConfigDTO: Config values
        """
        with open(self.path_to_config, 'r', encoding='utf-8') as file:
            config = json.load(file)
        return ConfigDTO(
            seed_urls=config["seed_urls"],
            total_articles_to_find_and_parse=config["total_articles_to_find_and_parse"],
            headers=config["headers"],
            encoding=config["encoding"],
            timeout=config["timeout"],
            should_verify_certificate=config["should_verify_certificate"],
            headless_mode=config["headless_mode"]
        )

    def _validate_config_content(self) -> None:
        """
        Ensure configuration parameters are not corrupt.
        """
        with open(self.path_to_config, 'r', encoding='utf-8') as file:
            conf = json.load(file)

        if not (isinstance(conf['seed_urls'], list)
                and all(re.match(r"https://", seed_url)
                        for seed_url in conf['seed_urls']
                        )
                ):
            raise IncorrectSeedURLError

        num = conf['total_articles_to_find_and_parse']
        if not isinstance(num, int) or num < 0 or isinstance(num, bool):
            raise IncorrectNumberOfArticlesError
        if num > 150 or num < 1:
            raise NumberOfArticlesOutOfRangeError

        if not isinstance(conf['headers'], dict):
            raise IncorrectHeadersError

        if not isinstance(conf['encoding'], str):
            raise IncorrectEncodingError

        if not isinstance(conf['should_verify_certificate'], bool) \
                or not isinstance(conf['headless_mode'], bool):
            raise IncorrectVerifyError

        if not isinstance(conf['timeout'], int) \
                or conf['timeout'] >= 60 or conf['timeout'] <= 0:
            raise IncorrectTimeoutError

    def get_seed_urls(self) -> list[str]:
        """
        Retrieve seed urls.

        Returns:
            list[str]: Seed urls
        """
        return self._seed_urls

    def get_num_articles(self) -> int:
        """
        Retrieve total number of articles to scrape.

        Returns:
            int: Total number of articles to scrape
        """
        return self._num_articles

    def get_headers(self) -> dict[str, str]:
        """
        Retrieve headers to use during requesting.

        Returns:
            dict[str, str]: Headers
        """
        return self._headers

    def get_encoding(self) -> str:
        """
        Retrieve encoding to use during parsing.

        Returns:
            str: Encoding
        """
        return self._encoding

    def get_timeout(self) -> int:
        """
        Retrieve number of seconds to wait for response.

        Returns:
            int: Number of seconds to wait for response
        """
        return self._timeout

    def get_verify_certificate(self) -> bool:
        """
        Retrieve whether to verify certificate.

        Returns:
            bool: Whether to verify certificate or not
        """
        return self._should_verify_certificate

    def get_headless_mode(self) -> bool:
        """
        Retrieve whether to use headless mode.

        Returns:
            bool: Whether to use headless mode or not
        """
        return self._headless_mode


def make_request(url: str, config: Config) -> requests.models.Response:
    """
    Deliver a response from a request with given configuration.

    Args:
        url (str): Site url
        config (Config): Configuration

    Returns:
        requests.models.Response: A response from a request
    """
    sleep(config.get_timeout())

    return requests.get(
        url=url,
        timeout=config.get_timeout(),
        headers=config.get_headers(),
        verify=config.get_verify_certificate()
    )


class Crawler:
    """
    Crawler implementation.
    """

    url_pattern: Union[Pattern, str]

    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the Crawler class.

        Args:
            config (Config): Configuration
        """
        self.config = config
        self.urls = []
        self.url_pattern = self.config.get_seed_urls()[0].split('?')[0]

    def _extract_url(self, article_bs: BeautifulSoup) -> str:
        """
        Find and retrieve url from HTML.

        Args:
            article_bs (bs4.BeautifulSoup): BeautifulSoup instance

        Returns:
            str: Url from HTML
        """
        url = ''
        links = article_bs.findAll('a', hreflang='ru')
        for link in links:
            if 'Подробнее' in link.stripped_strings:
                url = link.get('href')
                if url not in self.urls:
                    break
        url = self.url_pattern + url[len('/news')::]
        return url

    def find_articles(self) -> None:
        """
        Find articles.
        """
        seed_urls = self.get_search_urls()

        for seed_url in seed_urls:
            response = make_request(seed_url, self.config)
            if not response.ok:
                continue

            article_bs = BeautifulSoup(response.text, "html.parser")
            urls = [self._extract_url(article_bs)
                             for i in range(10)]
            self.urls.extend(urls)

    def get_search_urls(self) -> list:
        """
        Get seed_urls param.

        Returns:
            list: seed_urls param
        """
        return self.config.get_seed_urls()


# 10
# 4, 6, 8, 10
class CrawlerRecursive(Crawler):
    """
    Recursive Crawler is a child of Crawler class.
    """
    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.inforced_stop = False
        self.start_url = self.config.get_seed_urls()[0][:-1]  # without num of ?page=0

    def find_articles(self) -> None:
        last_page = 0

        response = make_request(self.start_url, self.config)
        if response.ok:
            article_bs = BeautifulSoup(response.text, "html.parser")
            last_page = int(article_bs.find(class_='pager__item pager__item--last')
                                      .find('a')['href'])

        seed_urls = [f"{self.start_url}{str(num)}"
                     for num in range(0, last_page)]

        for seed_url in seed_urls:
            response = make_request(seed_url, self.config)
            if not response.ok:
                continue

            article_bs = BeautifulSoup(response.text, "html.parser")
            urls = [self._extract_url(article_bs)
                    for i in range(10)]
            self.urls.extend(urls)


class HTMLParser:
    """
    HTMLParser implementation.
    """

    def __init__(self, full_url: str, article_id: int, config: Config) -> None:
        """
        Initialize an instance of the HTMLParser class.

        Args:
            full_url (str): Site url
            article_id (int): Article id
            config (Config): Configuration
        """
        self.full_url = full_url
        self.article_id = article_id
        self.config = config
        self.article = Article(self.full_url, self.article_id)

    def _fill_article_with_text(self, article_soup: BeautifulSoup) -> None:
        """
        Find text of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        headline = article_soup.find(itemprop="headline")
        raw_text = f'{headline.string}'

        text_blocks = article_soup.findAll('p')
        for text_block in text_blocks:
            if not text_block.string:
                continue
            raw_text += f'\n{text_block.string}'

        self.article.text = raw_text

    def _fill_article_with_meta_information(self, article_soup: BeautifulSoup) -> None:
        """
        Find meta information of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        self.article.title = article_soup.find(itemprop="headline").string

        date = article_soup.find(itemprop="datePublished")['datetime']
        self.article.date = self.unify_date_format(date)

        author = article_soup.findAll('strong')[1].string
        if author:
            self.article.author = [author]
        else:
            self.article.author = ['NOT FOUND']

        topic_fields = article_soup.findAll(class_="field field--name-field-tegi " +
                                                   "field--type-entity-reference " +
                                                   "field--label-hidden field__items")
        topics = topic_fields[0].findAll('a')
        self.article.topics = [topic.string for topic in topics]

    def unify_date_format(self, date_str: str) -> datetime.datetime:
        """
        Unify date format.

        Args:
            date_str (str): Date in text format

        Returns:
            datetime.datetime: Datetime object
        """
        return datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

    def parse(self) -> Union[Article, bool, list]:
        """
        Parse each article.

        Returns:
            Union[Article, bool, list]: Article instance
        """
        response = make_request(self.full_url, self.config)
        if response.ok:
            article_bs = BeautifulSoup(response.text, 'lxml')
            self._fill_article_with_text(article_bs)
            self._fill_article_with_meta_information(article_bs)

        return self.article


def prepare_environment(base_path: Union[pathlib.Path, str]) -> None:
    """
    Create ASSETS_PATH folder if no created and remove existing folder.

    Args:
        base_path (Union[pathlib.Path, str]): Path where articles stores
    """
    if not pathlib.Path.is_dir(base_path):
        base_path.mkdir(parents=True, exist_ok=True)

    for file in base_path.iterdir():
        file.unlink(missing_ok=True)


def main() -> None:
    """
    Entrypoint for scrapper module.
    """
    configuration = Config(path_to_config=constants.CRAWLER_CONFIG_PATH)

    prepare_environment(base_path=constants.ASSETS_PATH)

    crawler = Crawler(config=configuration)
    crawler.find_articles()

    for index, url in enumerate(crawler.urls):
        parser = HTMLParser(full_url=url, article_id=index + 1, config=configuration)
        article = parser.parse()
        to_raw(article)
        to_meta(article)
    print("It's done!")


if __name__ == "__main__":
    main()