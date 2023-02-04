__author__ = 'Prudhvi PLN'

import json
import requests
from urllib.parse import quote_plus

class AnimeClient():
    def __init__(self, config, session=None):
        # create a requests session and use across to re-use cookies
        self.req_session = session if session else requests.Session()
        self.base_url = config['base_url']
        self.search_url = self.base_url + config['search_url']
        self.episodes_list_url = self.base_url + config['episodes_list_url']
        self.download_link_url = self.base_url + config['download_link_url']
        self.episode_url = self.base_url + config['episode_url']
        self.anime_id = ''      # anime id. required to create referer link
        self.udb_episode_dict = {}   # dict containing all details of epsiodes

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
        response = self.req_session.get(url, headers={'referer': referer}) if referer else self.req_session.get(url)
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
        '''
        return json data containing kwik links for a episode
        '''
        response = self._send_request(self.download_link_url + ep_id, None, False)
        # print(response)

        return json.loads(response)['data']

    def search(self, keyword):
        '''
        search for anime based on a keyword
        '''
        # url decode the search word
        search_key = quote_plus(keyword)
        search_url = self.search_url + search_key

        return self._send_request(search_url)

    def fetch_episodes_list(self, session):
        '''
        fetch all available episodes list in the selected anime
        '''
        episodes_data = []
        self.anime_id = session
        list_episodes_url = self.episodes_list_url + session

        raw_data = json.loads(self._send_request(list_episodes_url, None, False))
        last_page = int(raw_data['last_page'])
        # add first page's episodes
        episodes_data = raw_data['data']
        # if last page is not 1, get episodes from all pages
        if last_page > 1:
            for pgno in range(2, last_page+1):
                episodes_data.extend(self._send_request(f'{list_episodes_url}&page={pgno}'))

        return episodes_data

    def fetch_episode_links(self, episodes, ep_start, ep_end):
        '''
        fetch only required episodes based on episode range provided
        '''
        download_links = {}
        for episode in episodes:
            if int(episode.get('episode')) >= ep_start and int(episode.get('episode')) <= ep_end:
                response = self._get_kwik_links(episode.get('session'))
                if response is not None:
                    # add episode uid to udb dict
                    self._update_udb_dict(episode.get('episode'), {'episodeId': episode.get('session')})
                    # filter out eng dub links
                    download_links[episode.get('episode')] = [ _res for _res in response for k in _res.values() if k.get('audio') != 'eng']

        return download_links

    def get_m3u8_content(self, kwik_link, ep_no):
        '''
        return response as text of kwik link
        '''
        ep_id = self.udb_episode_dict[ep_no]['episodeId']
        referer_link = self.episode_url.replace('_anime_id_', self.anime_id).replace('_episode_id_', ep_id)
        # add episode link to udb dict
        self._update_udb_dict(ep_no, {'episodeLink': referer_link})
        response = self._send_request(kwik_link, referer_link, False)

        return response

    def anime_search_results(self, items):
        '''
        pretty print anime results based on your search
        '''
        for idx, item in enumerate(items):
            info = f"{idx+1}: {item.get('title')} | {item.get('type')}\n   " + \
                   f"| Episodes: {item.get('episodes')} | Released: {item.get('year')}, {item.get('season')} " + \
                   f"| Status: {item.get('status')}"
            print(info)

    def anime_episode_results(self, items):
        '''
        pretty print episodes list from fetch_episodes_list
        '''
        cnt = show = len(items)
        if cnt > 30:
            show = int(input(f'Total {cnt} episodes found. Enter range to display [default=ALL]: ') or cnt)
            print(f'Showing top {show} episodes:')
        for item in items[:show]:
            print(f"Episode: {item.get('episode'):02d} | Audio: {item.get('audio')} | Duration: {item.get('duration')} | Release data: {item.get('created_at')}")

    def anime_episode_links(self, items):
        '''
        pretty print episode links from fetch_episode_links
        '''
        for item, details in items.items():
            info = f"Episode: {item:02d}"
            for _res in details:
                _reskey = next(iter(_res))
                filesize = _res[_reskey]['filesize'] / (1024**2)
                info += f' | {_reskey}P ({filesize:.2f} MB) [{_res[_reskey]["audio"]}]'
            print(info)
