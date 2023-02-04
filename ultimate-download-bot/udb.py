__version__ = '2.1'
__author__ = 'Prudhvi PLN'

import os
import re
import yaml
import jsbeautifier as js
from concurrent.futures import ThreadPoolExecutor, as_completed

from Clients.AnimeClient import AnimeClient
from Utils.HLSDownloader import downloader

config_file = 'config_udb.yaml'
print_episode_list = True
# list of invalid characters not allowed in windows file system
invalid_chars = ['/', '\\', '"', ':', '?', '|', '<', '>', '*']


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
    # parse m3u8 link from raw response.
    # if below logic is still failing, then execute the javascript code from html response
    # use either selenium in headless or use online compiler api (ex: https://onecompiler.com/javascript)
    # print(text)
    _regex_extract = lambda rgx, txt, grp: re.search(rgx, txt).group(grp) if re.search(rgx, txt) else False
    js_code = _regex_extract(";eval\(.*\)", text, 0)
    if not js_code:
        raise Exception('m3u8 link extraction failed. js code not found')

    try:
        parsed_js_code = js.beautify(js_code.replace(';', '', 1))
    except Exception as e:
        raise Exception('m3u8 link extraction failed. Unable to execute js')

    parsed_link = _regex_extract('http.*.m3u8', parsed_js_code, 0)
    if not parsed_link:
        raise Exception('m3u8 link extraction failed. link not found')

    return parsed_link

def fetch_m3u8_links(ac, target_links, resolution, episode_prefix):

    has_key = lambda x, y: y in x.keys()

    for ep, link in target_links.items():
        print(f'Episode: {ep:02d}', end=' | ')
        res_dict = [ i.get(resolution) for i in link if has_key(i, resolution) ]
        if len(res_dict) == 0:
            print(f'Resolution [{resolution}] not found')
        else:
            try:
                ep_name = f'{episode_prefix} {ep} - {resolution}P.mp4'
                kwik_link = res_dict[0]['kwik']
                raw_content = ac.get_m3u8_content(kwik_link, ep)
                ep_link = parse_m3u8_link(raw_content)
                # add m3u8 & kwik links against episode
                ac._update_udb_dict(ep, {'episodeName': ep_name, 'kwikLink': kwik_link, 'm3u8Link': ep_link})
                print(f'Link found [{ep_link}]')
            except Exception as e:
                print(f'Failed to fetch link with error [{e}]')

    final_dict = { k:v for k,v in ac._get_udb_dict().items() if v.get('m3u8Link') is not None }
    # print(final_dict)

    return final_dict

def start_downloader(download_fn, out_dir, temp_dir, concurrency, links, max_parallel_downloads):

    print(f"\nDownloading episode(s) to {out_dir}...")

    # start downloads in parallel threads
    with ThreadPoolExecutor(max_workers=max_parallel_downloads, thread_name_prefix='udb-') as executor:
        results = [ executor.submit(download_fn, out_dir, temp_dir, concurrency, **val) for val in links.values() ]
        for result in as_completed(results):
            print(result.result())


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
        ep_range = input("\nEnter episodes to download (ex: 1-16) [default=ALL]: ") or "all"
        if str(ep_range).lower() == 'all':
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

        # set output names & make it windows safe
        anime_title = target_anime['title']
        episode_prefix = f"{anime_title} episode"
        for i in invalid_chars:
            anime_title = anime_title.replace(i, '')

        # get available resolutions from first item.
        # remaining will have same set of resolutions. if not, please swap it with hard-coded list
        valid_resolutions = [ next(iter(i)) for i in next(iter(target_ep_links.values())) ]
        # valid_resolutions = ['360','480','720','1080']

        # get valid resolution from user
        while True:
            resolution = input(f"\nEnter download resolution ({'|'.join(valid_resolutions)}) [default=720]: ") or "720"
            if resolution not in valid_resolutions:
                print(f'Invalid Resolution [{resolution}] entered! Please give a valid resolution!')
            else:
                break

        # get m3u8 link for the specified resolution
        print('\nFetching Episode links:')
        target_dl_links = fetch_m3u8_links(client, target_ep_links, resolution, episode_prefix)

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

            # invoke downloader using a threadpool
            start_downloader(downloader, target_dir, temp_download_dir, concurrency_per_file, target_dl_links, max_parallel_downloads)
        else:
            print("Download halted on user input")

    except KeyboardInterrupt as ki:
        print('User interrupted')
        exit(0)

    except Exception as e:
        print(f'Unknown error occured: {e}')
        exit(1)
