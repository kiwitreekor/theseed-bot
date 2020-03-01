import requests, re, urllib.parse, json, os.path, time, logging
from bs4 import BeautifulSoup

# theseed v4.16

class TheSeedError(Exception):
    def __init__(self, code, msg = '', title = ''):
        self.code = code
        self.msg = msg
        self.page_title = title
    
    def get_raw_msg(self):
        soup = BeautifulSoup(self.msg, 'html.parser')
    
        msg = ''
        
        for string in soup.strings:
            msg += str(string)
        
        return msg
    
    def __repr__(self):
        if self.code:
            return '{} ({}) @{}'.format(self.code, self.get_raw_msg(), self.page_title)
        else:
            return '{} @{}'.format(self.get_raw_msg(), self.page_title)
    
    def __str__(self):
        return repr(self)

class TheSeedDocument():
    namespace = ''
    title = ''
    force_show_namespace = True
    
    def __init__(self, namespace, title, force_show_namespace = True):
        if not namespace or not title:
            raise TypeError()
        
        self.namespace = namespace
        self.title = title
        self.force_show_namespace = force_show_namespace
    
    def __repr__(self):
        return 'TheSeedDocument(' + str(self) + ')'
    
    def __str__(self):
        if self.force_show_namespace:
            return self.namespace + ':' + self.title
        else:
            return self.title

class TheSeed():
    rx_parse_content = re.compile(r'<script>window\.INITIAL_STATE=(\{.*?\})</script>')
    cookies = {}
    
    config = {'member': {'username': None, 'password': None, 'cookies': {}, 'recaptcha_public': ''}, 'general': {'edit_interval': 1000, 'access_interval': 0, 'log_path': './theseed.log'}}
    default_config_path = 'config.json'
    config_path = ''
    
    '''
    format of common response:
        "config"
            "hash"
            "wiki.recaptcha_public"
            "wiki.editagree_text"
            "wiki.front_page"
            "wiki.site_name"
            "wiki.copyright_url"
            "wiki.canonical_url"
            "wiki.copyright_text"
            "wiki.sitenotice"
        "localConfig"
        "page"
            "title"
            "viewName"
            "data"
                "error"
        "session"
            "member"
                "gravatar_url"
                "quick_block"
                "username"
            "ip"
            "identifier"
            "menus"
            "hash"
    '''
    
    def __init__(self, host, config_path = '', log_level = logging.INFO):
        self.host = host
        
        self.config_path = config_path
        self.load_config()
        
        self.logger = logging.getLogger(__name__)
        
        log_formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)s] >> %(message)s')
        
        log_file_handler = logging.FileHandler(self.config['general']['log_path'], encoding='utf-8')
        log_file_handler.setFormatter(log_formatter)
        log_file_handler.setLevel(level=log_level)
        
        log_stream_handler = logging.StreamHandler()
        log_stream_handler.setFormatter(log_formatter)
        log_stream_handler.setLevel(level=logging.DEBUG)
        
        self.logger.addHandler(log_file_handler)
        self.logger.addHandler(log_stream_handler)
        self.logger.setLevel(level=logging.DEBUG)
        
    # helper functions
    def url(self, url_ = '', parameter = {}):
        param = ''
        if len(parameter) > 0:
            param = '?' + urllib.parse.urlencode(parameter, encoding='UTF-8', doseq=True)
        
        return 'https://' + self.host + '/' + url_ + param
    
    def document_url(self, title, type = '', parameter = {}):
        return self.url(type + '/' + title, parameter)
    
    def wait(self, type):
        if type == 'access':
            time.sleep(self.config['general']['access_interval'] / 1000)
        elif type == 'edit':
            time.sleep(self.config['general']['edit_interval'] / 1000)
        
    def parse_error(self, content_json):
        err_inst = None
        
        if content_json['page']['viewName'] == 'error':
            err_inst = TheSeedError(None, content_json['page']['data']['content'])
        
        if 'error' in content_json['page']['data']:
            err = content_json['page']['data']['error']
            
            err_inst = TheSeedError(err['code'], err['msg'], content_json['page']['title'])
        
        if err_inst:
            self.logger.error(str(err_inst))
            raise err_inst
        
    def get(self, url):
        response = requests.get(url, cookies=self.cookies)
        
        self.wait('access')
        
        match = self.rx_parse_content.search(response.text)
        content = match[1]
        
        content_json = json.loads(content)
        
        self.config['member']['recaptcha_public'] = content_json['config']['wiki.recaptcha_public']
        
        with open('response.txt', mode='w') as f:
            json.dump(content_json, f, sort_keys=True, indent=4)
            
        self.parse_error(content_json)
        
        return (response, content_json)
        
    def post(self, url, parameter, multipart = False):
        if not multipart:
            response = requests.post(url, data=parameter, cookies=self.cookies, allow_redirects=False)
        else:
            response = requests.post(url, files=parameter, cookies=self.cookies, allow_redirects=False)
        self.wait('access')
        
        if response.status_code == 200:
            match = self.rx_parse_content.search(response.text)
            content = match[1]
            
            content_json = json.loads(content)
            
            with open('response.txt', mode='w') as f:
                json.dump(content_json, f, sort_keys=True, indent=4)
            
            self.parse_error(content_json)
        else:
            with open('response.txt', mode='wb') as f:
                f.write(response.text.encode('utf-8'))
        
        return (response, None)
    
    # handle configuration
    def load_config(self):
        if not self.config_path:
            self.config_path = self.default_config_path
            
        if not os.path.isfile(self.config_path):
            self.init_config(self.config_path)
            return
        
        with open(self.config_path, 'r') as config_file:
            self.config = json.load(config_file)
            
        self.cookies = self.config['member']['cookies']
    
    def init_config(self):
        with open(self.config_path, 'w') as config_file:
            json.dump(self.config, config_file, sort_keys=True, indent=4)
    
    def save_config(self):
        if not self.config_path:
            self.config_path = self.default_config_path

        with open(self.config_path, 'w') as config_file:
            json.dump(self.config, config_file, sort_keys=True, indent=4)
        
    # action functions
    def w(self, title, rev = -1):
        response = self.get(self.document_url(title, 'w'))
    
    def raw(self, title, rev = -1):
        response = self.get(self.document_url(title, 'raw'))
    
    def edit(self, title, callback, section = None, log = '', request = False):
        '''
        response:
            "page"
                "data"
                    "body"
                        "baserev"
                        "section"
                        "text"
                    "captcha"
                    "document"
                        "namespace"
                        "title"
                    "helptext"
                    "readonly"
                    "token"
        request:
            token
            identifier
            baserev
            text
            log
            agree
        '''
        param = {}
        if section != None and not request:
            param['section'] = section
        
        view_name = 'edit' if not request else 'new_edit_request'
            
        response, content_json = self.get(self.document_url(title, view_name, param))
        
        data = content_json['page']['data']
        
        token = data['token']
        rev = data['body']['baserev']
        text = data['body']['text']
        
        new_text = callback(title, text)
        
        if new_text == None:
            self.logger.info('Skip (edit, {})'.format(title))
            return
        
        id = content_json['session']['identifier']
        
        parameters = {'token': (None, token), 'identifier': (None, id), 'baserev': (None, rev), 'text': (None, new_text), 'log': (None, log), 'agree': (None, 'Y')}
        
        if section != None:
            parameters['section'] = (None, section)
        
        self.post(self.document_url(title, view_name), parameters, multipart=True)
        
        self.logger.info('Success ({}, {})'.format(view_name, title))
            
        with open('response.txt', mode='w') as f:
            json.dump(content_json, f, sort_keys=True, indent=4)
            
        self.wait('edit')
    
    def login(self):
        '''
        username
        password
        autologin
        
        honoka
        kotori
        umi
        '''
        
        id = self.config['member']['username']
        pw = self.config['member']['password']
        
        try:
            response, content_json = self.post(self.url('member/login'), {'username': id, 'password': pw, 'autologin': 'Y'})
        except TheSeedError as err:
            self.logger.error(err)
            
        else:
            self.logger.info('Success (login, {})'.format(id))
            
            # record cookies
            if 'honoka' in response.cookies:
                self.cookies['honoka'] = response.cookies['honoka']
                
            if 'kotori' in response.cookies:
                self.cookies['kotori'] = response.cookies['kotori']
                
            if 'umi' in response.cookies:
                self.cookies['umi'] = response.cookies['umi']
            
            self.config['member']['cookies'] = self.cookies
            
            self.config['member']['username'] = id
            self.config['member']['password'] = pw
    
    def logout(self):
        response, content_json = self.get(self.url('member/logout'))
        
        self.cookies = {}
        
        self.config['member']['cookies'] = {}
        
        self.logger.info('Success (logout)')
    
    def search(self, query, pages = [1]):
        '''
        response:
            "page"
                "data"
                    "body"
                    "page"
                    "pages" [int]
                    "query"
                    "search" []
                        "doc"
                            "forceShowNamespace" (optional)
                            "namespace"
                            "title"
                        "text"
                    "took"
                    "total"
                "meta"
                "title"
                "viewName"
        '''
        search = []
        
        for page in pages:
            response, content_json = self.get(self.url('Search', {'q': query, 'page': page}))
            
            search_json = content_json['page']['data']['search']
            
            for item in search_json:
                if 'forceShowNamespace' in item['doc']:
                    document = TheSeedDocument(item['doc']['namespace'], item['doc']['title'], item['doc']['forceShowNamespace'])
                else:
                    document = TheSeedDocument(item['doc']['namespace'], item['doc']['title'])
                
                search.append(document)
            self.logger.debug('Success (search, {} - page {})'.format(query, page))
        
        self.logger.info('Success (search, {})'.format(query))
        return search