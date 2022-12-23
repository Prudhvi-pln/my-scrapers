import requests
from bs4 import BeautifulSoup as BS
# from idm import IDMan
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


base_url = 'https://dramacool.sr/'

# get drama name as user input
keyword = input("Enter Drama name: ")
# mask search keyword
search_key = keyword.replace(' ', '+')
search_url = base_url + 'search?type=drama&keyword=' + search_key

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
    ep_start, ep_end = map(int, range.split('-'))
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
    print("\nDownloading episodes...")

    # driver define and lunch
    driver = webdriver.Chrome()
    driver.maximize_window()

    # IDM downloader
    # downloader = IDMan()

    for ep, link in target.items():
        print(f"Downloading episode-{ep} from url: {link}...")
        driver.get(link)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, f'//*[@id="content-download"]/div[1]/div[contains(. ,"{resolution}P")]'))).click()
        # downloader.download(url, r"c:\DOWNLOADS", output=None, referrer=None, cookie=None, postData=None, user=None, password=None, confirm = False, lflag = None, clip=False)

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
