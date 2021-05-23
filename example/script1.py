import re, math, sys, os, difflib, time, requests
from theseed_bot import namumark

targets = [('문서명 1', '대체 문서명 1'), ('문서명 2', '대체 문서명 2')]
log = '자동 편집 중...(역링크 수정)'

def edit_link(title, text):
    # 파서 초기화
    parser = namumark.Namumark(title, text)

    # 문단 정렬
    parser.paragraphs.sort_level()
    
    for target, replace in targets:
        # 링크 검색
        link_targets = parser.paragraphs.find_all(type = 'LinkedText', link = target, recursive = True)
    
        for link in link_targets:
            # 링크 내용 교체
            link.link = replace
            
            if not link.content:
                # 링크에 대체 텍스트가 없는 경우 원본 텍스트 유지
                link.content = [namumark.PlainText(target)]
    
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