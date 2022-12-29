__version__ = '1.5'
__author__ = 'Prudhvi PLN'

import logging
import os
import requests
import speech_recognition as sr
import yaml
from bs4 import BeautifulSoup as BS
from idm import IDMan
from progressbar import ProgressBar
from pydub import AudioSegment
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from time import sleep
from urllib.parse import quote_plus, unquote
from urllib.request import urlretrieve, build_opener, install_opener

# config file
config_file = 'downloader_config.yaml'

# display progress bar
class ShowProgressBar():
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

# batch downloader
class BatchDownloader():
    def __init__(self, config_file, type):
        self.type = type
        self.filtered_episode_links = {}
        # idm agent & chrome driver
        self.idm = None
        self.driver = None
        # set header
        self.header = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        # load yaml config
        with open(config_file, "r") as stream:
            try:
                config = yaml.safe_load(stream)
                self.config = config[type]
            except yaml.YAMLError as exc:
                print(f"Error occured while reading yaml file: {exc}")
                exit(1)

        # logger to write download links to file
        logging.basicConfig(level=logging.INFO)
        logging.basicConfig(filename=config['download_links_file'], filemode='w', format='%(message)s', force=True)

    def print_and_log(self, message):
        print(message)
        logging.info(message)

    def init_webdriver(self):
        # define and launch driver
        options = Options()
        options.add_argument(f'user-agent={self.header["user-agent"]}')
        # options.add_argument('headless')
        # options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.driver = webdriver.Chrome(options=options)
        self.driver.maximize_window()

    def close_webdriver(self):
        self.driver.close()
        self.driver.quit()

    def init_idm(self):
        # create idm
        if self.config['downloader'] == 'idm':
            self.idm = IDMan()

    def get_bsoup(self, search_url, custom_header=None):
        header = self.header if custom_header is None else custom_header
        html_content = requests.get(search_url, headers=header).text

        return BS(html_content, 'html.parser')

    def audio2text(self, mp3Path):
        wavPath = mp3Path.replace('.mp3', '.wav')
        sound = AudioSegment.from_mp3(mp3Path)
        sound.export(wavPath, format="wav")
        # initialize the recognizer
        r = sr.Recognizer()
        # open the file
        with sr.AudioFile(wavPath) as source:
            # listen for the data (load audio to memory)
            audio_data = r.record(source)
            # recognize (convert from speech to text)
            text = r.recognize_google(audio_data)
            #print(f"Captcha text: {text}")

        # delete files after completed
        os.remove(wavPath)
        os.remove(mp3Path)

        return text

    def save_file(self, content, filename):
        with open(filename, "wb") as handle:
            for data in content.iter_content():
                handle.write(data)

    def search(self, keyword):
        # mask search keyword
        search_key = quote_plus(keyword)
        search_url = self.config['base_url'] + self.config['search_url'] + search_key
        soup = self.get_bsoup(search_url)
        # get matched items
        items = soup.select(self.config['search_element'])
        if len(items) == 0:
            print(f"No results found with key word: {keyword}")
            exit(0)

        return items

    def fetch_search_links(self, items):
        dict = {}
        count = 1
        for item in items:
            item_url = item.find('a')['href']
            item_url = self.config['base_url'] + item_url if item_url.startswith('/') else item_url
            dict.update({count: [item.find('a')['title'], item_url]})
            count += 1

        return dict

    def print_series_info(self, site, info):
        print("\nFetching details: ")
        print(f'Title: {site[0].upper()}')
        for detail in info:
            if (detail.find('span') is not None and \
                detail.find('span').text.strip() in ['Type:', 'Country:', 'Status:', 'Released:', 'Genre:']):
                if len(detail.find_all('a')) > 0:
                    print(detail.find('span').text.strip(), end=" ")
                    print(', '.join([ i.text.replace(', ','').strip() for i in detail.find_all('a') ]))
                else:
                    print(detail.text.replace('"','').strip())

    def print_drama_episodes_info(self, episode_list):
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

    def print_anime_episodes_info(self, episode_list):
        print("\nEpisodes summary till date:")
        # for anime, display only total episodes. lazy load episode urls later
        print("Total episodes: " + [ ele.text for ele in episode_list ][-1].split('-')[-1])

    def fetch_series_details(self, target):
        self.print_and_log("Navigating to url: " + target[1])
        soup = self.get_bsoup(target[1])
        info = soup.select(self.config['series_info_element'])
        # print details of drama
        self.print_series_info(target, info)
        # fetch episode list & print details
        self.episode_list = soup.select(self.config['episodes_element'])
        if self.type == 'anime':
            self.anime_id = soup.select('input#movie_id')[0]['value']
            self.print_anime_episodes_info(self.episode_list)
        elif self.type == 'drama':
            self.print_drama_episodes_info(self.episode_list)

    def get_download_urls(self, referer_link, ep_no):
        delayTime = 1
        filename = 'audio.mp3'
        self.driver.get(referer_link)
        urls = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, f'//*[@id="content-download"]/div[1]'))).find_elements('xpath','.//div/a')
        if len(urls) == 0:
            # start captcha solving
            print(f"Started solving captcha for episode-{ep_no}...", end=' ')
            outeriframe = self.driver.find_element(By.ID, 'content-download').find_element(By.TAG_NAME, 'iframe')
            outeriframe.click()

            allIframesLen = self.driver.find_elements(By.TAG_NAME, 'iframe')
            audioBtnFound = False
            audioBtnIndex = -1

            for index in range(len(allIframesLen)):
                self.driver.switch_to.default_content()
                iframe = self.driver.find_elements(By.TAG_NAME, 'iframe')[index]
                self.driver.switch_to.frame(iframe)
                self.driver.implicitly_wait(delayTime)
                try:
                    audioBtn = self.driver.find_element(By.ID, 'recaptcha-audio-button') or self.driver.find_element(By.ID, 'recaptcha-anchor')
                    audioBtn.click()
                    audioBtnFound = True
                    audioBtnIndex = index
                    break
                except Exception as e:
                    pass

            if audioBtnFound:
                try:
                    # sometimes you need to solve captcha multiple times. So, keep solving...
                    while True:
                        href = self.driver.find_element(By.ID, 'audio-source').get_attribute('src')
                        response = requests.get(href, stream=True)
                        self.save_file(response, filename)
                        response = self.audio2text(os.getcwd() + '/' + filename)

                        self.driver.switch_to.default_content()
                        iframe = self.driver.find_elements(By.TAG_NAME, 'iframe')[audioBtnIndex]
                        self.driver.switch_to.frame(iframe)

                        inputbtn = self.driver.find_element(By.ID, 'audio-response')
                        inputbtn.send_keys(response)
                        inputbtn.send_keys(Keys.ENTER)

                        sleep(delayTime)
                        errorMsg = self.driver.find_elements(By.CLASS_NAME, 'rc-audiochallenge-error-message')[0]

                        if errorMsg.text == "" or errorMsg.value_of_css_property('display') == 'none':
                            print("Captcha solved!!!")
                            break
                        
                except Exception as e:
                    print(e)
                    print('Caught. Need to change proxy now. Exiting code...')
                    exit(1)

            # submit captcha after solved
            self.driver.switch_to.default_content()
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//*[@id="btn-submit"]'))).click()
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//*[@id="content-download"]/div[1]/div[2]')))
            urls = self.driver.find_element(By.XPATH, f'//*[@id="content-download"]/div[1]').find_elements('xpath','.//div/a')

        return urls

    def filter_episode_links(self, ep_range):
        if ep_range == 'all':
            ep_start, ep_end = 1, len(self.episode_list)
        else:
            try:
                ep_start, ep_end = map(int, ep_range.split('-'))
            except ValueError as ve:
                ep_start = ep_end = int(ep_range)

        print("\nFetching links: ")

        if self.type == 'anime':
            # lazy load episode urls
            episodes_retrieve_url = self.config['episodes_retrieve_url'].format(ep_start=ep_start, ep_end=ep_end, id=self.anime_id)
            self.episode_list = self.get_bsoup(episodes_retrieve_url).select('ul a')

        # open web driver to avoid captcha detection
        self.init_webdriver()

        for episode in self.episode_list[::-1]:
            key = 'h3' if self.type == 'drama' else ('div', 'name')
            ep_no = int(episode.find(key).text.strip().split()[-1])
            if ep_no >= ep_start and ep_no <= ep_end:
                download_links = {}
                ep_link = self.config['base_url'] + episode['href'].strip() if episode['href'].strip().startswith('/') else episode['href']
                referer_link = self.get_bsoup(ep_link).select(self.config['download_link_element'])[0]['href']
                referer_link = 'https:' + referer_link if referer_link.startswith('/') else referer_link
                # add referrer link
                download_links['source'] = referer_link
                # get download links via web-driver becoz of recaptcha
                download_urls = self.get_download_urls(referer_link, ep_no)
                # get all download links
                for link in download_urls:
                    download_links[link.text.split()[1].replace('(','').strip()] = link.get_attribute('href')
                self.filtered_episode_links[ep_no] = download_links
                # print links
                self.print_and_log(f"Episode-{ep_no} links:")
                for link in download_links:
                    self.print_and_log(f"  {link}: {download_links[link]}")
                if len(download_links) <= 1:
                    self.print_and_log("  Failed to fetch download links")

        # close the web driver
        self.close_webdriver()

        return len(self.filtered_episode_links)

    def start_downloader(self, out_dir, resolution = '480'):
        # set & create out directory
        out_dir = self.config['download_dir'] + '\\' + out_dir
        if not os.path.exists(out_dir): os.makedirs(out_dir)
        print("\nDownloading episode(s)...")

        self.init_idm()

        for ep, link in self.filtered_episode_links.items():
            print(f"Downloading episode-{ep}...")
            out_file = unquote(link['source'].split('title=')[1]).replace('+', ' ') + ' - ' + resolution + '.mp4'
            if self.config['downloader'] == 'idm':
                self.idm.download(link[resolution], out_dir, output=out_file, referrer=link['source'], cookie=None, postData=None, user=None, password=None, confirm=False, lflag=None, clip=False)
                print(f"Download started in IDM. File will be saved as: {out_dir}\{out_file}")
            elif self.config['downloader'] == 'python':
                opener = build_opener()
                opener.addheaders = [('referer', link['source'])]
                install_opener(opener)
                urlretrieve(link[resolution], f'{out_dir}\{out_file}', ShowProgressBar())
                # response = requests.get(link[resolution], headers = {'referer': link['source']}, stream = True)
                # open(f'{out_dir}\{out_file}', 'wb').write(response.content)
                print(f"File saved as: {out_dir}\{out_file}")

# main function
if __name__ == '__main__':
    # get series type
    types = {1: 'anime', 2: 'drama'}
    try:
        type = int(input("\nSelect type of series: \n1. Anime\n2. Drama\nEnter your choice: "))
        if type not in types:
            raise Exception
    except Exception as e:
        print("Invalid input!")
        exit(1)
    # initialize BatchDownloader
    bd = BatchDownloader(config_file, types[type])

    # get search keyword from user input
    keyword = input("\nEnter series/movie name: ")
    # search with keyword
    items = bd.search(keyword)
    # fetch the search result urls
    search_results = bd.fetch_search_links(items)
    print("\nSearch Results:")
    for x,y in search_results.items():
        print(f"{x}: {y[0]}")

    # get user selection for the search results
    try:
        option = int(input("\nSelect one of the above: "))
    except Exception as e:
        print("Invalid input!")
        exit(1)
    if option < 1 or option > len(search_results.keys()):
        print("Invalid option!!!")
        exit(1)

    # print details of the series & get all episode links
    bd.fetch_series_details(search_results[option])

    # get user inputs
    ep_option = input("\nEnter episodes to download (ex: 1-16): ") or "all"

    # filter required episode links
    target_ep_cnt = bd.filter_episode_links(ep_option)

    proceed = input(f"\nProceed with downloading {target_ep_cnt} episodes (y|n)? ").lower()
    if proceed == 'y':
        resolution = input("\nEnter download resolution (360|480|720|1080) [default=480]: ") or "480"
        bd.start_downloader(search_results[option][0], resolution + 'P')
    else:
        print("Download halted on user input")
