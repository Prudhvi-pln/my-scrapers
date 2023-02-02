# UDB [Ultimate-Download-Bot]
`
Anime series downloader from https://animepahe.com/. Downloads the file using Http Live Streaming (HLS) as m3u8 and converts to mp4 using ffmpeg
`
## Pre-requisites
 - Python > 3.8
 - pip dependencies: `pip install -r requirements.txt`
   - Uses jsbeautifier to execute javascript for retrieving HLS
 - ffmpeg
   - Windows:
     - download ffmpeg from [here](https://ffmpeg.org/download.html)
     - add to Environment variables > PATH
   - Linux (Ubuntu):
     - sudo apt install -y ffmpeg

## Changelog
 - Version 2.0 [2023-02-02]
   - All new downloader. Custom implementation of m3u8 downloader and reliable m3u8 parser

 - Version 1.2 [2023-01-29]
   - Fix m3u8 link parser. Bug fixes

 - Version 1.1 [2023-01-28]
   - First version
   - Download multiple anime episodes in parallel from animepahe

## Developer Guide (for the future me)
### HLS
 - HLS means Http Live Streaming. In IDM, you can see the file ending as .ts
 - It will contain main file .m3u8 which contains details of the segment files and a key
 - Algorithm to download this file:
   - download all segments in .m3u8 & decrypt if required
   - combine the segments in same order as in m3u8
   - convert the combined file to mp4 using ffmpeg
 - Coding this algo is fun, but you are lazy, so you are using m3u8downloader pip package

### Process Flow
 - get search results from __search_url__ _(every anime has a uid)_
 - for anime selected from above, get the episodes list from __episodes_list_url__ _(every episode has a uid)_
 - for episodes selected from above, get the download links _(kwik links)_ from __download_link_url__ _(every Kwik download link has a uid)_
 - from above kwik links, get the m3u8 stream link _(requires __episode_url__ as referer)_
 - from above m3u8 links, download the stream data and convert to mp4 _(requires __kwik link__ as referer)_

### Function Flow
```
 > Initialize AnimeClient as AC > AC.search > AC.animesearchresults (pretty print)

 > AC.fetchepisodeslist (get list of episodes) > AC.animeepisoderesults (pretty print episodes)

 > get episodes required from user > AC.fetchepisodelinks (get kwik links for required episodes in jpn lang) > AC.animeepisodelinks (pretty print)

 > get required resolution from user > fetchm3u8links > AC.getm3u8content > parsem3u8link (extract m3u8 url by decoding javascript)

 > startdownloader (start download using ThreadPool) > m3u8downloader (start downloadm3u8 using subprocess) > Initialize HLSDownloader as HLS > HLS.downloader()
 ```
 - AnimeClient is specific to a website.
 - HLSDownloader is 90% universal. 10% depends on HLS. If a new technique comes up in HLS, this needs to be updated