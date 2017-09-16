# tg-dump

Telegram chat history downloader.

It uses [pytg](https://github.com/luckydonald/pytg) to connect to
telegram-cli and download the chat history.

## Requirements

Install [telegram-cli](https://github.com/vysheng/tg)

## How to install

Clone the repo
```
git clone https://github.com/l4sh/tg-dump
cd tg-dump
```

Install and activate virtualenv. Not required but recommended
```
virtualenv .venv
source .venv/bin/activate
```

Install requirements
```
pip install -r requirements.txt
```

Done

### How to use

From the `tg-dump` dir run.

```python main.py```

It will run `telegram-cli` if it's not running and connect to it
on port `44134`.
