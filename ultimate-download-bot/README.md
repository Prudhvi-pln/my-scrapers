# UDB [Ultimate-Download-Bot]
`
Anime series downloader from https://animepahe.com/. Downloads the file using Http Live Streaming (HLS) as m3u8 and converts to mp4 using ffmpeg
`
## Pre-requisites
 - Python > 3.8
 - pip dependencies: `pip install -r requirements.txt`
   - Uses m3u8downloader from [here](https://pypi.org/project/m3u8downloader/)
 - ffmpeg
   - Windows:
     - download ffmpeg from [here](https://ffmpeg.org/download.html)
     - add to Environment variables > PATH
   - Linux (Ubuntu):
     - sudo apt install -y ffmpeg

## Changelog
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
```
 > Initialize AnimeClient as AC > AC.search > AC.animesearchresults (pretty print)

 > AC.fetchepisodeslist (get list of episodes) > AC.animeepisoderesults (pretty print episodes)

 > get episodes required from user > AC.fetchepisodelinks (get kwik links for required episodes in jpn lang) > AC.animeepisodelinks (pretty print)

 > get required resolution from user > fetchm3u8links > AC.getm3u8content > parsem3u8link (extract m3u8 url by decoding javascript)

 > Initialize HLSDownloader as HLS > HLS.startdownloader (start download using ThreadPool) > m3u8downloader (start downloadm3u8 using subprocess)
```