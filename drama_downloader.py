__version__ = '1.0.0'
__author__ = 'Prudhvi Chelluri'

import requests
from bs4 import BeautifulSoup as BS
from idm import IDMan
from progressbar import ProgressBar
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import unquote
from urllib.request import urlretrieve, build_opener, install_opener

# basic config
downloader = 'idm'  # options: idm/browser/python
out_dir = 'C:\\Users\\HP\\Downloads\\Video'

base_url = 'https://dramacool.sr/'

# get drama name as user input
keyword = input("Enter Drama name: ")
# mask search keyword
search_key = keyword.replace(' ', '+')
search_url = base_url + 'search?type=drama&keyword=' + search_key

class showProgressBar():
    def __init__(self):
        self.pbar = None

    def __call__(self, block_num, block_size, total_size):
        if not self.pbar:
            self.pbar = ProgressBar(maxval=total_size)
            self.pbar.start()

        downloaded = block_num * block_size
        if downloaded < total_size:
            self.pbar.update(downloaded)
        else:
            self.pbar.finish()

# modular functions
def get_soup(search_url):
    header = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36",
    }
    html_content = requests.get(search_url, headers=header).text
    #print(html_content)
    return BS(html_content, 'html.parser')

def fetch_search_items(items):
    # print(items)
    dict = {}
    count = 1
    for item in items:
        dict.update({count: [item.find('a')['title'], item.find('a')['href']]})
        count += 1
    return dict

def print_drama_details(site, info):
    print("\nFetching details: ")
    print(f'Title: {site[0]}')
    for detail in info:
        if detail.find('span') is not None and detail.find('span').text in ['Country:', 'Status:', 'Released:', 'Genre:']:
            print(detail.find('span').text, end=" ")
            print(', '.join([ i.text.strip() for i in detail.find_all('a') ]))

def print_episode_details(episode_list):
    tot = len(episode_list)
    sub, raw = 0, 0
    for i in episode_list:
        if i.find('span', {'class': 'SUB'}): sub += 1
        elif i.find('span', {'class': 'RAW'}): raw += 1
    print("\nEpisodes summary till date:")
    print(f"Total episodes: {tot}")
    print(f"Raw episodes: {raw}")
    print(f"Subbed episodes: {sub}")
    print("\nRecent episode details:")
    print(f"Name: {episode_list[0].find('h3').text.strip()}")
    print(f"Type: {episode_list[0].find('span', {'class': 'type'}).text}")
    print(f"Last updated on: {episode_list[0].find('span', {'class': 'time'}).text}")

def fetch_episode_links(episode_list, range):
    try:
        ep_start, ep_end = map(int, range.split('-'))
    except ValueError as ve:
        ep_start = ep_end = int(range)
    print("\nFetching links: ")
    ep_target = {}
    for episode in episode_list[::-1]:
        ep_no = int(episode.find('h3').text.strip().split()[-1])
        if ep_no >= ep_start and ep_no <= ep_end:
            ep_link = get_soup(episode['href']).find('div', {'class': 'plugins2'}).find('ul').find('li', {'class': 'download'}).find('a')['href']
            ep_link = 'https:' + ep_link if ep_link.startswith('//') else ep_link
            ep_target.update({ep_no: ep_link})
            print(f"Episode-{ep_no}: {ep_link}")

    return ep_target

def start_downloader(target, resolution = '480'):
    print("\nDownloading episode(s)...")

    # driver define and lunch
    driver = webdriver.Chrome()
    driver.maximize_window()

    # IDM downloader
    if downloader == 'idm': idm = IDMan()

    for ep, link in target.items():
        print(f"Downloading episode-{ep}...")
        driver.get(link)
        download_link = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, f'//*[@id="content-download"]/div[1]/div[contains(. ,"{resolution}P")]')))
        download_url = download_link.find_element('xpath', './/a').get_attribute('href')
        out_file = unquote(link.split('title=')[1]).replace('+', ' ') + '.mp4'
        if downloader == 'idm':
            idm.download(download_url, out_dir, output=out_file, referrer=link, cookie=None, postData=None, user=None, password=None, confirm=False, lflag=None, clip=False)
            print(f"Download started in IDM. File will be saved as: {out_dir}\{out_file}")
        elif downloader == 'browser':
            download_link.click()
            print(f"File will be saved to your browser download directory")
        elif downloader == 'python':
            opener = build_opener()
            opener.addheaders = [('referer', link)]
            install_opener(opener)
            urlretrieve(download_url, f'{out_dir}\{out_file}', showProgressBar())
            # response = requests.get(download_url, headers = {'referer': link}, stream = True)
            # open(f'{out_dir}\{out_file}', 'wb').write(response.content)
            print(f"File saved as: {out_dir}\{out_file}")


# main function
if __name__ == '__main__':
    soup = get_soup(search_url)
    # get matched items
    items = soup.find('ul', {'class': 'list-episode-item'}).find_all('li')

    if len(items) > 0:
        search_results = fetch_search_items(items)
        #print(search_results)
        print("\nSearch Results:")
        for x,y in search_results.items():
            print(f"{x}: {y[0]}")

        option = int(input("\nSelect one of the above: "))
        if option < 1 or option > len(search_results.keys()):
            print("Invalid option!!!")
        else:
            target = search_results[option]
            print("Navigating to url: " + target[1])
            soup = get_soup(target[1])
            info = soup.find('div', {'class': 'info'}).find_all('p')
            # print details of drama
            print_drama_details(target, info)
            # fetch episode list
            episode_list = soup.find('ul', {'class': 'all-episode'}).find_all('a')
            # print episode details
            print_episode_details(episode_list)
            # get user inputs
            resolution = input("\nEnter download resolution in Pixels (360|480|720|1080): ")
            ep_option = input("\nEnter episodes to download (ex: 1-16): ")
            # fetch episode links
            ep_target = fetch_episode_links(episode_list, ep_option)

            proceed = input(f"\nProceed with downloading {len(ep_target)} episodes (y|n)? ").lower()
            if proceed == 'y':
                start_downloader(ep_target, resolution)
            else:
                print("Download halted on user input")

    else:
        print(f"No drama found with key word: {keyword}")
