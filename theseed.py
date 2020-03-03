import requests, re, urllib.parse, json, os.path, time, logging, quickjs, zlib
from bs4 import BeautifulSoup

# theseed v4.16

class BaseError(Exception):
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
            return '{} {} @{}'.format(self.code, '({})'.format(self.get_raw_msg()) if self.msg else '', self.page_title)
        else:
            return '{} @{}'.format(self.get_raw_msg(), self.page_title)
    
    def __str__(self):
        return repr(self)

class Error(BaseError):
    pass

class StopSignal(BaseError):
    def __init__(self, parent):
        super().__init__('user-discuss-occurred')

        parent.save_config()

class URL():
    host = ''
    baseurl = '/'
    url = ''
    parameter = {}

    def __init__(self, host, baseurl, url, param = {}):
        self.host = host
        self.baseurl = baseurl
        self.url = url
        self.parameter = param
    
    def __str__(self):
        param = ''
        if len(self.parameter) > 0:
            param = '?' + urllib.parse.urlencode(self.parameter, encoding='UTF-8', doseq=True)
        
        return 'https://' + self.host + self.baseurl + self.url + param


class Document():
    namespace = ''
    title = ''
    force_show_namespace = True
    
    def __init__(self, data):
        if not 'title' in data or not 'namespace' in data:
            raise TypeError()
        
        self.namespace = data['namespace']
        self.title = data['title']

        if 'forceShowNamespace' in data:
            self.force_show_namespace = data['forceShowNamespace']
    
    def __repr__(self):
        return 'TheSeedDocument(' + str(self) + ')'
    
    def __str__(self):
        if self.force_show_namespace:
            return self.namespace + ':' + self.title
        else:
            return self.title

class TheSeed():
    rx_parse_content = re.compile(r'<script>window\.INITIAL_STATE=(\{.*?\})</script>')
    rx_parse_script_url = re.compile(r'<script src="/(skins/.*?/.*?\.js)" defer></script>')
    x_chika = ''
    cookies = {}
    
    config = {'member': {'username': None, 'password': None, 'cookies': {}}, 'general': {'edit_interval': 1000, 'access_interval': 500, 'log_path': './theseed.log', 'confirmed_user_discuss': int(time.time())}}
    default_config_path = 'config.json'
    config_path = ''

    wait_start = {}

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

        self.is_loaded = False
        
        log_formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)s] >> %(message)s')
        
        log_file_handler = logging.FileHandler(self.read_config('general.log_path'), encoding='utf-8')
        log_file_handler.setFormatter(log_formatter)
        log_file_handler.setLevel(level=log_level)
        
        log_stream_handler = logging.StreamHandler()
        log_stream_handler.setFormatter(log_formatter)
        log_stream_handler.setLevel(level=logging.DEBUG)
        
        self.logger.addHandler(log_file_handler)
        self.logger.addHandler(log_stream_handler)
        self.logger.setLevel(level=logging.DEBUG)

        self.state = {}

        with open('theseed_hash.js', mode='r') as f:
            theseed_hash_js = f.read()
            self.theseed_nonce_hash = quickjs.Function('u', theseed_hash_js)
        
    # helper functions
    def url(self, url_, parameter = {}, internal = False):
        return URL(self.host, '/internal/' if internal else '/', url_, parameter)
    
    def document_url(self, title, _type = '', parameter = {}, internal = False):
        return self.url(_type + '/' + urllib.parse.quote(title, encoding='UTF-8'), parameter, internal)
    
    def set_wait(self, _type):
        self.wait_start[_type] = time.time()

    def wait(self, _type):
        if _type == 'access':
            wait_time = self.read_config('general.access_interval')
        elif _type == 'edit':
            wait_time = self.read_config('general.edit_interval')
        
        time.sleep(max(self.wait_start[_type] + wait_time / 1000 - time.time(), 0))
        
        del self.wait_start[_type]
    
    def decode_internal(self, stream):
        n = 0
        i = 0
        e = 0
        s_array = [53, 152, 166, 1, 230, 68, 121, 84, 40, 38, 50, 3, 19, 41, 151, 74, 145, 238, 42, 202, 237, 59, 255, 31, 69, 56, 4, 198, 90, 60, 135, 249, 116, 101, 5, 87, 79, 193, 147, 48, 158, 47, 111, 44, 110, 13, 28, 223, 118, 75, 96, 61, 83, 164, 21, 169, 14, 94, 186, 99, 89, 233, 126, 100, 167, 73, 188, 235, 168, 0, 108, 189, 224, 17, 194, 173, 7, 138, 250, 66, 142, 182, 156, 102, 139, 70, 155, 175, 105, 144, 200, 209, 241, 12, 137, 52, 106, 180, 113, 23, 149, 172, 91, 36, 34, 179, 65, 120, 141, 227, 8, 72, 184, 114, 165, 98, 25, 64, 9, 93, 39, 207, 246, 177, 159, 143, 16, 26, 213, 251, 49, 134, 204, 226, 63, 244, 77, 78, 216, 81, 199, 45, 86, 136, 171, 236, 140, 43, 150, 190, 76, 6, 215, 55, 170, 11, 239, 33, 10, 232, 220, 107, 104, 217, 82, 27, 253, 231, 20, 129, 247, 95, 176, 208, 85, 195, 30, 109, 212, 196, 254, 157, 15, 154, 92, 119, 243, 218, 24, 29, 205, 192, 221, 228, 32, 54, 22, 214, 146, 128, 131, 203, 163, 185, 252, 153, 125, 183, 88, 197, 222, 178, 132, 124, 234, 57, 51, 115, 162, 103, 160, 80, 133, 97, 206, 127, 201, 2, 248, 18, 117, 46, 219, 191, 62, 174, 123, 71, 240, 161, 122, 229, 245, 67, 242, 35, 181, 225, 37, 210, 211, 112, 58, 187, 148, 130]
        
        for pos in range(len(stream)):
            n = (n + 1) & 0xFF
            i = (i + s_array[n]) & 0xFF
            e = s_array[n]
            s_array[n] = s_array[i]
            s_array[i] = e
            stream[pos] ^= s_array[(s_array[n] + s_array[i]) & 0xFF]

    @classmethod
    def inflate(cls, data):
        decompress = zlib.decompressobj(zlib.MAX_WBITS)

        inflated = decompress.decompress(data)
        inflated += decompress.flush()

        return inflated        
        
    def parse_error(self):
        err_inst = None
        
        if self.state['page']['viewName'] == 'error':
            err_inst = Error(None, self.state['page']['data']['content'])
        
        if 'error' in self.state['page']['data']:
            err = self.state['page']['data']['error']
            
            if 'document' in self.state['page']['data']:
                err_inst = Error(err['code'], err['msg'], str(Document(self.state['page']['data']['document'])))
        
        if self.state['session']['member']:
            if 'user_document_discuss' in self.state['session']['member']:
                if self.state['session']['member']['user_document_discuss'] > self.read_config('general.confirmed_user_discuss'):
                    self.logger.critical('Emergency stop!')
                    self.confirm_user_discuss()
                    raise StopSignal(self)

        if err_inst:
            self.logger.error(str(err_inst))
            raise err_inst

    def parse_chika(self, response):
        matches = self.rx_parse_script_url.findall(response.text)
        script_url = matches[2]

        script_response = requests.get(self.url(script_url))

        rx_find_chika = re.compile(r'"X-Chika":"([0-9a-f]*?)",')

        chika_match = rx_find_chika.search(script_response.text)
        self.x_chika = chika_match[1]

        self.logger.debug('Parse X-Chika: {}'.format(self.x_chika))
    
    def request_init(self, req_type, url, parameter = {}):
        url.baseurl = '/'

        finished = False
        loop_count = 0
        response = None

        while not finished and loop_count < 3:
            loop_count += 1
                
            self.set_wait('access')

            if req_type == "get":
                response = requests.get(str(url), cookies=self.cookies)
            elif req_type == "post":
                response = requests.post(str(url), data=parameter, cookies=self.cookies)
            elif req_type == "post.multipart":
                response = requests.post(str(url), files=parameter, cookies=self.cookies)
            else:
                raise TypeError('{} is invalid request type'.format(req_type))
                
            self.wait('access')

            content_type = response.headers['content-type'].split(';')[0].strip().casefold()
            if content_type == 'text/html':
                if response.status_code == 429:
                    input('Resolve the recaptcha.')
                    continue

                match = self.rx_parse_content.search(response.text)
                if not match:
                    raise ValueError('invalid response received')

                content = match[1]
                
                self.state = json.loads(content)

                if not self.is_loaded:
                    self.parse_chika(response)

                self.is_loaded = True
            else:
                raise TypeError('{} is unsupported MIME type'.format(content_type))
            
            finished = True

        with open('response.txt', mode='w') as f:
            json.dump(self.state, f, sort_keys=True, indent=4)
        
        self.parse_error()

        return response
    
    def request_internal(self, req_type, url, parameter = {}):
        assert self.is_loaded

        finished = False
        loop_count = 0
        response = None

        while not finished and loop_count < 3:
            loop_count += 1

            url.baseurl = '/internal/'
            headers = {'X-Chika': self.x_chika, 'X-Namuwiki-Nonce': self.theseed_nonce_hash(str('/' + url.url).casefold()), 'X-Riko': self.state['session']['hash'],
                'X-You': self.state['config']['hash'], 'charset': 'utf-8'}

            self.set_wait('access')

            if req_type == "get":
                url.parameter['_'] = int(time.time())
                response = requests.get(str(url), cookies=self.cookies, allow_redirects=False, headers=headers)
            elif req_type == "post":
                response = requests.post(str(url), data=parameter, cookies=self.cookies, allow_redirects=False, headers=headers)
            elif req_type == "post.multipart":
                response = requests.post(str(url), files=parameter, cookies=self.cookies, allow_redirects=False, headers=headers)
            else:
                raise TypeError('{} is invalid request type'.format(req_type))
                
            self.wait('access')
            
            if response.status_code == 429:
                input('Resolve the recaptcha.')
                continue

            if response.headers['x-ruby'] != 'hit' or (response.status_code >= 300 or response.status_code < 200):
                raise ValueError('invalid response received')
            
            content_type = response.headers['content-type'].split(';')[0].strip().casefold()
            if content_type == 'application/json':
                self.state['page'].update(json.loads(response.text))
            elif content_type == 'application/octet-stream':
                data = bytearray(response.content)
                self.decode_internal(data)

                self.state['page'].update(json.loads(self.inflate(data)))
            else:
                raise TypeError('{} is unsupported MIME type'.format(content_type))
            
            finished = True
                
        with open('response.txt', mode='w') as f:
            json.dump(self.state, f, sort_keys=True, indent=4)
        
        if self.state['page']['status'] == 200:
            self.parse_error()

        if 'sessionHash' in self.state['page']:
            self.state['session']['hash'] = self.state['page']['sessionHash']
            del self.state['page']['sessionHash']
        
        if 'session' in self.state['page']:
            self.state['session'].update(self.state['page']['session'])
            del self.state['page']['session']

        return response
        
        
    def get(self, url):
        if not self.is_loaded:
            return self.request_init('get', url)
        else:
            return self.request_internal('get', url)
        
    def post(self, url, parameter, multipart = False):
        if not self.is_loaded:
            return self.request_init('post' if not multipart else 'post.multipart', url, parameter)
        else:
            return self.request_internal('post' if not multipart else 'post.multipart', url, parameter)
    
    # handle configuration
    def load_config(self):
        if not self.config_path:
            self.config_path = self.default_config_path
            
        if not os.path.isfile(self.config_path):
            self.init_config()
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
    
    def read_config(self, key):
        keys = key.split('.')

        temp = self.config
        try:
            while keys:
                temp = temp[keys[0]]
                del keys[0]
        except KeyError:
            raise KeyError(key)
        
        return temp
    
    def write_config(self, key, value):
        keys = key.split('.')

        temp = self.config
        try:
            while len(keys) > 1:
                temp = temp[keys[0]]
                del keys[0]
        except KeyError:
            raise KeyError(key)
        
        temp[keys[0]] = value
        self.save_config()
        
    # action functions
    def w(self, title, rev = -1):
        '''
        response:
            "page"
                "data"
                    "body"
                    "category" []
                        "doc"
                            "namespace"
                            "title"
                        "exist"
                    "document"
                        "forceShowNamespace" (optional)
                        "namespace"
                        "title"
                    "discuss_progress"
                    "date"
                    "redirect"
                    "enable_ads"
                    "enable_powerlink"
                    "star_count"
                    "starred"
                    "rev"
                    "content"
                "meta"
                "title"
                "viewName"
        '''
        param = {}
        if rev > 0:
            param['rev'] = rev

        self.get(self.document_url(title, 'w', param, internal=True))

        data = self.state['page']['data']
        rev = data['rev']

        self.logger.info('Success (w, {}{})'.format(title, ' (r{})'.format(rev) if rev else ''))

        return data
    
    def raw(self, title, rev = -1):
        '''
        response:
            "page"
                "data"
                    "body"
                    "document"
                        "forceShowNamespace" (optional)
                        "namespace"
                        "title"
                    "rev"
                    "text"
                "meta"
                "title"
                "viewName"
        '''
        param = {}
        if rev > 0:
            param['rev'] = rev

        self.get(self.document_url(title, 'raw', param, internal=True))
        
        text = self.state['page']['data']['text']

        self.logger.info('Success (raw, {} (r{}))'.format(title, self.state['page']['data']['rev']))

        return text
    
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

        self.set_wait('edit')
            
        self.get(self.document_url(title, view_name, param))
        
        data = self.state['page']['data']
        
        token = data['token']
        rev = data['body']['baserev']
        text = data['body']['text']
        
        new_text = callback(title, text)
        
        if new_text == None:
            self.logger.info('Skip (edit, {})'.format(title))
            return
        
        ide = self.state['session']['identifier']
        
        parameters = {'token': (None, token), 'identifier': (None, ide), 'baserev': (None, rev), 'text': (None, new_text), 'log': (None, log), 'agree': (None, 'Y')}
        
        if section != None:
            parameters['section'] = (None, section)
        
        self.post(self.document_url(title, view_name), parameters, multipart=True)
        self.logger.info('Success ({}, {})'.format(view_name, title))
            
        self.wait('edit')
    
    def move(self, origin, target, log = '', swap = False, make_redirect = False):
        '''
        response:
            "page"
                "data"
                    "captcha"
                    "document"
                        "namespace"
                        "title"
                    "token"
        request:
            token
            identifier
            title
            log
            mode
        '''

        self.set_wait('edit')
            
        self.get(self.document_url(origin, 'move'))

        data = self.state['page']['data']

        token = data['token']
        ide = self.state['session']['identifier']

        parameters = {'token': (None, token), 'identifier': (None, ide), 'title': (None, target), 'log': (None, log), 'mode': (None, '' if not swap else 'swap')}
        
        self.post(self.document_url(origin, 'move'), parameters, multipart=True)
        self.logger.info('Success (move, {} to {})'.format(origin, target))

        self.wait('edit')

        if make_redirect:
            self.edit(origin, lambda a, b: '#redirect {}'.format(target))

    def delete(self, title, log = ''):
        '''
        response:
            "page"
                "data"
                    "captcha"
                    "document"
                        "namespace"
                        "title"
        request:
            token
            identifier
            title
            log
            mode
        '''

        self.set_wait('edit')

        self.get(self.document_url(title, 'delete'))

        ide = self.state['session']['identifier']

        parameters = {'identifier': (None, ide), 'log': (None, log), 'agree': (None, 'Y')}

        self.post(self.document_url(title, 'delete'), parameters, multipart=True)
        self.logger.info('Success (delete, {})'.format(title))

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
        
        id = self.read_config('member.username')
        pw = self.read_config('member.password')
        
        try:
            response = self.post(self.url('member/login'), {'username': id, 'password': pw, 'autologin': 'Y'})
        except Error as err:
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
            
            self.write_config('member.cookies', self.cookies)
    
    def logout(self):
        self.get(self.url('member/logout'))
        
        self.cookies = {}
        
        self.write_config('member.cookies', {})
        
        self.logger.info('Success (logout)')
    
    def search(self, query, pages = [1], return_total=False):
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
            self.get(self.url('Search', {'q': query, 'page': page}))
            
            search_json = self.state['page']['data']['search']
            
            for item in search_json:
                document = Document(item['doc'])
                
                search.append(document)
            self.logger.debug('Success (search, {} - page {})'.format(query, page))
        
        total = self.state['page']['data']['total']
        
        self.logger.info('Success (search, {})'.format(query))
        
        if return_total:
            return (search, total)
        else:
            return search
    
    def confirm_user_discuss(self):
        self.write_config('general.confirmed_user_discuss', int(time.time()))