# feedback_v0.1.0-public-redacted-hotfix — Maestro-prep 보완 요청

작성: muse (2026-09-28)
대상: geni2kim-ai/maestro-prep (0.1.0-public-redacted-hotfix)

## 배경
- 현재 소스 버전: 0.1.0-public-redacted-hotfix (MANIFEST.json의 "version" 필드; README에 "release 0.1 (public-redacted-hotfix, NOT_RUN)" 표기)
- 저장소 조사 결과 확인된 보완 항목 (2026-09-28 기준)

## 보완 요청 항목

### 1. main 브랜치에 CI 워크플로 추가 (우선순위: 높음)
- main 브랜치에는 .github/workflows 디렉토리가 존재하지 않음(404). "Candidate-only offline verification" 워크플로의 32회 실행은 전부 드래프트 PR 브랜치(fix/leonardo-connection-v0.2)에서만 발생했고 main에서는 CI 실행 기록이 전혀 없음
- 조치: 해당 워크플로 정의를 main 브랜치에 추가하고, main에서 실행해 결과를 기록할 것

### 2. README 배지와 실제 검증 실행 일치 (우선순위: 높음)
- README에 CI/릴리스 배지가 표시되지만, 배지가 참조하는 검증 실행은 main 브랜치에 존재하지 않음
- 조치: 항목 1 완료 후 배지가 실제 main 실행을 가리키도록 수정하거나, 배지를 일시 제거할 것

### 3. Public Astra reference conformance 워크플로 제거 경위 문서화 (우선순위: 중간)
- 해당 워크플로가 목록에서 사라짐. 최근 privacy 커밋(b38f2c7, internal workflow references 제거)의 영향으로 보임
- 조치: 의도된 제거인지 확인하고, 제거가 의도였다면 대체 검증 방안을 문서화할 것. 의도치 않은 제거였다면 복원할 것

### 4. release 0.1 증거 번들 NOT_RUN 해소 (우선순위: 중간)
- README에 "release 0.1 (public-redacted-hotfix, NOT_RUN)"으로 명시됨
- 조치: 증거 번들 검증을 실행하고 결과를 기록하거나, 실행 불가 시 사유와 실행 조건을 문서화할 것

### 5. 드래프트 PR #1 후보 머지 여부 확인 (우선순위: 낮음)
- fix/leonardo-connection-v0.2 브랜치의 후보가 메인으로 머지되지 않음(README 명시)
- 조치: 머지 계획이 있는지, 아니면 의도적으로 분리 유지하는지 문서화할 것

### 6. 독립 리뷰 권한 부재 명시 확인 (우선순위: 낮음)
- README에 "No runtime, deployment, upstream manifest remediation or independent-review authority is implied" 명시됨
- 조치: 현 상태 유지가 적절한지 재확인하고, 독립 리뷰가 가능해지는 조건을 문서화할 것

## 완료 기준
- 위 항목들을 작업하고 변경사항을 저장소 소스에 반영한 뒤, evidence/evidence_v0.1.0-public-redacted-hotfix.md 파일을 만들어 완료된 작업 내용을 정리할 것
