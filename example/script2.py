import re, math, sys, os, difflib, time, requests
from theseed_bot import namumark

targets = ['문서명 1', '문서명 2', '문서명 3', '문서명 4']
log = '자동 편집 중...(인용문 색상 제거 - 분류:{})'

def remove_color(title, text):
    # 파서 초기화
    parser = namumark.Namumark(title, text)

    # 문단 정렬
    parser.paragraphs.sort_level()

    # 인용문 검색
    quote_targets = parser.paragraphs.find_all(type = 'QuotedText', recursive = True)

    for i in quote_targets:
        # 색상 문법 검색
        color_targets = i.find_all(type = 'ColoredText', recursive = True)

        for c in color_targets:
            # 색상 문법 제거
            idx = c.parent.content.index(c)
            c.parent.content = c.parent.content[:idx] + c.content + c.parent.content[idx+1:]
    
    new_text = parser.render()

    sys.stdout.writelines(list(difflib.unified_diff(text.splitlines(keepends = True), new_text.splitlines(keepends = True))))
    
    return (new_text, log.format(target))
                    
headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ?'}

if __name__ == '__main__':
    # theseed API 활용 방법은 https://doc.theseed.io/ 참고
    for target in targets:
        target_backlinks = []
        next = None
        
        while True:
            res = requests.get('https://namu.wiki/api/backlink/{}?from={}'.format(target, next), headers = headers).json()
            
            for doc in res['backlinks']:
                target_backlinks.append(doc['document'])
            
            next = res['from']
            if not next:
                break
        
        for doc in target_backlinks:
            res = requests.get('https://namu.wiki/api/edit/{}'.format(doc), headers = headers).json()
            try:
                if not res['exists']:
                    continue
            except:
                print(res)
                continue
            
            token = res['token']
            new_text, log = remove_color('문서', doc, False, res['text'])
            
            res = requests.post('https://namu.wiki/api/edit/{}'.format(doc), json = {'text': new_text, 'log': log, 'token': token}, headers = headers)
            print(res.text)
            
            time.sleep(1)