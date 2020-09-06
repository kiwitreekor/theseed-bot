import requests, re, urllib.parse, json, os.path, time, logging, zlib, hashlib, base64
from bs4 import BeautifulSoup

# theseed v4.18.0

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
        return "'" + str(self) + "'"
    
    def __str__(self):
        if self.force_show_namespace:
            return self.namespace + ':' + self.title
        else:
            return self.title

class BacklinkFlags():
    file = 2
    include = 4
    link = 1
    redirect = 8

class Namespaces():
    category = '분류'
    template = '틀'
    document = '문서'
    file = '파일'
    user = '사용자'

class TheSeed():
    rx_parse_content = re.compile(r'<script>window\.INITIAL_STATE=(\{.*?\})</script>')
    rx_parse_script_url = re.compile(r'<script src="/(skins/[^<>]*?/main\.[^<>]*?\.js)" defer></script>')
    x_chika = ''
    cookies = {}
    strings = []
    
    decode_array = []
    
    initial_config = {'member': {'username': None, 'password': None, 'cookies': {}}, 'general': {'log_level': {'file': 20, 'stream': 10}, 'edit_interval': 1000, 'access_interval': 500, 'log_path': './theseed.log', 'confirmed_user_discuss': int(time.time())}}
    default_config_path = 'config.json'
    config_path = ''
    
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 Edg/81.0.416.72'

    max_loop_count = 5

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
    
    def __init__(self, host, config_path = ''):
        self.host = host
        
        self.config_path = config_path
        self.load_config()
        
        self.logger = logging.getLogger(__name__)

        self.is_loaded = False
        
        file_log_level = self.read_config('general.log_level.file')
        stream_log_level = self.read_config('general.log_level.stream')
        log_formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)s] >> %(message)s')
        
        log_file_handler = logging.FileHandler(self.read_config('general.log_path'), encoding='utf-8')
        log_file_handler.setFormatter(log_formatter)
        log_file_handler.setLevel(level=file_log_level)
        
        log_stream_handler = logging.StreamHandler()
        log_stream_handler.setFormatter(log_formatter)
        log_stream_handler.setLevel(level=stream_log_level)
        
        self.logger.addHandler(log_file_handler)
        self.logger.addHandler(log_stream_handler)
        self.logger.setLevel(level=min(stream_log_level, file_log_level))

        self.state = {}
    
    def __del__(self):
        self.save_config()
        
    # helper functions
    def url(self, url_, parameter = None):
        if parameter == None:
            parameter = {}
            
        return URL(self.host, '/', url_, parameter)
    
    def document_url(self, title, _type = '', parameter = None):
        if parameter == None:
            parameter = {}
            
        parameter['noredirect'] = 1
        return self.url(_type + '/' + urllib.parse.quote(title, encoding='UTF-8'), parameter)
    
    def set_wait(self, _type):
        self.wait_start[_type] = time.time()

    def wait(self, _type):
        if _type == 'access':
            wait_time = self.read_config('general.access_interval')
        elif _type == 'edit':
            wait_time = self.read_config('general.edit_interval')
        
        time.sleep(max(self.wait_start[_type] + wait_time / 1000 - time.time(), 0))
        
        del self.wait_start[_type]
    
    def theseed_nonce_hash(self, value):
        bvalue = value.encode('utf-8')
        
        m = hashlib.md5()
        m.update(bvalue)
        
        hash = m.digest()[:16]
        
        return base64.b64encode(hash)
    
    def decode_internal(self, stream):
        n = 0
        i = 0
        e = 0
        s_array = list(self.decode_array)
        
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
            err_type = None

            if '편집요청 권한이 부족' in self.state['page']['data']['content']:
                err_type = 'permission_edit_request'
            elif '문서를 찾을 수 없습니다.' in self.state['page']['data']['content']:
                err_type = 'document_not_found'

            err_inst = Error(err_type, self.state['page']['data']['content'])
        
        if 'error' in self.state['page']['data']:
            err = self.state['page']['data']['error']
            
            if 'document' in self.state['page']['data']:
                err_inst = Error(err['code'], err['msg'], str(Document(self.state['page']['data']['document'])))
            else:
                err_inst = Error(err['code'], err['msg'])
        
        if self.state['session']['member']:
            if 'user_document_discuss' in self.state['session']['member']:
                if self.state['session']['member']['user_document_discuss'] > self.read_config('general.confirmed_user_discuss'):
                    self.logger.critical('Emergency stop!')
                    self.confirm_user_discuss()
                    raise StopSignal(self)

        if err_inst:
            self.logger.error(str(err_inst))
            raise err_inst

    def parse_strings(self, response):
        match = self.rx_parse_script_url.search(response.text)
        script_url = match[1]

        script_response = requests.get(self.url(script_url))
        
        rx_js_var = re.compile(r'var ([A-Za-z0-9_]+)=\[(.*?)\];')
        rx_js_array256 = re.compile(r'\[(((0x[0-9A-Fa-f]+),){255}(0x[0-9A-Fa-f]+))\]')
        js_var_match = rx_js_var.search(script_response.text)
        
        str_var = js_var_match[1]
        str_raw = js_var_match[2]
        
        rx_quotes = re.compile(r"(?<!\\)'")
        quote_pos = None
        for m in rx_quotes.finditer(str_raw):
            if not quote_pos:
                quote_pos = m.start(0) + 1
            else:
                self.strings.append(str_raw[quote_pos:m.start(0)])
                quote_pos = None
        
        self.decode_array = []
        
        rx_js_rotate = re.compile(rf'\({str_var},(0x[0-9A-Fa-f]+)\)')
        str_rotate = int(rx_js_rotate.search(script_response.text)[1], 16)
        
        # decode_array_match = rx_js_array256.search(script_response.text)[1].split(',')
        # for i in range(256):
        #     self.decode_array.append(int(decode_array_match[i], 16))
        
        self.strings = self.strings[str_rotate:] + self.strings[:str_rotate]
        
        rx_find_chika = re.compile(r"'X-Chika': *[a-z0-9_]+\('(.*?)'\),")
        
        chika_match = rx_find_chika.search(script_response.text)
        chika_string_id = int(chika_match[1], 16)
        
        self.x_chika = self.strings[chika_string_id]

        self.logger.debug('Parse X-Chika: {}'.format(self.x_chika))
    
    def request_init(self, req_type, url, parameter = {}):
        url.baseurl = '/'

        finished = False
        loop_count = 0
        response = None
        
        headers = {'user-agent': self.user_agent}

        while not finished and loop_count < self.max_loop_count:
            loop_count += 1
                
            self.set_wait('access')

            if req_type == "get":
                response = requests.get(str(url), cookies=self.cookies, headers=headers)
            elif req_type == "post":
                response = requests.post(str(url), data=parameter, cookies=self.cookies, headers=headers)
            elif req_type == "post.multipart":
                response = requests.post(str(url), files=parameter, cookies=self.cookies, headers=headers)
            else:
                raise TypeError('{} is invalid request type'.format(req_type))
                
            self.wait('access')

            content_type = response.headers['content-type'].split(';')[0].strip().casefold()
            if content_type == 'text/html':
                if response.status_code == 429:
                    # IP로 감지하는 리캡차이므로 브라우저를 켜서 해결하면 됨.
                    input('Resolve the recaptcha.')
                    continue

                match = self.rx_parse_content.search(response.text)
                if not match:
                    raise ValueError('invalid response received')

                content = match[1]
                
                self.state = json.loads(content)

                if not self.is_loaded:
                    self.parse_strings(response)

                self.is_loaded = True
            else:
                raise TypeError('{} is unsupported MIME type'.format(content_type))
            
            finished = True

        # with open('response.txt', mode='w', encoding='utf-8') as f:
            # json.dump(self.state, f, ensure_ascii=False, sort_keys=True, indent=4)
        
        self.parse_error()

        return response
    
    def request_internal(self, req_type, url, parameter = {}):
        assert self.is_loaded

        finished = False
        loop_count = 0
        response = None
        
        while not finished and loop_count < self.max_loop_count:
            loop_count += 1

            url.baseurl = '/internal/'
            headers = {'X-Chika': self.x_chika, 'X-Namuwiki-Nonce': self.theseed_nonce_hash(str('/' + url.url).casefold()), 'X-Riko': self.state['session']['hash'],
                'X-You': self.state['config']['hash'], 'charset': 'utf-8', 'user-agent': self.user_agent}

            self.set_wait('access')

            try:
                if req_type == "get":
                    response = requests.get(str(url), cookies=self.cookies, allow_redirects=False, headers=headers)
                elif req_type == "post":
                    response = requests.post(str(url), data=parameter, cookies=self.cookies, allow_redirects=False, headers=headers)
                elif req_type == "post.multipart":
                    response = requests.post(str(url), files=parameter, cookies=self.cookies, allow_redirects=False, headers=headers)
                else:
                    raise TypeError('{} is invalid request type'.format(req_type))
            except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError) as e:
                # https://stackoverflow.com/questions/44509423/python-requests-chunkedencodingerrore-requests-iter-lines
                if loop_count < self.max_loop_count:
                    continue
                else:
                    raise e
                
            self.wait('access')
            
            if response.status_code == 429:
                input('Resolve the recaptcha.')
                continue
            elif response.status_code == 400:
                # Frontend update detected
                self.is_loaded = False
                return self.request_init(req_type, url, parameter)

            if not 'x-ruby' in response.headers:
                print(response.text)
                with open('response.txt', mode='w', encoding='utf-8') as f:
                    json.dump(dict(response.headers), f, ensure_ascii=False, sort_keys=True, indent=4)
                
                if loop_count < self.max_loop_count:
                    continue
                else:
                    raise ValueError('invalid response received')
            
            if response.headers['x-ruby'] != 'hit' or (response.status_code >= 300 or response.status_code < 200):
                if loop_count < self.max_loop_count:
                    continue
                else:
                    raise ValueError('invalid response received')
            
            content_type = response.headers['content-type'].split(';')[0].strip().casefold()
            if content_type == 'application/json':
                self.state['page'].update(json.loads(response.text))
            elif content_type == 'application/octet-stream':
                # data = bytearray(response.content)
                # self.decode_internal(data)
                data = response.text

                self.state['page'].update(json.loads(self.inflate(data)))
            else:
                raise TypeError('{} is unsupported MIME type'.format(content_type))
            
            finished = True
                
        # with open('response.txt', mode='w', encoding='utf-8') as f:
            # json.dump(self.state, f, ensure_ascii=False, sort_keys=True, indent=4)
        
        if self.state['page']['status'] == 200:
            self.parse_error()
        elif self.state['page']['status'] >= 400 and self.state['page']['status'] < 500:
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
        
        self.config = self.initial_config
        
        with open(self.config_path, 'r') as config_file:
            config = json.load(config_file)
        
        def update(d, u):
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d
        
        self.config = update(self.config, config)
            
        self.cookies = self.config['member']['cookies']
    
    def init_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as config_file:
            json.dump(self.initial_config, config_file, ensure_ascii=False, sort_keys=True, indent=4)
    
    def save_config(self):
        if not self.config_path:
            self.config_path = self.default_config_path

        with open(self.config_path, 'w', encoding='utf-8') as config_file:
            json.dump(self.config, config_file, ensure_ascii=False, sort_keys=True, indent=4)
    
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

    def confirm_user_discuss(self):
        self.write_config('general.confirmed_user_discuss', int(time.time()))
        
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

        self.get(self.document_url(title, 'w', param))

        if self.state['page']['viewName'] == 'notfound':
            self.logger.info('Not Found (w, {})'.format(title))

            return None

        assert self.state['page']['viewName'] == 'wiki'

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

        self.get(self.document_url(title, 'raw', param))
        
        text = self.state['page']['data']['text']

        self.logger.info('Success (raw, {} (r{}))'.format(title, self.state['page']['data']['rev']))

        return text
    
    def random(self):
        loaded = self.is_loaded
        self.get(self.url('random'))

        if loaded:
            return urllib.parse.unquote(self.state['page']['url'][3:])
        else:
            return self.state['page']['title']
    
    def randompage(self, namespace = Namespaces.document):
        '''
        "page"
            "data"
                "namespaces"
                "selectedNamespace"
                "randompage" []
                    "namespace"
                    "title"
        '''
        self.get(self.url('RandomPage', {'namespace':  namespace}))

        documents = []

        for doc in self.state['page']['data']['randompage']:
            documents.append(Document(doc))
        
        return documents

    def get_available_namespaces(self):
        self.get(self.url('RandomPage'))

        namespaces = self.state['page']['data']['namespaces']

        return namespaces

    def history(self, title, from_ = None, until = None, page = -1):
        '''
        "page"
            "data"
                "document"
                    "namespace"
                    "title"
                "history" []
                    "rev"
                    "log"
                    "date"
                    "author" or "ip"
                    "count"
                    "logtype"
                    "target_rev"
                    "blocked"
                
        '''

        history = []
        finished = False
        next_rev = None
        
        i = 0

        while not finished and (page < 0 or i < page):
            parameters = {}
            if from_ and not next_rev:
                parameters['from'] = from_
            elif next_rev:
                parameters['from'] = next_rev
            
            self.get(self.document_url(title, 'history', parameter=parameters))

            history_json = self.state['page']['data']['history']

            next_rev = self.state['page']['data']['from']

            if until:
                if not next_rev:
                    finished = True
                elif until < next_rev:
                    finished = True
            else:
                if not next_rev:
                    finished = True

            for h in history_json:
                pass_doc = False

                if from_ and h['rev'] > from_:
                    pass_doc = True

                if until and h['rev'] < until:
                    pass_doc = True
                
                if not pass_doc:
                    history.append(h)
            
            self.logger.debug('Success (history, {}{}, partial)'.format(title, ' - from {}'.format(parameters['from']) if 'from' in parameters else ''))
            i += 1

        self.logger.info('Success (history, {})'.format(title))

        return history
    
    def edit_request(self, slug):
        '''
        "page"
            "data"
                "body"
                "document"
                    "namespace"
                    "title"
                "editRequest"
                    "slug"
                    "status" (accepted|open|closed)
                    "accepter_author"
                    "baserev"
                    "log"
                    "author"
                    "ip"
                    "created"
                    "updated"
                    "accepted_rev"
                    "close_reason"
                "isAcceptable"
                "isOwnEditRequest"
                "isConflicted"
                "diffoutput"
                "updateThreadStatus"
        '''

        self.get(self.document_url(slug, 'edit_request'))

        edit_request = self.state['page']['data']['editRequest']

        self.logger.info('Success (edit_request, {})'.format(slug))

        return edit_request
    
    def edit(self, title, callback, section = None, request = False):
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
        
        finished = False
        loop_count = 0
        
        action_name = ''
        request_exists = False

        while not finished and loop_count < self.max_loop_count:
            if not request_exists:
                url = self.document_url(title, view_name, param)
                action_name = view_name
                
            self.get(url)
            
            if self.state['page']['status'] >= 300 and self.state['page']['status'] < 400 and not request_exists:
                view_name = 'new_edit_request'
                continue
            
            data = self.state['page']['data']
            
            token = data['token']
            rev = data['body']['baserev']
            text = data['body']['text']
            
            result = callback(Document(data['document']), text)
            skip_log = 'Skip ({}, {})'.format(action_name, title)

            if result == None:
                self.logger.info(skip_log)
                return
            
            new_text, log = result

            if new_text == text:
                self.logger.info(skip_log)
                return
            
            ide = self.state['session']['identifier']
            
            parameters = {'token': (None, token), 'identifier': (None, ide), 'baserev': (None, rev), 'text': (None, new_text), 'log': (None, log), 'agree': (None, 'Y')}
            
            if section != None:
                parameters['section'] = (None, section)
            
            try:
                self.post(self.document_url(title, view_name), parameters, multipart=True)
            except Error as err:
                if err.code == 'already_edit_request_exists':
                    slug = self.find_my_edit_request(title)
                    action_name = 'edit_my_request'
                    url = self.document_url(slug + '/edit', 'edit_request')
                    request_exists = True
                else:
                    raise err
            else:
                finished = True
            
            loop_count += 1

        self.logger.info('Success ({}, {})'.format(action_name, title))
            
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
            self.edit(origin, lambda a, b: ('#redirect {}'.format(target), '자동 생성된 리다이렉트'))

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
            identifier
            agree
            log
        '''

        self.set_wait('edit')

        self.get(self.document_url(title, 'delete'))

        ide = self.state['session']['identifier']

        parameters = {'identifier': (None, ide), 'log': (None, log), 'agree': (None, 'Y')}

        self.post(self.document_url(title, 'delete'), parameters, multipart=True)
        self.logger.info('Success (delete, {})'.format(title))

        self.wait('edit')
    
    def revert(self, title, rev, log = ''):
        '''
        request:
            identifier
            rev
            log
        '''
        
        self.set_wait('edit')

        ide = self.state['session']['identifier']

        parameters = {'identifier': ide, 'log': log, 'rev': rev}

        self.post(self.document_url(title, 'revert'), parameters)
        self.logger.info('Success (revert, {}, r{})'.format(title, rev))

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
            # record cookies
            if 'kotori' in response.cookies:
                self.cookies['kotori'] = response.cookies['kotori']
            
            # pin
            if self.state['page']['viewName'] == 'login_pin':
                if self.state['page']['data']['mode'] == 'pin':
                    while True:
                        pin = input('{}로 도착한 PIN을 입력하세요: '.format(self.state['page']['data']['email']))
                        
                        if not pin:
                            return
                        
                        try:
                            response = self.post(self.url('member/login/pin'), {'pin': pin, 'trust': 'Y'})
                        except Error as err:
                            continue
                        
                        if self.state['page']['status'] == 302:
                            break
                elif self.state['page']['data']['mode'] == 'disable':
                    response = self.post(self.url('member/login/pin'), {'pin': '123456', 'trust': 'Y'})
                else:
                    raise NotImplementedError('Unidentified page')
                        
            self.logger.info('Success (login, {})'.format(id))
            
            if 'honoka' in response.cookies:
                self.cookies['honoka'] = response.cookies['honoka']
                
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

    def backlink(self, title, from_ = None, until = None, namespaces = None, flag = None):
        '''
        response:
            "page"
                "data"
                    "body"
                    "RefsFlagsMap"
                        "file"
                        "include"
                        "link"
                        "redirect"
                    "backlinks" {[]}
                        "doc"
                        "type"
                    "from"
                    "until"
                    "namespaces" []
                        "count"
                        "namespace"
                    "selectedFlag"
                    "selectedNamespace"
        '''
        document_list = []

        # load all namespaces
        self.get(self.document_url(title, 'backlink'))

        all_namespaces = [x['namespace'] for x in self.state['page']['data']['namespaces']]

        if namespaces == None:
            namespaces = all_namespaces

        for namespace in namespaces:
            if namespace not in all_namespaces:
                continue

            finished = False
            next_doc = None

            while not finished:
                parameters = {}
                if from_ and not next_doc:
                    parameters['from'] = from_
                elif next_doc:
                    parameters['from'] = next_doc
                
                if namespace:
                    parameters['namespace'] = namespace
                
                if flag:
                    parameters['flag'] = flag
                
                self.get(self.document_url(title, 'backlink', parameter=parameters))

                backlink_json = self.state['page']['data']['backlinks']

                next_doc = self.state['page']['data']['from']

                if until:
                    if not next_doc:
                        finished = True
                    elif until < next_doc:
                        finished = True
                else:
                    if not next_doc:
                        finished = True

                for backlinks in backlink_json.values():
                    for backlink in backlinks:
                        doc = Document(backlink['doc'])
                        pass_doc = False

                        if from_ and doc.title < from_:
                            pass_doc = True

                        if until and doc.title > until:
                            pass_doc = True
                        
                        if not pass_doc:
                            if flag != None:
                                document_list.append(doc)
                            else:
                                document_list.append((doc, backlink['type']))
                
                self.logger.debug('Success (backlink, {}{}, partial)'.format(title, ' - from {}'.format(parameters['from']) if 'from' in parameters else ''))

        self.logger.info('Success (backlink, {})'.format(title))

        return document_list
    
    def _category(self, title, namespaces = None, from_ = None, until = None):
        '''
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
                "categorys" []
                    "namespace"
                    "total"
                    "isCategoryNamespace"
                    "categorys" {[]}
                        "doc"
                        "type"
                    "from"
                    "until"
            "meta"
            "title"
            "viewName"
        '''
        document_list = []
        
        if namespaces == None:
            # load all namespaces
            self.get(self.document_url(Namespaces.category + ':' + title, 'w'))

            namespaces = [x['namespace'] for x in self.state['page']['data']['categorys']]

            if Namespaces.category in namespaces:
                del namespaces[namespaces.index(Namespaces.category)]

        for namespace in namespaces:
            finished = False
            next_doc = None
            
            while not finished:
                parameters = {}
                if from_ and not next_doc:
                    parameters['cfrom'] = from_
                elif next_doc:
                    parameters['cfrom'] = next_doc
                
                if namespace:
                    parameters['namespace'] = namespace
                
                self.get(self.document_url(Namespaces.category + ':' + title, 'w', parameter=parameters))

                categories_json = None

                for category_list in self.state['page']['data']['categorys']:
                    if category_list['namespace'] == namespace:
                        categories_json = category_list
                
                if not categories_json:
                    break

                next_doc = categories_json['from']

                if until:
                    if not next_doc:
                        finished = True
                    elif until < next_doc:
                        finished = True
                else:
                    if not next_doc:
                        finished = True

                for links in categories_json['categorys'].values():
                    for link in links:
                        doc = Document(link)
                        pass_doc = False

                        if from_ and doc.title < from_:
                            pass_doc = True

                        if until and doc.title > until:
                            pass_doc = True
                        
                        if not pass_doc:
                            document_list.append(doc)
                
                self.logger.debug('Success (category, {}{}, partial)'.format(title, ' - from {}'.format(parameters['cfrom']) if 'cfrom' in parameters else ''))

        self.logger.info('Success (category, {})'.format(title))

        return document_list
    
    def category(self, title, namespaces = None, exclude = None, from_ = None, until = None, recursive = -1):
        if exclude == None:
            exclude = []

        if title in exclude:
            return []
        
        document_list = self._category(title, namespaces, from_, until)
        
        if recursive != 0:
            category_list = self._category(title, [Namespaces.category], from_, until)
            
            exclude.append(title)
            
            for category in category_list:
                document_list.extend(self.category(category.title, namespaces, exclude, from_, until, recursive - 1))
        
        titles = []
        
        result = []
        
        for document in document_list:
            if not str(document) in titles:
                titles.append(str(document))
                result.append(document)
        
        return result
    
    def thread_list(self, title, type_ = 'discuss'):
        '''
        "page"
            "data":
                "document"
                    "namespace"
                    "title"
                "thread_list" []
                    "discuss" []
                        "id"
                        "author"
                        "text"
                        "date"
                        "hide_author"
                        "type"
                        "admin"
                        "blocked"
                    "slug"
                    "topic"
                "editRequests" []
                    "slug"
                "deleteThread"
                "body"
        '''
        result = []

        parameters = {}

        if type_ == 'closed_edit_request':
            parameters['state'] = 'closed_edit_requests'
        elif type_ == 'closed_discuss':
            parameters['state'] = 'close'

        self.get(self.document_url(title, 'discuss', parameter=parameters))

        if type_ == 'discuss':
            for thread in self.state['page']['data']['thread_list']:
                result.append(thread['slug'])
        
        elif type_ == 'edit_request' or type_ == 'closed_edit_request':
            for edit_request in self.state['page']['data']['editRequests']:
                result.append(edit_request['slug'])
 
        return result
    
    def thread(self, slug, comment = None):
        '''
        main response
            "page"
                "data":
                    "document"
                        "namespace"
                        "title"
                    "status" (normal|pause|close)
                    "topic"
                    "slug"
                    "comments" []
                        "id"
                        "hide_author"
                    "updateThreadDocument"
                    "updateThreadTopic"
                    "updateThreadStatus"
                    "hideThreadComment"
                    "deleteThread"
                    "body"
        comment response
            "comments" []
                "id"
                "author"
                "ip"
                "text"
                "date"
                "hide_author"
                "type" (normal|status|document|topic)
                "admin"
                "blocked"
        '''

        self.get(self.document_url(slug, 'thread'))

        result = {}

        result['document'] = Document(self.state['page']['data']['document'])
        result['status'] = self.state['page']['data']['status']
        result['topic'] = self.state['page']['data']['topic']
        result['comments'] = []
        
        comment_num = len(self.state['page']['data']['comments'])
        loaded_comment = 0

        comments = []

        if comment == None:
            comment = range(1, comment_num + 1)
        
        for i in comment:
            if loaded_comment >= i:
                continue

            self.get(self.document_url(slug + '/{}'.format(i), 'thread'))
            comments.extend(self.state['page']['data']['comments'])

            loaded_comment = i + 30
        
        for c in comments:
            if c['id'] in comment:
                result['comments'].append(c)

        self.logger.info('Success (thread, {})'.format(slug))

        return result
    
    def create_thread(self, document, topic, text):
        '''
        request:
            identifier
            topic
            text
        '''
        parameters = {'identifier': (self.state['session']['identifier']), 'topic': topic, 'text': (text)}
        self.post(self.document_url(document, 'discuss'), parameters)

        if self.state['page']['status'] != '302':
            raise Error('no permission!')

        target_url = self.state['page']['url']
        match = re.match(r'/thread/(.*)', target_url)

        assert match
        
        slug = match[1]

        self.logger.info('Success (create_thread, {})'.format(slug))

        return slug

    def comment_thread(self, slug, text):
        '''
        request:
            identifier
            text
        '''

        parameters = {'identifier': (self.state['session']['identifier']), 'text': (text)}
        self.post(self.document_url(slug, 'thread'), parameters)

        self.logger.info('Success (comment_thread, {})'.format(slug))
    
    def find_my_edit_request(self, title):
        edit_requests = self.thread_list(title, 'edit_request')

        for slug in edit_requests:
            info = self.edit_request(slug)
            
            if info['status'] != 'open':
                continue

            if info['author'] == self.read_config('member.username'):
                return slug
        
        return None
    
    def _meta_pages(self, view_name, namespace = None, from_ = None, until = None):
        '''
        "page"
            "data":
                "selectedNamespace"
                "namespaces"
                "orphanedpages|neededpages|uncategorizedpages" []
                    "id"
                    "doc"
                        "namespace"
                        "title"
                "from"
                "until"
                "body"
        '''

        document_list = []
        finished = False
        next_doc = None

        while not finished:
            parameters = {}
            if from_ and not next_doc:
                parameters['from'] = from_
            elif next_doc:
                parameters['from'] = next_doc
            
            if namespace:
                parameters['namespace'] = namespace
            
            self.get(self.url(view_name, parameter=parameters))

            pages_json = self.state['page']['data'][view_name.lower()]

            next_doc = self.state['page']['data']['from']

            if until:
                if not next_doc:
                    finished = True
                elif until < next_doc:
                    finished = True
            else:
                if not next_doc:
                    finished = True

            for page in pages_json:
                doc = Document(page['doc'])
                pass_doc = False

                if from_ and doc.title < from_:
                    pass_doc = True

                if until and doc.title > until:
                    pass_doc = True
                
                if not pass_doc:
                    document_list.append(doc)
            
            self.logger.debug('Success ({}{}, partial)'.format(view_name, ' - from {}'.format(parameters['from']) if 'from' in parameters else ''))

        self.logger.info('Success ({})'.format(view_name))

        return document_list
    
    def orphaned_pages(self, namespace = None, from_ = None, until = None):
        return self._meta_pages('OrphanedPages', namespace, from_, until)
    
    def uncategorized_pages(self, namespace = None, from_ = None, until = None):
        return self._meta_pages('UncategorizedPages', namespace, from_, until)
    
    def needed_pages(self, namespace = None, from_ = None, until = None):
        return self._meta_pages('NeededPages', namespace, from_, until)

    def acl(self, title, acl_type = None):
        '''
        "page"
            "data":
                "document"
                    "namespace"
                    "title"
                "docACL"
                    "acls"
                        "read"/"edit"/"move"/"delete"/"edit_request"/"create_thread"/"write_thread_comment"/"acl" []
                            "id"
                            "condition"
                            "action"
                            "expired"
                    "editable"
                "nsACL"
                    (same as docACL)
                "ACLTypes"
                "body"
        '''

        self.get(self.document_url(title, 'acl'))

        document_acl = self.state['page']['data']['docACL']['acls']
        namespace_acl = self.state['page']['data']['nsACL']['acls']
        
        if not acl_type:
            result = {}

            result['docACL'] = document_acl
            result['nsACL'] = namespace_acl
        else:
            if acl_type not in document_acl or acl_type not in namespace_acl:
                raise KeyError(acl_type)
                
            if document_acl[acl_type]:
                result = document_acl[acl_type]
            else:
                result = namespace_acl[acl_type]

        self.logger.info('Success (acl, {})'.format(title))

        return result
