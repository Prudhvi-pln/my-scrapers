# my-scrapers
`
contains collection of my web scrapers for various uses mostly entire series download automation ;)
`
## Pre-requisites
 - Python >3.8
 - Chrome
 - pip dependencies: `pip install -r requirements.txt`
 - SpeechRecognition requires ffmpeg to be installed. _Note: ffmpeg needs to be added to Environment variables > PATH_

## Drama Downloader
 - Script: `drama_downloader.py`
 - Version: `1.0`
 - Description: `bot to download a drama series`

## Batch Downloader
 - Script: `download_bot.py`
 - Configuration: `downloader_config.yaml`
 - Version: `2.0`
 - Description: `bot to download both anime & drama series/movie`

 ### Changelog
  - Version: `2.0`
    - Added multi-threading for parallel downloads
    - Added cache while retrieving download links
    - Bug fixes in captcha solver
    - Lot of optimizations under the hood
  - Version: `1.5`
    - major breakthrough in captcha :) Automated captcha solving using speech recognition module
  - Version: `1.1`
    - tried to fix captcha issues during bulk downloads
  - Version: `1.0`
    - optimized version of drama downloader