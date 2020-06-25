import re, sys
from theseed_bot import theseed, namumark

targets = ['봉숭아 학당(개그 콘서트)']
log = '자동 편집 중...(역링크 수정 - {})'

def edit_link(doc, text):
    parser = namumark.Namumark(namumark.Document(doc.namespace, doc.title, text, force_show_namespace=doc.force_show_namespace))

    parser.paragraphs.sort_level()
        
    link_targets = parser.paragraphs.find_all(type = 'LinkedText', link = target, recursive = True)
    
    for i in link_targets:
        i.link = '봉숭아 학당(개그콘서트)'
    
    new_text = parser.render()
        
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
                namu.edit(str(document), edit_link)
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
    
    for target in targets:
        documents = namu.backlink(target, flag = theseed.BacklinkFlags.link)
        do_edit(documents)

    namu = None