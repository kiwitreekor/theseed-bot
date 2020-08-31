import re, math, sys, os, difflib
from theseed_bot import theseed, namumark

targets = ['메카니멀']
log = '자동 편집 중...(인용문 색상 제거 - 분류:{})'

def remove_color(doc, text):
    parser = namumark.Namumark(namumark.Document(doc.namespace, doc.title, text, force_show_namespace=doc.force_show_namespace))

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

def do_edit(documents, from_ = None):
    check = False
    for document in documents:
        if from_:
            if not check:
                if str(document) == from_:
                    check = True
                else:
                    continue
        
        finished = False
        err_count = 0

        while not finished and err_count < 4:
            try:
                namu.edit(str(document), remove_color)
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
                    
if __name__ == '__main__':
    namu = theseed.TheSeed('namu.wiki')

    namu.logout()
    namu.login()
    
    try:
        for target in targets:
            documents = namu.category(target, namespaces=[theseed.Namespaces.document], recursive=-1)
            do_edit(documents)
    finally:
        namu = None