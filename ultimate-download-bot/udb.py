__version__ = '1.2'
__author__ = 'Prudhvi PLN'

import os
import re
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from subprocess import Popen, PIPE
from time import time
from Clients.AnimeClient import AnimeClient

config_file = 'config_udb.yaml'
print_episode_list = True
# list of invalid characters not allowed in windows file system
invalid_chars = ['/', '\\', '"', ':', '?', '|', '<', '>', '*']


class HLSDownloader():
    def __init__(self, out_dir, temp_dir, concurrency):
        self.out_dir = out_dir
        self.temp_dir = temp_dir
        self.concurrency = concurrency

    def create_out_dirs(self):
        if not os.path.exists(self.out_dir): os.makedirs(self.out_dir)
        if not os.path.exists(self.temp_dir): os.makedirs(self.temp_dir)

    def remove_out_dirs(self):
        if len(os.listdir(self.temp_dir)) == 0:
            os.rmdir(self.temp_dir)
        else:
            print('WARN: temp dir is not empty. temp dir is retained for resuming incomplete downloads.')

        if len(os.listdir(self.out_dir)) == 0: os.rmdir(self.out_dir)

    def exec_cmd(self, cmd):
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        # print stdout to console
        msg = proc.communicate()[0].decode("utf-8")
        std_err = proc.communicate()[1].decode("utf-8")
        rc = proc.returncode
        if rc != 0:
            msg = f"Error occured: {std_err}"
            return (1, msg)
        return (0, msg)

    def m3u8_downloader(self, url, out_file):
        get_current_time = lambda fmt='%F %T': datetime.now().strftime(fmt)

        start = get_current_time()
        start_epoch = int(time())
        print(f'[{start}] Download started for {out_file}...')

        if os.path.isfile(f'{self.out_dir}\\{out_file}'):
            # skip file if already exists
            return f'[{start}] File already exists. Skipping {out_file}...'
        else:
            # call downloadm3u8 via subprocess
            cmd = f'downloadm3u8 -o "{self.out_dir}\\{out_file}" --tempdir "{self.temp_dir}" --concurrency {self.concurrency} {url}'
            status, msg = self.exec_cmd(cmd)
            end = get_current_time()
            if status != 0:
                return f'[{end}] Download failed for {out_file}. {msg}'
            end_epoch = int(time())
            return f'[{end}] Download complete in {end_epoch-start_epoch}s! File saved as {self.out_dir}\{out_file}'

    def start_downloader(self, links, max_parallel_downloads):

        # create output directory
        self.create_out_dirs()
        print("\nDownloading episode(s)...")

        # start downloads in parallel threads
        with ThreadPoolExecutor(max_workers=max_parallel_downloads, thread_name_prefix='udb-') as executor:
            results = [ executor.submit(self.m3u8_downloader, link, out_file) for out_file, link in links.items() ]
            for result in as_completed(results):
                print(result.result())

        # remove temp dir once completed and dir is empty
        self.remove_out_dirs()


# load yaml config into dict
def load_yaml(config_file):
    if not os.path.isfile(config_file):
        print(f'Config file [{config_file}] not found')
        exit(1)

    with open(config_file, "r") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(f"Error occured while reading yaml file: {exc}")
            exit(1)

def parse_m3u8_link(text):
    # parse m3u8 link from raw response. normally, javascript should be executed for this
    # if below logic is still failing, then execute the javascript code from html response
    # use either selenium in headless or use online compiler api (ex: https://onecompiler.com/javascript)
    # print(text)
    get_match = lambda rgx, txt: re.search(rgx, txt).group(0) if re.search(rgx, txt) else False
    raw_link = get_match("m3u8.*https", text)
    if not raw_link:
        raise Exception('m3u8 link extraction failed')

    # print(raw_link)
    _r = raw_link.split('|')[::-1]
    parsed_link = f'{_r[0]}://{_r[1]}-{_r[2]}.' + '.'.join(_r[3:6]) + '/'

    # get url format for m3u8. it varies per request. set to default if not found
    link_fmt = get_match("://.*\';", text)
    idx_for_url = 6
    if not link_fmt:
        parsed_link += '/' + '/'.join(_r[idx_for_url:]) #set to default
    else:
        link_fmt = link_fmt.replace('://','').replace("';",'')
        # url can have some hard-coded values. if url format has any digits, use the same in parsed url
        for i in re.split('\.|/|-', link_fmt)[5:]:
            if re.match('^\d+$', i):
                parsed_link += f'/{i}'
            else:
                parsed_link += f'/{_r[idx_for_url]}'
                idx_for_url += 1

    return parsed_link.replace('/m3u8','.m3u8')

def fetch_m3u8_links(target_links, resolution, episode_prefix):

    final_download_dict = {}
    has_key = lambda x, y: y in x.keys()

    for ep, link in target_links.items():
        print(f'Episode: {ep}', end=' | ')
        res_dict = [ i.get(resolution) for i in link if has_key(i, resolution) ]
        if len(res_dict) == 0:
            print(f'Resolution [{resolution}] not found')
        else:
            try:
                ep_name = f'{episode_prefix} {ep} - {resolution}P.mp4'
                kwik_link = res_dict[0]['kwik']
                raw_content = client.get_m3u8_content(kwik_link, ep)
                ep_link = parse_m3u8_link(raw_content)
                final_download_dict[ep_name] = ep_link
                print(f'Link found [{ep_link}]')
            except Exception as e:
                print(f'Failed to fetch link with error [{e}]')

    return final_download_dict


if __name__ == '__main__':
    try:
        # load config from yaml to dict using yaml
        config = load_yaml(config_file)

        # create client
        client = AnimeClient(config['anime'])
        max_parallel_downloads = config['max_parallel_downloads']

        # search in an infinite loop till you get your series
        while True:
            # get search keyword from user input
            keyword = input("\nEnter series/movie name: ")
            # search with keyword
            search_results = client.search(keyword)

            if search_results is None:
                print('No matches found. Try with different keyword')
                continue

            # print search results
            print("\nSearch Results:")
            client.anime_search_results(search_results)

            print("\nEnter 0 to search with different key word")

            # get user selection for the search results
            try:
                option = int(input("\nSelect one of the above: "))
            except Exception as e:
                print("Invalid input!"); exit(1)

            if option < 0 or option > len(search_results):
                print("Invalid option!!!"); exit(1)
            elif option == 0:
                continue
            else:
                break

        target_anime = search_results[option-1]
        # fetch episode links
        episodes = client.fetch_episodes_list(target_anime.get('session'))
        if print_episode_list:
            print('\nAvailable Episodes Details:')
            client.anime_episode_results(episodes)

        # get user inputs
        ep_range = input("\nEnter episodes to download (ex: 1-16): ") or "all"
        if ep_range == 'all':
            ep_range = f"{episodes[0]['episode']}-{episodes[-1]['episode']}"

        try:
            ep_start, ep_end = map(int, ep_range.split('-'))
        except ValueError as ve:
            ep_start = ep_end = int(ep_range)

        # filter required episode links
        target_ep_links = client.fetch_episode_links(episodes, ep_start, ep_end)
        # print episode links
        print("\nTarget Episodes & Available Resolutions:")
        client.anime_episode_links(target_ep_links)

        if len(target_ep_links) == 0:
            print("No episodes are available for download!")
            exit(0)

        # set output names
        anime_title = target_anime['title']
        episode_prefix = f"{anime_title} episode"
        for i in invalid_chars:
            anime_title = anime_title.replace(i, '')

        # get m3u8 link for the specified resolution
        resolution = input("\nEnter download resolution (360|480|720|1080) [default=720]: ") or "720"
        print('\nFetching Episode links:')
        target_dl_links = fetch_m3u8_links(target_ep_links, resolution, episode_prefix)

        if len(target_dl_links) == 0:
            print('No episodes available to download! Exiting.')
            exit(0)

        proceed = input(f"\nProceed with downloading {len(target_dl_links)} episodes (y|n)? ").lower()
        if proceed == 'y':
            # output settings for m3u8
            target_dir = f"{config['download_dir']}\\{anime_title} ({target_anime['year']})"
            concurrency_per_file = config['concurrency_per_file']
            temp_download_dir = config['temp_download_dir']
            if temp_download_dir == 'auto':
                temp_download_dir = f'{target_dir}\\temp_dir'

            # download client
            dlClient = HLSDownloader(target_dir, temp_download_dir, concurrency_per_file)

            dlClient.start_downloader(target_dl_links, max_parallel_downloads)
        else:
            print("Download halted on user input")

    except KeyboardInterrupt as ki:
        print('User interrupted')
        exit(0)

    except Exception as e:
        print(f'Unknown error occured: {e}')
        exit(1)
