import re, math, sys, os, difflib, time, requests
from theseed_bot import theseed, namumark

targets = ['문서명 1', '문서명 2', '문서명 3', '문서명 4']
log = '자동 편집 중...(셀 정렬 문법 통일)'

def unify_align(title, text):
    # 파서 초기화
    parser = namumark.Namumark(title, text)
    
    parser.paragraphs.sort_level()
    # parser만 불러온 뒤 바로 아무것도 하지 않고 바로 render()를 할 경우,
    # 셀 내용 정렬시 <(><:><)>가 존재하면 살려두고, 없이 여백만 있으면 여백을 이용합니다.

    table_targets = []
    table_targets.extend(parser.paragraphs.find_all(type = 'Table', recursive = True))
    
    for target in table_targets:
        # 아래 함수는 <(><:><)>를 ||에 붙이는 여백 문법으로 바꿉니다.
        target.compress_align()
    
    new_text = parser.render()

    return (new_text, log)
                    
headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ?'}

if __name__ == '__main__':
    # theseed API 활용 방법은 https://doc.theseed.io/ 참고
    for doc in targets:
        res = requests.get('https://namu.wiki/api/edit/{}'.format(doc), headers = headers).json()
        try:
            if not res['exists']:
                continue
        except:
            print(res)
            continue
        
        token = res['token']
        new_text, log = unify_align('문서', doc, False, res['text'])
        
        res = requests.post('https://namu.wiki/api/edit/{}'.format(doc), json = {'text': new_text, 'log': log, 'token': token}, headers = headers)
        print(res.text)
        
        time.sleep(1)