@ECHO OFF
cls
set /p id="Enter Instagram Username: "
python instaloader.py --no-metadata-json --no-video-thumbnails --no-captions --no-compress-json profile %id%
move %id% C:\Users\%username%\Desktop
echo Download completed!
PAUSE


