"""
Module to retrieve album description from a known source.
"""
import re

from bs4 import BeautifulSoup, Tag
from ruamel.yaml.scalarstring import PreservedScalarString as Pss

from request_base import BaseRequest  # pylint: disable=import-error
from utils import log_it  # pylint: disable=import-error


class MusicTextGetter(BaseRequest):
    """
    Class to get music CD description.
    """

    def __init__(self, url="", query_str="", album_artist="", album_title=""):
        self._album_title = self._album_artist = self._url = self._query_str = ""

        self.data = ""
        self.url = url if url else "https://jazzforum.com.pl/main/cd/"
        self.album_artist = album_artist
        self.album_title = album_title
        self.search = self.resolve_search(query_str if query_str else self.album_title)

        super().__init__("", "")
        self.req_headers = {'Content-Type': 'application/json'}

    @property
    def url(self):  # pylint: disable=missing-function-docstring
        return self._url

    @url.setter
    def url(self, in_url):
        self._url = in_url

    @property
    def album_title(self):  # pylint: disable=missing-function-docstring
        return self._album_title

    @album_title.setter
    def album_title(self, in_title):
        self._album_title = in_title

    @property
    def album_artist(self):  # pylint: disable=missing-function-docstring
        return self._album_artist

    @album_artist.setter
    def album_artist(self, in_artist):
        self._album_artist = in_artist

    @property
    def search(self):  # pylint: disable=missing-function-docstring
        return self._query

    @search.setter
    def search(self, in_query):
        self._query = in_query

    @staticmethod
    def resolve_search(in_query_str=''):
        """
        Fix received query string by replacing spaces with dashes
        :param in_query_str: Query string to fix
        :return: Updated query string
        """
        return re.sub(r' +', '-', in_query_str)

    def add_paragraph(self, in_obj, out_para):
        """
        Add a paragraph to a list in out_para.
        :param in_obj: Object possibly containing a paragraph to add
        :param out_para: Output list of paragraphs
        :return: Modified output list of paragraphs
        """
        if not isinstance(in_obj, Tag):
            return out_para

        if isinstance(in_obj.next, str) and str(in_obj.text) not in "".join(out_para):
            out_para.append(str(in_obj.text or in_obj))
        else:
            out_para = self.add_paragraph(in_obj.next, out_para)

        return out_para

    def find_paragraphs(self, in_tags, out_paras):
        """
        Find paragraphs and add them ot an output list.
        :param in_tags: Tags (list of dict) in which to find paragraphs
        :param out_paras: Output lit of paragraphs
        :return: Modified list of output paragraphs
        """
        for tag in in_tags:
            out_paras = self.add_paragraph(tag, out_paras)

        return out_paras

    def validate_text_data(self, soup_to_check=None):
        """
        Check received beautiful soup object against the member variables title and artist for a match.
        :param soup_to_check: A BeautifulSoup object to verify
        :return: True indicates a match, False otherwise
        """
        if not soup_to_check:
            return True

        review_title_set = {x for x in set(re.split(r'\W', soup_to_check.find("h3").get_text().lower())) if x}
        review_artist_set = {y for y in set(re.split(r'\W', soup_to_check.find("h4").get_text().lower())) if y}

        if not set(re.split(r'\W', self.album_title.lower())).intersection(review_title_set) and \
                not set(re.split(r'\W', self.album_artist.lower())).intersection(review_artist_set):
            return False

        return True

    def get_text_data(self, as_html_str=False):
        """
        Method to retrieve text data from a know source (JazzForum)
        :param as_html_str: Flag indicating if HTML string is to be returned
        :return: A string containing the retrieved text on success, otherwise an empty string
        """
        page_url = self.url + self.search
        response = self._submit_request('GET', page_url, '')

        if response.status_code == 200:
            if as_html_str:
                return response.content.decode()

            bsoup = BeautifulSoup(response.content.decode(), "html.parser")

            news_right = bsoup.find("div", attrs={'class': "news_glowny_prawy"})

            if not self.validate_text_data(soup_to_check=news_right):
                return ""

            first_p = news_right.find_all("p", recursive=True)
            all_p = []
            all_p = self.find_paragraphs(first_p, all_p)
            out_text = []

            for p_text in all_p:
                p_text = re.sub(r'[ \n]+', ' ', p_text)
                if p_text in out_text:
                    continue

                out_text.append(p_text)

            return Pss("\n\n".join(out_text))

        log_it('error', __name__, f"Failed to get page content from {self.url}.")
        log_it('error', __name__,
               f"Get content response:\n{str(response.status_code)}: {response.reason}\n")

        return ""
