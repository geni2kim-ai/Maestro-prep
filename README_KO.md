# Maestro-Prep 초기 공개 후보 — 비식별화 버전

기본 브랜치는 최초 공개한 공통 진입점의 기능을 유지하며, 운영상의 내부 노드명·비공개 파일 경로·외부에 불필요한 워크플로 정보를 제거했습니다. 현재 진행 중인 차기 버전의 개발 기능은 별도의 검토용 브랜치에 유지합니다.

`python -m maestro_prep.cli component-check`, `python -m unittest discover -s tests -q`, `python tools/public_privacy_check.py`로 공개 소스를 검사할 수 있습니다. 포함된 O-Prep은 **공개용 호환 변형**이며 기존 소유자가 승인한 원본의 해시를 대체하지 않습니다. 실제 라우팅·계획·증거 모듈은 승인된 로컬 설치본을 별도로 확인하고, 이 공개 코드만으로 배포 권한을 인정하지 마십시오.

## main 브랜치 검증

[main CI](https://github.com/geni2kim-ai/Maestro-prep/actions/workflows/candidate-ci.yml?query=branch%3Amain)는 초기 공개 버전의 현재 바이트와 합성 테스트를 검사합니다. 별도 드래프트 브랜치의 성공 기록을 main의 검증으로 표시하지 않으며, CI·릴리스 배지는 의도적으로 표시하지 않습니다. 실제 검증은 현재 main 커밋 SHA와 그 커밋의 Actions 실행 결과를 직접 대조해야 합니다. 로컬 실행: `python .github/scripts/main_ci.py` (Python 3.11 또는 3.13). 40개 배포 파일의 manifest는 CI 설정, 이번 feedback 및 후속 evidence 문서를 배포 파일에서 제외합니다. 자세한 경계와 외부 승인 조건은 [검증·리뷰 문서](.github/docs/RELEASE_CI_AND_REVIEW.md)를 참조하세요.
