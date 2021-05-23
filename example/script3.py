import re, math, sys, os, difflib, time, requests
from theseed_bot import theseed, namumark

targets = ['문서명 1', '문서명 2', '문서명 3', '문서명 4']
log = '자동 편집 중...(다크 모드 대응)'

def edit_dark(title, text):
    # 파서 초기화
    parser = namumark.Namumark(title, text)
    
    parser.paragraphs.sort_level()

    targets = []
        
    targets.extend(parser.paragraphs.find_all(type = 'WikiDiv', recursive = True))
    targets.extend(parser.paragraphs.find_all(type = 'HtmlText', recursive = True))
        
    for target in targets:
        target.separate_color()
    
    table_targets = parser.paragraphs.find_all(type = 'Table', recursive = True)
    
    for target in table_targets:
        target.apply_styles()
    
    colortext_targets = parser.paragraphs.find_all(type = 'ColoredText', recursive = True)
    linkedtext_targets = parser.paragraphs.find_all(type = 'LinkedText', recursive = True)
    
    for target in table_targets:
        target.generate_dark()
        
    for target in colortext_targets:
        target.generate_dark()
            
    for target in linkedtext_targets:
        target.generate_dark()
    
    for target in table_targets:
        target.compress()

    new_text = parser.render()

    sys.stdout.writelines(list(difflib.unified_diff(text.splitlines(keepends = True), new_text.splitlines(keepends = True))))
    
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
        new_text, log = edit_dark('문서', doc, False, res['text'])
        
        res = requests.post('https://namu.wiki/api/edit/{}'.format(doc), json = {'text': new_text, 'log': log, 'token': token}, headers = headers)
        print(res.text)
        
        time.sleep(1)