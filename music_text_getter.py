import re

from bs4 import BeautifulSoup, Tag
from ruamel.yaml.scalarstring import PreservedScalarString as Pss

from request_base import BaseRequest
from utils import log_it


class MusicTextGetter(BaseRequest):

    def __init__(self, url="", query_str="", album_title=""):
        self._album_title = self._url = self._query_str = ""

        self.data = ""
        self.url = url if url else "https://jazzforum.com.pl/main/cd/"
        self.album_title = album_title
        self.search = self.resolve_search(query_str if query_str else self.album_title)

        super().__init__("", "")
        self.req_headers = {'Content-Type': 'application/json'}

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, in_url):
        self._url = in_url

    @property
    def album_title(self):
        return self._album_title

    @album_title.setter
    def album_title(self, in_title):
        self._album_title = in_title

    @property
    def search(self):
        return self._query

    @search.setter
    def search(self, in_query):
        self._query = in_query

    @staticmethod
    def resolve_search(in_query_str=''):
        return re.sub(r' +', '-', in_query_str)

    def add_paragraph(self, in_obj, out_para):
        if not isinstance(in_obj, Tag):
            return out_para

        if isinstance(in_obj.next, str) and str(in_obj.text) not in "".join(out_para):
            out_para.append(str(in_obj.text or in_obj))
        else:
            out_para = self.add_paragraph(in_obj.next, out_para)

        return out_para

    def find_paragraphs(self, in_tags, out_paras):
        for tag in in_tags:
            out_paras = self.add_paragraph(tag, out_paras)

        return out_paras

    def get_text_data(self, as_html_str=False):
        page_url = self.url + self.search
        response = self._submit_request('GET', page_url, '')

        if response.status_code == 200:
            if as_html_str:
                return response.content.decode()

            bsoup = BeautifulSoup(response.content.decode(), "html.parser")

            news_right = bsoup.find("div", attrs={'class': "news_glowny_prawy"})
            first_p = news_right.find_all("p", recursive=True)
            all_p = list()
            all_p = self.find_paragraphs(first_p, all_p)
            out_text = []

            for p_text in all_p:
                p_text = re.sub(r'[ \n]+', ' ', p_text)
                if p_text in out_text:
                    continue

                out_text.append(p_text)

            return Pss("\n\n".join(out_text))

        log_it('error', __name__, "Failed to get page content from {}.".format(self.url))
        log_it('error', __name__,
               "Get content response:\n{}: {}\n".format(str(response.status_code), response.reason))

        return ""
