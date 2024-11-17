import re, math, sys, os, difflib, time, requests
from theseed_bot import namumark

targets = [('분류:분류 1', '분류:대체 분류 1'), ('분류:분류 2', '분류:대체 분류 2')]
log = '자동 편집 중...(역링크 수정)'

def edit_category(title, text):
    # 파서 초기화
    parser = namumark.Namumark(title, text)
    
    for target, replace in targets:
        # 분류 교체
        parser.replace_category(target, replace)
    
    # 분류를 모두 상단으로 이동
    parser.move_category(namumark.CategoryPosition.TOP)
    
    new_text = parser.render()

    sys.stdout.writelines(list(difflib.unified_diff(text.splitlines(keepends = True), new_text.splitlines(keepends = True))))
        
    return (new_text, log)
                    
headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ?'}

if __name__ == '__main__':
    # theseed API 활용 방법은 https://doc.theseed.io/ 참고
    for target, replace in targets:
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
            new_text, log = edit_link(doc, res['text'])
            
            res = requests.post('https://namu.wiki/api/edit/{}'.format(doc), json = {'text': new_text, 'log': log, 'token': token}, headers = headers)
            print(res.text)
            
            time.sleep(1)