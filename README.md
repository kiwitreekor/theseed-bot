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

    # 설정 파일 저장을 위해 필요함
    wiki = None 

더 많은 예시는 example 폴더 참조.

로그인이 필요한 경우, 최소 1회 스크립트를 실행한 뒤 생성되는 config.json에 ID와 비밀번호 입력.

## 설정 파일
기본적으로 터미널이 실행되고 있는 경로에 생성됨.

* general
    * access_interval: 일반적인 접속 시 시간 간격
    * edit_interval: 편집 시 시간 간격
    * confirmed_user_discuss: 사용자 토론이 확인된 시각
    * log_level: 로그 수준
    * log_path: 로그 파일 경로
* member
    * id: ID
    * password: 비밀번호
    * cookies: 쿠키 정보

## 지원하는 기능

* no-force-recaptcha를 요구하지 않는 기능
    - 로그인 / 로그아웃
    - 문서 불러오기
    - raw 불러오기
    - 무작위 문서 불러오기
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
    - 파일 업로드

* no-force-recaptcha를 요구하는 기능
    - 편집 요청 생성
    - 문서 이동
    - 문서 삭제
    - 토론 생성하기