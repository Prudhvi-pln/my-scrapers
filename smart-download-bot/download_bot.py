__version__ = '2.4'
__author__ = 'Prudhvi PLN'

import json
import os
import pythoncom
import requests
import speech_recognition as sr
import yaml
from bs4 import BeautifulSoup as BS
from concurrent.futures import ThreadPoolExecutor
from idm import IDMan
from progressbar import ProgressBar
from pydub import AudioSegment
from random import randint
from selenium import webdriver
from selenium_stealth import stealth
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import NoSuchElementException
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
use_stealth = True
use_proxy = False
PROXY = '127.0.0.1:9150'
manual_solve_time = 60

invalid_chars = ['/', '\\', '"', ':', '?', '|', '<', '>', '*']

# countdown timer
def countdown(time_sec):
    while time_sec:
        time_sec -= 1
        mins, secs = divmod(time_sec, 60)
        timeformat = '{:02d}:{:02d}'.format(mins, secs)
        print(timeformat, end='\r')
        sleep(1)
    print()

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
        self.element_waitime = 30
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
                self.checkpoint_file = config['download_links_file']
                self.config = config[type]
                self.profile_details = config['chrome_profile']
            except yaml.YAMLError as exc:
                print(f"Error occured while reading yaml file: {exc}")
                exit(1)

        # load previous checkpoint for download links
        self.prev_checkpoint = {}
        if os.path.isfile(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as fin:
                self.prev_checkpoint = json.load(fin)

    def init_webdriver(self):
        # define and launch driver
        options = Options()
        # add user agent
        options.add_argument(f'user-agent={self.header["user-agent"]}')
        options.add_argument("--start-maximized")
        # options.add_argument('--headless')
        options.add_argument('--ignore-certificate-errors')
        if use_proxy:
            options.add_argument('--proxy-server=socks5://%s' % PROXY)
        # use a profile
        if self.profile_details['use_profile']:
            options.add_argument(f'--user-data-dir={self.profile_details["user_dir"]}')
            options.add_argument(f'--profile-directory={self.profile_details["profile_name"]}')
        else:
            options.add_argument("--incognito")
        # disable 'tests being run by controlled software' & disable debug logging
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        self.driver = webdriver.Chrome(options=options, service_log_path='./chrome_driver.log')
        if use_stealth:
            stealth(self.driver,
                user_agent=self.header["user-agent"],
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
        # self.get_captcha_score()

    def close_webdriver(self):
        # self.get_captcha_score()
        self.driver.close()
        self.driver.quit()

    def reopen_webdriver(self):
        self.close_webdriver()
        self.init_webdriver()

    def init_idm(self):
        # create idm
        if self.config['downloader'] == 'idm':
            self.idm = IDMan()

    def get_captcha_score(self, element_waittime=20):
        self.driver.get("https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php")
        WebDriverWait(self.driver, element_waittime).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "li.step1 button.go"))).click()
        resp = json.loads(WebDriverWait(self.driver, element_waittime).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "pre.response"))).get_attribute("innerHTML"))
        print(f'[ {resp["challenge_ts"]} ] Current Captcha score: {resp["score"]}')
        if len(resp["error-codes"]) > 0:
            print(f', Error codes: {resp["error-codes"]}')

        return resp["score"]

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
            return

        return items

    def fetch_search_links(self, items):
        dict = {}
        for idx, item in enumerate(items):
            item_url = item.find('a')['href']
            item_url = self.config['base_url'] + item_url if item_url.startswith('/') else item_url
            item_title = item.select(self.config['search_title'])[0].text.strip()
            dict[idx+1] = [item_title, item_url]

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
            else:
                print(detail.text.replace('"','').strip())

    def print_drama_episodes_info(self, episode_list):
        try:
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
        except Exception as e:
            pass

    def print_anime_episodes_info(self, episode_list):
        print("\nEpisodes summary till date:")
        # for anime, display only total episodes. lazy load episode urls later
        print("Total episodes: " + [ ele.text for ele in episode_list ][-1].split('-')[-1])

    def fetch_series_details(self, target):
        print("Navigating to url: " + target[1])
        soup = self.get_bsoup(target[1])
        if self.config['series_info_element'] != '':
            info = soup.select(self.config['series_info_element'])
            # print details of drama
            self.print_series_info(target, info)
        # fetch episode list & print details
        self.episode_list = soup.select(self.config['episodes_element'])
        # print(self.episode_list)
        if self.type == 'anime':
            self.anime_id = soup.select('input#movie_id')[0]['value']
            self.print_anime_episodes_info(self.episode_list)
        elif self.type == 'drama':
            self.print_drama_episodes_info(self.episode_list)

    def close_ads(self):
        if not self.profile_details['use_profile']:
            # disable full block ad if any.
            # Need not do this if you are using ad-block extension in your profile
            try:
                self.driver.execute_script('''
                var div_list = document.querySelectorAll('html > div');
                var div_array = [...div_list];
                div_array.forEach(div => { div.style.display = 'none';});
                ''')
                # document.querySelector('html > div').style.display = 'none';")
            except:
                pass

    def captcha_solver(self, retry):
        # reference: https://github.com/ohyicong/recaptcha_v2_solver/blob/master/recaptcha_solver.py

        def wait(delay=2):
            # increase sleep time as retry count increases
            sleep_time = randint(delay, delay*retry)
            self.driver.implicitly_wait(sleep_time)
            # Ads may popup during waiting.
            self.close_ads()

        print(f"  Started solving captcha...", end=' ')
        filename = 'audio.mp3'
        wait()

        def click_on_captcha():
            self.driver.find_element(By.ID, 'content-download').find_element(By.TAG_NAME, 'iframe').click()

        try:
            click_on_captcha()
        except Exception as e:
            # close ads and repeat
            self.close_ads()
            click_on_captcha()

        audioBtnFrame = None
        wait()
        self.driver.switch_to.default_content()
        iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')

        # find iframe for audio captcha (in case of multiple iframes)
        for index in range(len(iframes)):
            try:
                self.close_ads()
                self.driver.switch_to.default_content()
                iframe = self.driver.find_elements(By.TAG_NAME, 'iframe')[index]
                self.driver.switch_to.frame(iframe)
                wait(1)
                audioBtn = self.driver.find_element(By.ID, 'recaptcha-audio-button')
                audioBtn.click()
                audioBtnFrame = iframe
                break
            except Exception as e:
                pass

        if audioBtnFrame is None:
            print('Audio Captcha not found.')
            return 1

        # sometimes you need to solve captcha multiple times. So, keep solving...
        while True:
            try:
                wait(3)
                # check if captcha is solved
                self.driver.switch_to.default_content()
                WebDriverWait(self.driver, self.element_waitime).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="btn-submit"]'))).click()
                print("Captcha solved!!!")
                return 0
            except ElementClickInterceptedException as ecie:
                # if not solved, retry again
                wait()
                self.driver.switch_to.frame(audioBtnFrame)
                href = self.driver.find_element(By.ID, 'audio-source').get_attribute('src')
                response = requests.get(href, stream=True)
                self.save_file(response, filename)
                response = self.audio2text(os.getcwd() + '/' + filename)

                wait()
                inputbtn = self.driver.find_element(By.ID, 'audio-response')
                inputbtn.send_keys(response)
                inputbtn.send_keys(Keys.ENTER)
            except NoSuchElementException as nse:
                print("BLOCKED")
                return 1

    def get_download_urls_from_web(self, referer_link, retry):

        download_links = {}
        # add referrer link
        download_links['source'] = referer_link

        self.driver.get(referer_link)
        try:
            urls = WebDriverWait(self.driver, self.element_waitime).until(EC.presence_of_element_located((By.XPATH, f'//*[@id="content-download"]/div[1]'))).find_elements('xpath','.//div/a')
            if len(urls) == 0:
                # solve audio captcha
                status = self.captcha_solver(retry)
                self.close_ads()

                # wait for user to solve it manually if bot failed
                if status == 1:
                    print(f'      Waiting {manual_solve_time}s for user to solve the captcha manually...', end=' ')
                    try:
                        countdown(manual_solve_time)
                    except KeyboardInterrupt as ki:
                        print('Solved')
                    # switch to first tab. due to popup ads
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    WebDriverWait(self.driver, self.element_waitime).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="btn-submit"]'))).click()

                # submit captcha after solved
                WebDriverWait(self.driver, self.element_waitime).until(EC.presence_of_element_located((By.XPATH, '//*[@id="content-download"]/div[1]/div[2]')))
                self.close_ads()
                urls = self.driver.find_element(By.XPATH, f'//*[@id="content-download"]/div[1]').find_elements('xpath','.//div/a')

            # get all download links
            for link in urls:
                download_links[link.text.split()[1].replace('(','').strip()] = link.get_attribute('href')

        except Exception as e:
            print(e)

        return download_links

    def get_download_urls(self, referer_link, ep_no, retries = 1):
        download_links = {}
        print(f"Episode-{ep_no} links:")
        print(f"  source: {referer_link}")
        # load links from cache if present
        if ep_no in self.prev_checkpoint and referer_link == self.prev_checkpoint[ep_no]['source'] and len(self.prev_checkpoint[ep_no]) > 1:
            print("  Loaded from cache")
            download_links = self.prev_checkpoint[ep_no]
        # load from web using browser
        else:
            # retry logic if download links are not fetched
            for retry in range(1, retries+1):
                download_links = self.get_download_urls_from_web(referer_link, retry)
                if len(download_links) > 1:
                    break
                else:
                    print(f"  Failed to fetch download links. Retry count: {retry}")
                    if retry < retries: self.reopen_webdriver()

        # print links
        print(f"  Available Resolutions: {list(download_links.keys())[1:]}")
        # for link in download_links:
        #     if link != 'source':
        #         print(f"  {link}: {download_links[link]}")

        return download_links

    def filter_episode_links(self, ep_range):
        if ep_range == 'all':
            ep_start, ep_end = 1, len(self.episode_list)
        else:
            try:
                ep_start, ep_end = map(int, ep_range.split('-'))
            except ValueError as ve:
                ep_start = ep_end = int(ep_range)

        print("\nFetching links: ")

        # open web driver to avoid captcha detection
        self.init_webdriver()

        if self.type == 'anime':
            # lazy load episode urls
            episodes_retrieve_url = self.config['episodes_retrieve_url'].format(ep_start=ep_start, ep_end=ep_end, id=self.anime_id)
            self.episode_list = self.get_bsoup(episodes_retrieve_url).select('ul a')

        for episode in self.episode_list[::-1]:
            if self.config['episode_number'] != '':
                key = episode.find(self.config['episode_number'])
            else:
                key = episode
            ep_no = key.text.strip().split()[-1]
            # print(f'Ep no: {ep_no}')

            if int(ep_no) >= ep_start and int(ep_no) <= ep_end:

                ep_link = self.config['base_url'] + episode['href'].strip() if episode['href'].strip().startswith('/') else episode['href']
                referer_link = self.get_bsoup(ep_link).select(self.config['download_link_element'])[0]['href']
                referer_link = 'https:' + referer_link if referer_link.startswith('/') else referer_link

                # get download links via web-driver becoz of recaptcha
                self.filtered_episode_links[ep_no] = self.get_download_urls(referer_link, ep_no)

                if len(self.filtered_episode_links[ep_no]) > 1:
                    # write current download links to a file as a checkpoint
                    with open(self.checkpoint_file, 'w') as fout:
                        print(json.dumps(self.filtered_episode_links, indent=2), file=fout)

        # close the web driver
        self.close_webdriver()

        return len([ i for i in self.filtered_episode_links if len(self.filtered_episode_links[i]) > 1 ])

    def start_download(self, ep_no, out_dir, resolution):
        referer_link = self.filtered_episode_links[ep_no]['source']
        out_file = unquote(referer_link.split('title=')[1]).replace('+', ' ') + ' - ' + resolution + '.mp4'
        for i in invalid_chars:
            out_file = out_file.replace(i, '') 

        # skip download if required resolution is not found
        if resolution not in self.filtered_episode_links[ep_no]:
            return f'Specified resoltion ({resolution}) not found for {out_file}. Skipping...'

        download_link = self.filtered_episode_links[ep_no][resolution]

        # skip file if already exists
        if os.path.isfile(f'{out_dir}\\{out_file}'):
            return f'File already exists. Skipping {out_file}...'

        print(f"Downloading {out_file}...")
        try:
            pythoncom.CoInitialize()
            # download using idm
            if self.config['downloader'] == 'idm':
                self.idm.download(download_link, out_dir, output=out_file, referrer=referer_link, cookie=None, postData=None, user=None, password=None, confirm=False, lflag=None, clip=False)
                # polling to check if download is complete
                tot_wait_time = 0
                while not os.path.isfile(f'{out_dir}\{out_file}'):
                    #print(f"{out_file} not downloaded yet. Waiting...")
                    sleep(self.config['min_download_wait_time_in_sec'])
                    tot_wait_time += self.config['min_download_wait_time_in_sec']
                    if tot_wait_time > self.config['max_download_wait_time_in_sec']:
                        return f"Download for {out_file} is taking longer than {self.config['max_download_wait_time_in_sec']}. Proceeding with next file..."
            # download within code using urllib
            elif self.config['downloader'] == 'python':
                opener = build_opener()
                opener.addheaders = [('referer', referer_link)]
                install_opener(opener)
                urlretrieve(download_link, f'{out_dir}\{out_file}', ShowProgressBar())
                # response = requests.get(download_link, headers = {'referer': referer_link}, stream = True)
                # open(f'{out_dir}\{out_file}', 'wb').write(response.content)
        except Exception as e:
            return f"Download Failed for {out_file} with error: {e}"

        return f"Download Complete! File saved as: {out_dir}\{out_file}"

    def batch_downloader(self, out_dir, resolution):
        # set & create out directory
        for i in invalid_chars:
            out_dir = out_dir.replace(i, '') 
        out_dir = self.config['download_dir'] + '\\' + out_dir
        if not os.path.exists(out_dir): os.makedirs(out_dir)
        print("\nDownloading episode(s)...")

        self.init_idm()

        # start downloads in parallel threads
        with ThreadPoolExecutor(max_workers=self.config['max_parallel_downloads'], thread_name_prefix='download-bot-') as executor:
            results = [ executor.submit(self.start_download, ep, out_dir, resolution) for ep in self.filtered_episode_links if len(self.filtered_episode_links[ep]) > 1 ]
            for result in results:
                print(result.result())


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

    # search in an infinite loop till you get your series
    while True:
        # get search keyword from user input
        keyword = input("\nEnter series/movie name: ")
        # search with keyword
        items = bd.search(keyword)
        if items is None: continue
        # fetch the search result urls
        search_results = bd.fetch_search_links(items)
        print("\nSearch Results:")
        for x,y in search_results.items():
            print(f"{x}: {y[0]}")

        print("\nEnter 0 to search with different key word")

        # get user selection for the search results
        try:
            option = int(input("\nSelect one of the above: "))
        except Exception as e:
            print("Invalid input!")
            exit(1)
        if option < 0 or option > len(search_results.keys()):
            print("Invalid option!!!")
            exit(1)
        elif option == 0:
            continue
        else:
            break

    # print details of the series & get all episode links
    bd.fetch_series_details(search_results[option])

    # get user inputs
    ep_option = input("\nEnter episodes to download (ex: 1-16): ") or "all"

    # filter required episode links
    target_ep_cnt = bd.filter_episode_links(ep_option)

    if target_ep_cnt == 0:
        print("No episodes are available for download!")
        exit(0)

    proceed = input(f"\nProceed with downloading {target_ep_cnt} episodes (y|n)? ").lower()
    if proceed == 'y':
        resolution = input("\nEnter download resolution (360|480|720|1080) [default=480]: ") or "480"
        bd.batch_downloader(search_results[option][0], resolution + 'P')
    else:
        print("Download halted on user input")
