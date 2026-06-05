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

    def _parse_ids(self, key):
        val = self.config.get('Telegram', key, fallback='')
        if not val:
            return []
        ids = []
        for part in val.replace(',', ' ').split():
            try:
                ids.append(int(part))
            except (ValueError, TypeError):
                continue
        return ids

    @property
    def api_token(self):
        return self.config.get('Telegram', 'api_token', fallback='')

    @property
    def admin_chat_ids(self):
        return self._parse_ids('admin_chat_id')

    @property
    def receiver_chat_ids(self):
        return self._parse_ids('receiver_chat_id')

    @property
    def proxy_url(self):
        return self.config.get('Telegram', 'proxy_url', fallback='')

    @property
    def temp_dir(self):
        return self.config.get('App', 'temp_dir', fallback='./temp')

config = Config('config.ini')
