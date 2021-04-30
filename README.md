# Flex.Bot
### Музыкальный бот для дискорда
  
_Данный проект был реализован в рамках практической работы_

## Linux setup
```rest
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install python3.7
sudo apt install python3-pip
sudo apt install python3-venv
sudo apt install libopus0
sudo apt install ffmpeg
sudo apt install git
python3 -m venv env
source env/bin/activate
git clone https://github.com/gitSunic/flex-bot.git
cd flex-bot
pip3 install -r req.txt
sudo nano cfg.py
python3 main.py
```
cfg.py
```text
discord_token = '<discord_api_token>'
youtube_token = ['<youtube_token_1>',
                 '<youtube_token_2>',
                 '...',
                 '<youtube_token_n>']
genius_token = '<genius_api_token>'
imgbb_token = '<imgbb_api_token>'
version = '1.0'
me = <developer_discord_id>
```
