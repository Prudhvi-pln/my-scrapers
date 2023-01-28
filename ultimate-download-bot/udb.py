__version__ = '1.0'
__author__ = 'Prudhvi PLN'

import os
import yaml
from subprocess import Popen, PIPE
from Clients.AnimeClient import AnimeClient

config_file = 'config_udb.yaml'
print_episode_list = True
# list of invalid characters not allowed in windows file system
invalid_chars = ['/', '\\', '"', ':', '?', '|', '<', '>', '*']

def exec_cmd(cmd):
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
    # print stdout to console
    print(proc.communicate()[0].decode("utf-8"))
    std_err = proc.communicate()[1].decode("utf-8")
    rc = proc.returncode
    if rc != 0:
        print("Error occured: " + str(std_err))

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

def fetch_m3u8_links(target_links, resolution, episode_prefix):

    final_download_dict = {}
    has_key = lambda x, y: y in x.keys()

    for ep, link in target_links.items():
        print(f'Episode: {ep}', end=' ')
        res_dict = [ i.get(resolution) for i in link if has_key(i, resolution) ]
        if len(res_dict) == 0:
            print(f'Resolution [{resolution}] not found')
        else:
            try:
                ep_name = f'{episode_prefix} {ep} - {resolution}P.mp4'
                kwik_link = res_dict[0]['kwik']
                ep_link = client.get_m3u8_link(kwik_link, ep)
                final_download_dict[ep_name] = ep_link
                print(f'Link found [{ep_link}]')
            except Exception as e:
                print(f'Failed to fetch link with error [{e}]')

    return final_download_dict

def m3u8_downloader(url, out_file, temp_dir, concurrency):
    cmd = f'downloadm3u8 -o {out_file} --tempdir {temp_dir} --concurrency {concurrency} {url}'
    cmd = 'sleep 10;echo hi'
    exec_cmd(cmd)

def start_downloader(links, out_dir, temp_dir, concurrency):
    # create output directory
    # if not os.path.exists(out_dir): os.makedirs(out_dir)
    # if not os.path.exists(temp_dir): os.makedirs(temp_dir)

    print("\nDownloading episode(s)...")
    for out_file, link in links.items():
        # skip file if already exists
        if os.path.isfile(f'{out_dir}\\{out_file}'):
            print(f'File already exists. Skipping {out_file}...')
        else:
            m3u8_downloader(link, f'{out_dir}\\{out_file}', temp_dir, concurrency)
            print(f'{out_file} downloaded at {out_dir}\{out_file}')


if __name__ == '__main__':
    try:
        # load config from yaml to dict using yaml
        config = load_yaml(config_file)

        # create client
        client = AnimeClient(config['anime'])

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

        # output settings
        anime_title = target_anime['title']
        for i in invalid_chars:
            anime_title = anime_title.replace(i, '')
        target_dir = f"{config['download_dir']}\\{anime_title} ({target_anime['year']})"
        episode_prefix = f"{anime_title} episode"
        concurrency_per_file = config['concurrency_per_file']
        temp_download_dir = config['temp_download_dir']
        if temp_download_dir == 'auto':
            temp_download_dir = f'{target_dir}\\temp_dir'

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

        # get m3u8 link for the specified resolution
        resolution = input("\nEnter download resolution (360|480|720|1080) [default=720]: ") or "720"
        print('\nFetching Episode links')
        target_dl_links = fetch_m3u8_links(target_ep_links, resolution, episode_prefix)

        proceed = input(f"\nProceed with downloading {len(target_dl_links)} episodes (y|n)? ").lower()
        if proceed == 'y':
            start_downloader(target_dl_links, target_dir, temp_download_dir, concurrency_per_file)
        else:
            print("Download halted on user input")

    except KeyboardInterrupt as ki:
        print('User interrupted')
        exit(0)

    except Exception as e:
        print(f'Unknown error occured: {e}')
        exit(1)
