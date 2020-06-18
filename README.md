# theseed-bot

the seed 계열을 위한 API 제공.

## 설치
`python setup.py install`

## 사용
`from theseed_bot import theseed`를 추가.

예시 스크립트:

    from theseed_bot import theseed
    
    wiki = theseed.TheSeed('namu.wiki')
    
    print(wiki.raw('나무위키:대문'))
