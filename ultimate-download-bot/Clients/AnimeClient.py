__author__ = 'Prudhvi PLN'

import json
import requests
from urllib.parse import quote_plus

class AnimeClient():
    def __init__(self, config):
        self.base_url = config['base_url']
        self.search_url = self.base_url + config['search_url']
        self.episodes_list_url = self.base_url + config['episodes_list_url']
        self.download_link_url = self.base_url + config['download_link_url']
        self.episode_url = self.base_url + config['episode_url']
        self.anime_id = ''      # anime id. required to create referer link
        self.episode_ids = {}   # dict containing episode ids. required to create referer link

    def _send_request(self, url, decode_json=True, referer=None):
        response = requests.get(url, headers={'referer': referer}) if referer else requests.get(url)
        # print(response)
        if response.status_code == 200:
            if not decode_json:
                return response.text
            data = json.loads(response.text)
            if data['total'] > 0:
                return data['data']
        else:
            print(f'Failed with response code: {response.status_code}')

    def _get_kwik_links(self, ep_id):
        response = self._send_request(self.download_link_url + ep_id, False)
        # print(response)

        return json.loads(response)['data']

    def search(self, keyword):
        # url decode the search word
        search_key = quote_plus(keyword)
        search_url = self.search_url + search_key

        return self._send_request(search_url)

    def fetch_episodes_list(self, session):
        self.anime_id = session
        list_episodes_url = self.episodes_list_url + session

        return self._send_request(list_episodes_url)

    def fetch_episode_links(self, episodes, ep_start, ep_end):
        download_links = {}
        for episode in episodes:
            if episode.get('episode') >= ep_start and episode.get('episode') <= ep_end:
                response = self._get_kwik_links(episode.get('session'))
                if response is not None:
                    self.episode_ids[episode.get('episode')] = episode.get('session')
                    # filter out eng dub links
                    download_links[episode.get('episode')] = [ _res for _res in response for k in _res.values() if k.get('audio') != 'eng']

        return download_links

    def get_m3u8_content(self, kwik_link, ep_no):
        ep_id = self.episode_ids[ep_no]
        referer_link = self.episode_url.replace('_anime_id_', 'self.anime_id').replace('_episode_id_', ep_id)
        response = self._send_request(kwik_link, False, referer_link)

        return response

    def anime_search_results(self, items):
        for idx, item in enumerate(items):
            info = f"{idx+1}: {item.get('title')} | {item.get('type')}\n   " + \
                   f"| Episodes: {item.get('episodes')} | Released: {item.get('year')}, {item.get('season')} " + \
                   f"| Status: {item.get('status')}"
            print(info)

    def anime_episode_results(self, items):
        for item in items:
            print(f"Episode: {item.get('episode')} | Audio: {item.get('audio')} | Duration: {item.get('duration')} | Release data: {item.get('created_at')}")

    def anime_episode_links(self, items):
        for item, details in items.items():
            info = f"Episode: {item} |"
            for _res in details:
                _reskey = next(iter(_res))
                filesize = _res[_reskey]['filesize'] / (1024**2)
                info += f' {_reskey} ({filesize:.2f} MB) [{_res[_reskey]["audio"]}] |'
            print(info)
