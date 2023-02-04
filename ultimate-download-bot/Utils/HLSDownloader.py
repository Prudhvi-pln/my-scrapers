__author__ = 'Prudhvi PLN'

import os
import re
import requests
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from subprocess import Popen, PIPE
from time import time

class HLSDownloader():
    # References: https://github.com/Oshan96/monkey-dl/blob/master/anime_downloader/util/hls_downloader.py
    # https://github.com/josephcappadona/m3u8downloader/blob/master/m3u8downloader/m3u8.py

    def __init__(self, out_dir, temp_dir, concurrency, referer_link, out_file, session=None):
        self.out_dir = out_dir
        self.temp_dir = f"{temp_dir}\\{out_file.replace('.mp4','')}" #create temp directory per episode
        self.concurrency = concurrency
        self.referer = referer_link
        self.out_file = out_file
        self.m3u8_file = f'{self.temp_dir}\\uwu.m3u8'
        # create a requests session and use across to re-use cookies
        self.req_session = session if session else requests.Session()
        self.req_session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Accept-Encoding": "*",
            "Connection": "keep-alive",
            "Referer": self.referer
        }

    def _get_stream_data(self, url, to_text=False):
        response = self.req_session.get(url)
        # print(response)
        if response.status_code == 200:
            return response.text if to_text else response.content
        else:
            print(f'Failed with response code: {response.status_code}')

    def _create_out_dirs(self):
        os.makedirs(self.out_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

    def _remove_out_dirs(self):
        shutil.rmtree(self.temp_dir)

    def _exec_cmd(self, cmd):
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        # print stdout to console
        msg = proc.communicate()[0].decode("utf-8")
        std_err = proc.communicate()[1].decode("utf-8")
        rc = proc.returncode
        if rc != 0:
            raise Exception(f"Error occured: {std_err}")
        return msg

    def _is_encrypted(self, m3u8_data):
        method = re.search('#EXT-X-KEY:METHOD=(.*),', m3u8_data)
        if method is None: return False
        if method.group(1) == "NONE": return False

        return True

    def _collect_uri_iv(self, m3u8_data):
        uri_iv = re.search('#EXT-X-KEY:METHOD=AES-128,URI="(.*)",IV=(.*)', m3u8_data)

        if uri_iv is None:
            uri_data = re.search('#EXT-X-KEY:METHOD=AES-128,URI="(.*)"', m3u8_data)
            return uri_data.group(1), None

        uri = uri_iv.group(1)
        iv = uri_iv.group(2)

        return uri, iv

    def _collect_ts_urls(self, m3u8_data):
        urls = [url.group(0) for url in re.finditer("https://(.*)\.ts(.*)", m3u8_data)]
        if len(urls) == 0:
            # Relative paths
            base_url = re.search("(.*)/\S+\.m3u8", self.episode.download_url).group(1)
            urls = [base_url + "/" + url.group(0) for url in re.finditer("(.*)\.ts(.*)", m3u8_data)]

        return urls

    def _download_segment(self, ts_url):
        try:
            segment_file_nm = ts_url.split('/')[-1]
            segment_file = f"{self.temp_dir}//{segment_file_nm}"

            if os.path.isfile(segment_file):
                return f'Segment file [{segment_file_nm}] already exists. Reusing.'

            with open(segment_file, "wb") as ts_file:
                ts_file.write(self._get_stream_data(ts_url))

            return f'Segment file [{segment_file_nm}] downloaded'

        except Exception as e:
            return f'ERROR: Unable to download segment [{segment_file_nm}] with error: {e}'

    def _download_segments(self, ts_urls):
        # print(f'[{self.out_file}] Downloading {len(ts_urls)} segments using {self.concurrency} workers...')
        reused_segments = 0
        failed_segments = 0
        # parallelize download of segments using a threadpool
        with ThreadPoolExecutor(max_workers=self.concurrency, thread_name_prefix='udb-m3u8-') as executor:
            results = [ executor.submit(self._download_segment, ts_url) for ts_url in ts_urls ]
            for result in as_completed(results):
                if 'ERROR' in result.result():
                    print(result.result())
                    failed_segments += 1
                elif 'Reusing' in result.result():
                    reused_segments += 1

        print(f'[{self.out_file}] Segments download status: Total: {len(ts_urls)} | Reused: {reused_segments} | Failed: {failed_segments}')
        if failed_segments > 0:
            raise Exception(f'Failed to download {failed_segments} / {len(ts_urls)} segments')

    def _rewrite_m3u8_file(self, m3u8_data):
        # regex safe temp dir path
        seg_temp_dir = self.temp_dir.replace('\\', '\\\\')
        # ffmpeg doesn't accept backward slash in key file
        key_temp_dir = self.temp_dir.replace('\\', '/')
        with open(self.m3u8_file, "w") as m3u8_f:
            m3u8_content = re.sub('URI=(.*)/', f'URI="{key_temp_dir}/', m3u8_data, count=1)
            m3u8_content = re.sub(r'https://(.*)/', f'{seg_temp_dir}\\\\', m3u8_content)
            m3u8_f.write(m3u8_content)

    def _convert_to_mp4(self):
        # print(f'Converting {self.out_file} to mp4')
        cmd = f'ffmpeg -loglevel warning -allowed_extensions ALL -i "{self.m3u8_file}" -c copy -bsf:a aac_adtstoasc "{self.out_dir}\\{self.out_file}"'
        self._exec_cmd(cmd)

    def m3u8_downloader(self, m3u8_link):
        # create output directory
        self._create_out_dirs()

        iv = None
        m3u8_data = self._get_stream_data(m3u8_link, True)

        is_encrypted = self._is_encrypted(m3u8_data)
        if is_encrypted:
            key_uri, iv = self._collect_uri_iv(m3u8_data)
            self._download_segment(key_uri)

        # did not run into HLS with IV during development, so skipping it
        if iv:
            raise Exception("Current code cannot decode IV links")

        ts_urls = self._collect_ts_urls(m3u8_data)
        self._download_segments(ts_urls)
        self._rewrite_m3u8_file(m3u8_data)
        self._convert_to_mp4()

        # remove temp dir once completed and dir is empty
        self._remove_out_dirs()

        return (0, None)


def downloader(out_dir, temp_dir, concurrency, **ep_details):
    m3u8_url = ep_details['m3u8Link']
    referer = ep_details['kwikLink']
    out_file = ep_details['episodeName']
    # create download client for the episode
    dlClient = HLSDownloader(out_dir, temp_dir, concurrency, referer, out_file)

    get_current_time = lambda fmt='%F %T': datetime.now().strftime(fmt)
    start = get_current_time()
    start_epoch = int(time())
    print(f'[{start}] Download started for {out_file}...')

    if os.path.isfile(f'{out_dir}\\{out_file}'):
        # skip file if already exists
        return f'[{start}] File already exists. Skipping {out_file}...'
    else:
        # cmd = f'downloadm3u8 -o "{self.out_dir}\\{out_file}" --tempdir "{self.temp_dir}" --concurrency {self.concurrency} {m3u8_url}'
        try:
            # main function where HLS download happens
            status, msg = dlClient.m3u8_downloader(m3u8_url)
        except Exception as e:
            status, msg = 1, str(e)

        # remove target dirs if no files are downloaded
        if len(os.listdir(temp_dir)) == 0: os.rmdir(temp_dir)
        if len(os.listdir(out_dir)) == 0: os.rmdir(out_dir)

        end = get_current_time()
        if status != 0:
            return f'[{end}] Download failed for {out_file}. {msg}'

        def pretty_time(sec):
            h, m, s = sec // 3600, sec % 3600 // 60, sec % 3600 % 60
            return '{:02d}h {:02d}m {:02d}s'.format(h,m,s) if h > 0 else '{:02d}m {:02d}s'.format(m,s)
        end_epoch = int(time())
        download_time = pretty_time(end_epoch-start_epoch)
        return f'[{end}] Download completed for {out_file} in {download_time}!'

# if __name__ == '__main__':
#     out_dir = r'C:\Users\HP\Downloads\Video\Gokushufudou Part 2 (2021)'
#     temp_dir = r'C:\Users\HP\Downloads\Video\Gokushufudou Part 2 (2021)\temp_dir'
#     concurrency = 4
#     url = 'https://eu-092.cache.nextcdn.org/stream/09/10/47c1fbad4e6ee390529f0f8bec3a2871e30c1522908ec4154e6071b88b0825a9/uwu.m3u8'
#     referer = 'https://kwik.cx/e/mIQCDxoHo2pA'
#     out_file = 'Gokushufudou Part 2 episode 6 - 360P.mp4'
#     print(downloader(out_dir, temp_dir, concurrency, url, referer, out_file))