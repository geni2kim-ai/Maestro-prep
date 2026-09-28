# Maestro-prep 소스·워크플로 견고성 점검 R1 — ChatGPT

**검토 성격:** 저장소 소유자 **Genie Kim의 정식 점검 의뢰**에 따라 **ChatGPT**가 직접 수행한 1회 비판적 코드 리뷰 및 경계 조건 확인. F3 체크리스트도 이전에 ChatGPT가 작성했으므로, 이번 결과는 **같은 계열 수행자의 검토**이며 별도 인간·별도 독립 리뷰어에 의한 독립 인증으로 표시하지 않는다.

- 검토 ID: `MAESTRO-PREP-OWNER-CHATGPT-ROBUSTNESS-20260928-R1` (본 보고서 추적용; 소유자가 별도로 발급한 식별자라고 주장하지 않음)
- 소유자: Genie Kim / 저장소: `geni2kim-ai/Maestro-prep` / 브랜치: `main`
- 리뷰 수행자: **ChatGPT** / 수행일: 2026-09-28 / 독립성: `SAME_LINEAGE_NOT_INDEPENDENT`
- 적용 기준: [F3 체크리스트](../.github/docs/RED_TEAM_CHECKLIST_DRAFT.md), Git blob `23bddffc92872b61da929905dfd9acfafeb5564f`
- 최초 검토 main: `4c6a6b0afcc4c64438ddb043cfe60ccfa632b293`
- **조치 후 정확한 소스 커밋:** [`7925339676b224649ba94e88006e48b3c8ef5e91`](https://github.com/geni2kim-ai/Maestro-prep/commit/7925339676b224649ba94e88006e48b3c8ef5e91)
- 최종 `MANIFEST.json`: Git blob `d92492b93d1feb164f5e37b307345c0e709a48b0`, UTF-8 6,962 bytes, 직접 계산한 SHA-256 `2035a8ca8277ff5d741dfc5ef8c0a0949910f7946b7360265aebb2f893e6500a`, 배포 목록 **40개**.
- 증거 수집: 연결된 GitHub App으로 이 저장소의 소스, 워크플로, 체크리스트, 관련 커밋 및 **이 저장소의** Actions 결과만 확인. GitHub-hosted Ubuntu/Windows 검증은 저장소의 푸시 CI가 실행했으며, ChatGPT가 별도 로컬 호스트에서 실행한 결과로 표현하지 않음.
- 제외: 다른 저장소, 외부 서비스·계정, 소유자 로컬 노드, 승인되지 않은 외부 소스·하네스, 실제 배포, 과거 PR 대화 및 캐시·외부 아카이브의 독립 조사는 실시하지 않음.
- 상태: **FINDINGS — 확인된 소스 보완 사항을 수정하고 저장소 내 합성 회귀를 확인한 비최종 보고서**. `candidate_only=true`, `finality=non_final`, `decision_authority=none`, `owner_adjudication=PENDING`.

## 1. 발견 사항 — 심각도 순

| ID | 심각도 | 경계 조건에서 발견한 사실 | 조치와 관찰 |
| --- | --- | --- | --- |
| F-01 | **HIGH** | 기존 현재 파일 개인정보 검사기는 UTF-8로 디코딩되지 않는 바이너리 파일을 건너뛰어, 해당 데이터 안의 ASCII/UTF-16 표식을 보지 않고 검사 통과를 표시할 수 있었다. | `tools/public_privacy_check.py`에 바이너리 내 ASCII 및 UTF-16 LE/BE 양쪽 바이트 정렬 검사, 파일 읽기 실패와 링크의 명시적 실패 처리를 추가. `tests/test_public_privacy_check.py`에 관련 합성 경계 사례 4개를 추가. [커밋 `6e6d283`](https://github.com/geni2kim-ai/Maestro-prep/commit/6e6d283c39ce2cb4e94a01b8b074f9b064ab1aaf). **수정 확인**. 압축·암호화 자료 및 과거 Git 객체의 전체 개인정보 무결성을 뜻하지 않음. |
| F-02 | **MEDIUM** | 외부 레퍼런스 검증 경로는 소유자가 핀한 바이트를 하네스 실행 **전에만** 확인했다. 이후 파일이 계속 변경된 상태여도 후보 영수증 평가를 진행할 수 있는 시간 경계가 남아 있었다. | `.github/scripts/external_conformance_gate.py`에서 소유자 승인 핀·6개 레퍼런스·별도 승인된 하네스 바이트를 하네스 반환 후 다시 확인하고, 변동이 지속되면 결과 기록을 거부하도록 수정. 임시 합성 하네스가 파일을 변경하는 경우의 거부 시험 추가. [커밋 `3e3a333`](https://github.com/geni2kim-ai/Maestro-prep/commit/3e3a333c644af40c545b21b3dc36a2939728e396). **합성 점검 통과**; 불변 호스트 격리를 증명하지는 않음. |
| F-03 | **MEDIUM** | 같은 외부 레퍼런스 경로에서 JSON의 중복 키가 일반 파서에 의해 정규화될 수 있었고, 아카이브 입력에서 특수 파일 유형 및 크기 경계 확인을 명확히 강화할 여지가 있었다. | 중복 키·비유한 JSON 값 거부, JSON·압축 아카이브 크기 제한, 멤버 유형 확인과 경계 조건 회귀를 추가. 검증 영수증은 제한된 크기로 읽고 결과 파일은 배타적으로 생성. 외부 검증 합성 테스트를 기존 4개에서 9개로 확대. **수정 확인**, 승인된 실제 외부 자료의 적합성은 `NOT_RUN`. |
| F-04 | **MEDIUM** | 생성한 릴리스 ZIP을 소유자가 받았을 때, 별도 다이제스트 입력과 모든 멤버의 바이트·고정 메타데이터를 압축 해제 없이 재확인하는 전용 절차가 부족했다. | `.github/scripts/build_release.py`에 `--verify-archive ... --expected-sha256 ...` 읽기 전용 경로 추가. 파일 40개 + 메타데이터 2개, 추가·중복·경로 경계·특수 파일 유형, 실제 ZIP 해시와 checkout 원본 바이트를 검사하는 합성 시험으로 builder 테스트를 3개에서 6개로 확대. [커밋 `34472ec`](https://github.com/geni2kim-ai/Maestro-prep/commit/34472ec2f60ae807b8276de472b80783b34fb95c). **수정 확인**; 사용자가 입력한 다이제스트의 *독립 전달 경로*는 이 도구가 인증하지 못함. |
| F-05 | **MEDIUM** | 기존 CI의 테스트 개수 하한만으로는 예상보다 많은 테스트가 건너뛰어진 경우도 성공 영수증으로 받아들일 수 있었다. | `.github/scripts/main_ci.py`에 OS별 예상 제외 수를 정확히 확인하는 판정과 회계 합성 테스트 3개 추가. 현재 coordinator 테스트 하한을 실제 **34개**에 맞춰 고정. 하한 조정 직후 기존 테스트의 30개 fixture와 불일치하여 [실패 실행 `36369838315`](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36369838315)이 발생했고, fixture를 34개로 수정한 [커밋 `9335106`](https://github.com/geni2kim-ai/Maestro-prep/commit/93351068e01ac1697b787336064791e947f88064) 이후 재검증 성공. **수정 확인**, 과거 실패 기록을 숨기지 않음. |
| F-06 | **LOW** | README의 배지 설명이 실제 main에서 CI가 이미 수행된 후에도 '첫 실행 전'이라는 과거 조건으로 읽힐 수 있어 정확한 현재 커밋과 이전 실행을 구별할 필요가 있었다. | 영문·국문 README를 **배지 미표시 정책 + 정확한 main SHA의 Actions 영수증 확인**으로 수정하고 `MANIFEST.json`·`SHA256SUMS.txt`의 README 핀을 재계산. 검증 문서도 정합화. [커밋 `7925339`](https://github.com/geni2kim-ai/Maestro-prep/commit/7925339676b224649ba94e88006e48b3c8ef5e91). **수정 확인**. |

이번 표의 심각도는 **이 저장소의 현재 코드와 사용 경계에 한정한 우선순위**이며 실제 외부 시스템의 영향이나 발생 여부를 확인한 평가는 아니다.

## 2. F3 체크리스트 RT-01~RT-12 항목별 판정

`PASS`는 기록된 소스·정적 확인·저장소 내부 합성 시험의 범위에서만 사용한다. `FINDINGS`는 실제 코드를 검토해 보완 항목을 식별했다는 뜻이며, 아래의 '수정 확인'은 **수정 후 CI 결과**를 가리킨다. 실제 외부 소유자 절차와 타 수행자 검토는 여기에 포함되지 않는다.

| 항목 | 판정 | 확인한 증거와 한계 |
| --- | --- | --- |
| **RT-01** 소스·분기·실행 계보 | **PASS** | 최초 `4c6a6b0`, 각 수정 커밋, 최종 `7925339`, 해당 main Actions의 `head_sha`와 결과를 대조. 별도 Draft PR의 CI는 main 영수증으로 사용하지 않음. |
| **RT-02** 현재 배포 목록·체크섬 | **PASS (현재 checkout 한정)** | 네 OS/Python 조합에서 40개 manifest/checksum 검사 통과, UTF-8 바이트로 manifest SHA-256 재계산. 검증기 소스의 추가 파일·해시 불일치 거부도 검토. 저장소 자체 CI 외 별도 실물 배포 ZIP/OS 독립 수령은 하지 않음. |
| **RT-03** 수동 릴리스 승인 경계 | **PASS (정적)** | `release.yml`의 main·owner actor·명시적 체크박스, 읽기 전용 권한, 고정된 GitHub action 참조 및 자격증명 비보존 설정 확인. 실제 수동 발동의 승인·거절 동작은 사용하지 않음(`NOT_RUN`). |
| **RT-04** ZIP 조립·멤버 경계 | **FINDINGS → 수정 확인** | ZIP 생성 및 읽기 전용 비교를 분리. 합성 경계 입력에 대한 6개 릴리스 검사와 42개 엔트리·고정 메타데이터·체크섬 조건, 네 플랫폼 CI에서 검증. 승인된 불변 릴리스 아카이브는 생성하지 않음. |
| **RT-05** 독립 다이제스트 출처 | **NOT_RUN** | ZIP의 자체 SHA-256 산출·read-only 대조 기능과 입력 다이제스트 비교 코드는 확인. 소유자 독립 채널 게시 및 다른 채널로 수령한 실제 ZIP 대조는 요청 범위 밖이며 자료 없음. `authenticity=NOT_VERIFIED`. |
| **RT-06** 영수증·아티팩트 계보 | **PASS (저장소 CI)** | 최초 기준 실행 및 변경 단계별 성공/실패 기록을 구분. 최종 source-run의 정확한 SHA와 네 job 완료를 직접 대조. Owner가 수동 생성하는 릴리스 아티팩트의 실제 보관·만료 확인은 `NOT_RUN`. |
| **RT-07** 소유자 핀·하네스 경계 | **FINDINGS → 수정 확인** | 정확한 source SHA 및 6개 파일·하네스 핀 계약 확인. 중복 키, 미승인 값, 바이트 불일치, 실행 후 지속적인 입력 변경의 합성 확인 추가. 소유자가 제공한 실제 핀은 없음; 외부 적합성 `NOT_RUN`. |
| **RT-08** 외부 레퍼런스 멤버·스키마 경계 | **FINDINGS → 수정 확인** | 멤버 목록 중복·경로 역참조·특수 파일 유형·크기 제한 및 JSON 해석 엄격성 보완. 저장소 합성 회귀 9개 통과; 실제 별도 승인 레퍼런스 스키마 적합성은 판정하지 않음. |
| **RT-09** 승인된 하네스의 실제 영수증 | **NOT_RUN** | 합성 코드로 하네스 반환 후 핀 변경 거부는 확인했으나, 소유자가 승인한 실물 레퍼런스·하네스·격리 러너 및 원본 영수증이 없어 실제 수행 여부를 판단하지 않음. |
| **RT-10** 현재 파일 개인정보 경계 | **FINDINGS → 수정 확인** | 바이너리 ASCII 및 BOM 없는 UTF-16 양쪽 정렬 검사, 링크·읽기 실패 명시 처리와 합성 검사 4개 추가. 현 소스 CI privacy 항목 통과. 과거 Git 객체·PR 대화·캐시·다운로드 사본은 **이번 범위 밖 / NOT_RUN**. |
| **RT-11** 권한·승인 표현 경계 | **PASS (소스·문서)** | 공개 호환 변형과 실제 승인 외부 원본을 구분. Owner release, 승인된 외부 conformance, 배포와 독립 리뷰를 모두 별도 게이트로 유지. 실제 호스트·원본 승인·실행 상태를 추정하지 않음. |
| **RT-12** 증거 표현과 실제 커밋 일치 | **FINDINGS → 수정 확인** | README 시간 경계 문구를 수정하고 34개 현재 coordinator 기준과 회귀 fixture를 동기화. 정확한 최종 main SHA·manifest 원시 바이트·네 플랫폼 9개 check receipt를 대조. 본 evidence 자체가 올라간 *다음* 커밋은 별도 CI로 다시 확인해야 함. |

## 3. 조치 커밋 및 검증 계보

| 구분 | 커밋 | 저장소 main CI | 기록 |
| --- | --- | --- | --- |
| 기존 기준 | `4c6a6b0` | [36365729919](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36365729919) | 기존 8개 항목을 각 4개 OS/Python job에서 통과 |
| 현재 파일 검사·CI 경계 | `6e6d283` | [36369493430](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36369493430) | 4/4 job 성공 |
| 외부 핀 해석·실행 전후 확인 | `3e3a333` | [36369613699](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36369613699) | 4/4 job 성공 |
| ZIP 읽기 전용 확인 | `34472ec` | [36369699273](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36369699273) | 4/4 job 성공 |
| 현재 테스트 하한 조정 | `e1be8fc` | [36369838315](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36369838315) | **실패**: CI 회계 합성 fixture가 이전 30개에 머묾 |
| 회계 fixture 정정 | `9335106` | [36369958514](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36369958514) | 4/4 job 성공 |
| README·manifest 정합화 | **`7925339`** | [36370025033](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36370025033) | **최종 source commit: 4/4 job 성공** |

### 최종 소스 `7925339676b224649ba94e88006e48b3c8ef5e91`의 실제 CI 결과

- 실행: [main push `36370025033`](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36370025033), 생성 시각 `2026-09-28T02:29:40Z`, 최종 `completed/success`.
- Ubuntu Python 3.11 job `108764204594`; Ubuntu Python 3.13 job `108764204607`; Windows Python 3.11 job `108764204506`; Windows Python 3.13 job `108764204746` — **4/4 성공**, 각 작업에서 **9/9 검사 항목 통과**.
- 네 작업 모두: 배포 파일 40개 checksum 검사 PASS, 현재 파일 개인정보 검사 PASS, 포함된 공개 호환 구성요소 핀 PASS, coordinator **34개·0건 건너뜀**, 20개 합성 아키텍처 리플레이 일치, ZIP 검사 **6개·0건 건너뜀**, 외부 소스 *합성* 게이트 **9개·0건 건너뜀**, CI 영수증 합성 검사 **3개·0건 건너뜀**.
- 공개 호환 구성요소 시험: 네 작업 모두 61개 수행, Ubuntu 각각 5개, Windows 각각 6개 건너뜀. Windows에서는 POSIX 전용 파일 모드 확인 1건을 추가로 건너뛰며 실제 Windows 호스트 ACL 검사는 `NOT_RUN`. 이 수치를 '61개 전부 실측 PASS'로 표현하지 않음.
- 이 CI 결과는 저장소에서 자동으로 실행한 **작성자 계열 자체 시험** 결과이지, ChatGPT가 별도 통제 환경에서 직접 실행했거나 외부 독립 수행자가 검증한 결과라고 주장하지 않음.

## 4. 잔여 조건과 판정 한계

1. `release.yml`의 Owner 수동 생성 실행, 완성된 릴리스 ZIP의 별도 채널 다이제스트 수령·대조: **NOT_RUN / NOT_VERIFIED**. 읽기 전용 ZIP 검사기에 동일 채널에서 복사한 값을 넣는 행위만으로 출처 독립성이 생기지 않음.
2. 소유자의 실제 외부 원본 6개 및 승인 하네스의 정확한 핀·격리 실행, 원시 관찰 기록: **NOT_PROVIDED / NOT_RUN**. 합성 시험 통과를 실제 conformance 판정으로 승격하지 않음.
3. 과거 Git/Actions 기록·캐시·외부 사본의 개인정보 확인, 로컬 노드/실제 서비스 및 다른 계정의 점검: **이번 의뢰 범위 밖 / NOT_RUN**. 저장소의 현재 파일 검사기는 해당 항목을 인증하지 않음.
4. 별도 독립 검토 수행자 지정, 그 수행자의 판정·원시 자료와 소유자 최종 수용 판단: **NOT_RUN / PENDING**. 정식 점검 의뢰에 따라 **ChatGPT가 이 리뷰를 수행**했지만, 기존 체크리스트의 작성자 역시 ChatGPT이므로 독립 리뷰 완료로 표기하지 않음.

**이번 작업의 결론:** 소스·워크플로에서 확인한 우선 조치 항목을 main에 반영하고 정확한 최종 소스의 4개 OS/Python CI를 확인한 `FINDINGS_WITH_REMEDIATION` 보고서. 외부 진위성·운영 승인·배포·독립 리뷰 완료를 승인하거나 암시하지 않으며 `candidate_only=true`, `non_final`, `decision_authority=none`을 유지한다. 이 보고서만 추가하는 후속 커밋은 40개 배포 파일 목록 밖에 있으며, 별도 정확한 커밋 CI 결과를 확인한 후에만 보고서 게시 커밋 자체의 성공을 서술한다.
