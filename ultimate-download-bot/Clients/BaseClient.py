__author__ = 'Prudhvi PLN'

import json
import requests
from bs4 import BeautifulSoup as BS
from requests.adapters import HTTPAdapter
from subprocess import Popen, PIPE
from urllib3.util.retry import Retry
# import cloudscraper as cs


class BaseClient():
    def __init__(self, session=None):
        # create a requests session and use across to re-use cookies
        self.req_session = session if session else requests.Session()
        # add retries with backoff
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        self.req_session.mount('http://', adapter)
        self.req_session.mount('https://', adapter)
        # disable insecure warnings
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        # self.req_session = session if session else cs.create_scraper()
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Accept-Encoding": "*",
            "Connection": "keep-alive"
        }
        self.udb_episode_dict = {}   # dict containing all details of epsiodes
        # list of invalid characters not allowed in windows file system
        self.invalid_chars = ['/', '\\', '"', ':', '?', '|', '<', '>', '*']

    def _get_bsoup(self, search_url, custom_header={}):
        '''
        return html parsed soup
        '''
        header = self.header
        header.update(custom_header)
        html_content = self.req_session.get(search_url, headers=header).text

        return BS(html_content, 'html.parser')
    
    def _update_udb_dict(self, parent_key, child_dict):
        if parent_key in self.udb_episode_dict:
            self.udb_episode_dict[parent_key].update(child_dict)
        else:
            self.udb_episode_dict[parent_key] = child_dict

    def _get_udb_dict(self):
        return self.udb_episode_dict

    def _send_request(self, url, referer=None, decode_json=True):
        '''
        call response session and return response
        '''
        # print(f'{self.req_session}: {url}')
        header = self.header
        if referer: header.update({'referer': referer})
        response = self.req_session.get(url, headers=header, verify=False)
        # print(response)
        if response.status_code == 200:
            if not decode_json:
                return response.text
            data = json.loads(response.text)
            if data['total'] > 0:
                return data['data']
        else:
            print(f'Failed with response code: {response.status_code}')

    def _exec_cmd(self, cmd):
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        # print stdout to console
        msg = proc.communicate()[0].decode("utf-8")
        std_err = proc.communicate()[1].decode("utf-8")
        rc = proc.returncode
        if rc != 0:
            raise Exception(f"Error occured: {std_err}")
        return msg

    def _windows_safe_string(self, word):
        for i in self.invalid_chars:
            word = word.replace(i, '')

        return word
