# Maestro-Prep 초기 공개 후보 — 비식별화 버전

기본 브랜치는 최초 공개한 공통 진입점의 기능을 유지하며, 운영상의 내부 노드명·비공개 파일 경로·외부에 불필요한 워크플로 정보를 제거했습니다. 현재 진행 중인 차기 버전의 개발 기능은 별도의 검토용 브랜치에 유지합니다.

`python -m maestro_prep.cli component-check`, `python -m unittest discover -s tests -q`, `python tools/public_privacy_check.py`로 공개 소스를 검사할 수 있습니다. 포함된 O-Prep은 **공개용 호환 변형**이며 기존 소유자가 승인한 원본의 해시를 대체하지 않습니다. 실제 라우팅·계획·증거 모듈은 승인된 로컬 설치본을 별도로 확인하고, 이 공개 코드만으로 배포 권한을 인정하지 마십시오.
