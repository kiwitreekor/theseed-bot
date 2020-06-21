# theseed-bot

the seed 계열을 위한 API 제공.

## 설치
    pip install -r requirements.txt
    python setup.py install

## 사용
    from theseed_bot import theseed

예시 스크립트:

    from theseed_bot import theseed
    
    wiki = theseed.TheSeed('namu.wiki')
    
    print(wiki.raw('나무위키:대문'))

로그인이 필요한 경우, 최소 1회 스크립트를 실행한 뒤 생성되는 config.json에 ID와 비밀번호 입력.

## 지원하는 기능

* no-force-recaptcha를 요구하지 않는 기능
    - 로그인 / 로그아웃
    - 문서 불러오기
    - raw 불러오기
    - 문서 편집
    - 토론 및 편집 요청 목록 불러오기
    - 문서 역사 불러오기
    - 검색
    - 분류에 속한 문서 불러오기
    - 역링크 불러오기
    - 고립된 문서 목록, 분류되지 않은 문서 목록, 작성이 필요한 문서 목록 불러오기
    - ACL 불러오기
    - 토론 불러오기
    - 토론 댓글 남기기

* no-force-recaptcha를 요구하는 기능
    - 편집 요청 생성
    - 문서 이동
    - 문서 삭제