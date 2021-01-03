import re, math, sys, os, difflib
from theseed_bot import theseed, namumark

log = '자동 편집 중...(셀 정렬 문법 통일)'

def unify_align(doc, text):
    parser = namumark.Namumark(namumark.Document(doc.namespace, doc.title, text, force_show_namespace=doc.force_show_namespace), available_namespaces=namu.get_available_namespaces())
    
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

def do_edit():
    i = 0
    while i < 500:
        documents = namu.randompage()

        for document in documents:
            finished = False
            err_count = 0

            while not finished and err_count < 4:
                try:
                    namu.edit(str(document), unify_align)
                except theseed.Error as err:
                    if err.code == 'recaptcha-error':
                        namu.logout()
                        namu.login()
                        
                        err_count += 1
                        continue
                    elif err.code == 'permission_edit':
                        finished = True
                        continue
                    elif err.code == 'same_content':
                        finished = True
                        pass
                    elif err.code == 'already_edit_request_exists':
                        finished = True
                        pass
                    else:
                        raise err
                except theseed.StopSignal:
                    sys.exit()
                else:
                    finished = True
        
        i += 1
                    
if __name__ == '__main__':
    namu = theseed.TheSeed('namu.wiki')

    namu.logout()
    namu.login()

    try:
        do_edit()
    finally:
        namu = None