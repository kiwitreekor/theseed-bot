import re, math, sys, os, difflib
from theseed_bot import theseed, namumark

log = '자동 편집 중...(다크 모드 대응)'

def edit_dark(doc, text):
    parser = namumark.Namumark(namumark.Document(doc.namespace, doc.title, text, force_show_namespace=doc.force_show_namespace))
    
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

def do_edit(documents):
    i = 0
    while i < 500:
        documents = namu.randompage()

        for document in documents:
            finished = False
            err_count = 0

            while not finished and err_count < 4:
                try:
                    namu.edit(str(document), edit_dark)
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
        do_edit(edit_dark)
    finally:
        namu = None