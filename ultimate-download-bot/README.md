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
 - Version 1.1 [2023-01-28]
   - First version
   - Download multiple anime episodes in parallel from animepahe
