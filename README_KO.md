# Maestro-Prep v0.1 로컬 노드 전달용 후보 패키지

**상태:** `PREP_ONLY / CANDIDATE_ONLY / NON_FINAL`. 선택 구조: **C안(한 개 진입점, Astra-Prep/O-Prep 독립 모듈, Leonardo 분기)**.

이 ZIP에는 O-Prep v0.3의 기존 Python 판단 엔진과 합성 테스트, 새 공통 진입점, 외부 Astra/Leonardo 영수증 계약 및 20개 합성 구조 비교 결과를 포함한다. **공식 Astra-Prep 본문·현재 Leonardo 바이너리·코드베이스·원시 노드 로그·실제 로컬 DB는 포함하지 않는다.** Astra-Prep/Leonardo와 실제 상호 운용했다고 주장하지 않는다.

## 최초 로컬 검증 순서

1. ZIP 해시를 파일의 전달 채널 밖에서 제공받은 값과 비교하고, 격리된 작업 폴더에서 압축 해제한다. 공유/approved 스킬 경로에 곧바로 복사하지 않는다.
2. `python tools/verify_package.py .`로 파일 수·바이트·SHA-256을 검사한다.
3. `python -m maestro_prep.cli component-check`로 vendored O-Prep v0.3 원본의 2개 소스 파일을 다시 해시한다.
4. `python -m unittest discover -s tests -q`와 `python -m unittest discover -s components/o_prep_v0_3/tests -q`를 실행한다.
5. `python tools/replay_simulation.py`로 이전의 20개 **합성** 분기 재생 결과를 확인한다.
6. `integrations/LEONARDO_POLICY.template.json`은 분석용 정책 제안이다. 정책 오너 승인 없이 실제 라우터에 복사하거나 기본값으로 설치하지 않는다.
7. 현재 노드의 공식 Astra-Prep 승인본과 Leonardo 라우터 버전·정책을 *별도로* 검사한다. 상이하면 HOLD하고 코드/정책을 바꿔서 시험 결과를 맞추지 않는다.
8. `examples/synthetic_node/`로 CLI 호출 구조를 재현한 후, 실제 노드에서 권한이 있는 경우에만 새로운 격리 증거 루트에 재수집한다.

## 구성

- `SKILL.md`: S0~S11과 외부 분기 규칙.
- `maestro_prep/`: 로컬 해시·버전·영수증 연결용 읽기 전용 CLI.
- `components/o_prep_v0_3/`: 이미 만든 O-Prep v0.3 결정 엔진·원본 테스트 및 `SOURCE_PIN.json`.
- `adapters/`: 실제 Astra-Prep과 Leonardo의 **외부** 인터페이스 규격(코드나 실행기를 대체하지 않음).
- `integrations/`: 소유자 검토용 최소 라우팅 정책 제안. 원본 Leonardo 정책으로 가장하지 않는다.
- `evidence/`: 기존 20개 합성 비교의 비밀 제거된 요약/재연 결과와 출처 해시. 실제 운영 평가 아님.
- `examples/synthetic_node/`: 모의 파일/해시만으로 재생 가능한 예제.
- `tests/`: 분기·장애·해시·검토 무효화·경로 이탈 등의 합성 테스트.
- `MANIFEST.json`, `SHA256SUMS.txt`, `tools/verify_package.py`: ZIP 내부 무결성.

## 예상 판단

- 새 작업인데 Astra가 누락: `HOLD_INTEGRATION` + `HOLD_PLAN_MODULE_MISSING`.
- 읽기 전용 기존 파일 확인인데 Astra가 누락: `audit-file`을 통한 로컬 검사 가능.
- O-Prep 누락 또는 소스 변경: fail-closed.
- O-Prep 데이터/라우터 출력 SHA 불일치: O-Prep의 `HOLD_SOURCE`가 우선.
- Astra가 있고 준비 영수증이 없으면: `CALL_ASTRA_PREP`(실행하지 않고 담당 노드에 반환).
- 일치하는 현지 증거 + 계획 영수증: `BOUND_CANDIDATE_CHECKS_PASSED`. ***이 상태는 운영 변경 승인 아님.***

## 정보 보호 및 제약

전체 원본을 중앙 채팅, 별도 LLM 또는 다른 노드의 스킬 패키지에 복사하지 않는다. 필요한 파일은 개인 노드의 격리된 evidence 루트에 두고 바이트 수/해시/문제 코드만 보고한다. 최종 설치와 채택은 사용자가 승인한 각 노드 정책 소유자가 결정해야 한다.
