import configparser
import os

class Config:
    def __init__(self, filepath='config.ini'):
        self.config = configparser.ConfigParser()
        if not os.path.exists(filepath):
            # Create default config if not exists
            self.config['Telegram'] = {
                'api_token': '',
                'admin_chat_id': '',
                'receiver_chat_id': '',
                'proxy_url': ''
            }
            self.config['App'] = {
                'temp_dir': './temp'
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                self.config.write(f)

        self.config.read(filepath, encoding='utf-8')

    def _parse_id(self, key):
        val = self.config.get('Telegram', key, fallback='')
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    @property
    def api_token(self):
        return self.config.get('Telegram', 'api_token', fallback='')

    @property
    def admin_chat_id(self):
        return self._parse_id('admin_chat_id')

    @property
    def receiver_chat_id(self):
        return self._parse_id('receiver_chat_id')

    @property
    def proxy_url(self):
        return self.config.get('Telegram', 'proxy_url', fallback='')

    @property
    def temp_dir(self):
        return self.config.get('App', 'temp_dir', fallback='./temp')

config = Config('config.ini')
