# Follow-up feedback — v0.1.0-public-redacted-hotfix

1라운드 evidence(v0.1.0-public-redacted-hotfix) 비판적 재검토 결과, 6개 항목 중 3개는 실질 해결됐고 3개는 정직한 경계 표기(NOT_RUN / NOT_GRANTED)로 끝났다.
아래 3개는 ChatGPT가 실행 가능하므로 후속 라운드에서 작업한다.

원칙: 실행을 가장하지 않는다. 권한 밖 작업은 owner의 트리거/승인 게이트를 두고, 자신이 "완료했다"고 주장하지 않는다.

## F1. release 0.1 증거 번들 — 실행 가능한 다음 단계
- workflow_dispatch 트리거 기반 `.github/workflows/release.yml` 초안을 작성한다.
- 릴리스 워크플로는 40-file ZIP + SHA256SUMS를 생성하고 아티팩트로 첨부해야 한다.
- owner가 수동으로 트리거하고, 다이제스트를 별도 채널에 게시하면 owner가 대조한다.
- ChatGPT는 아카이브 진위성을 "주장"하지 않는다. 불변 release ZIP 조립·독립 채널 다이제스트 게시 전까지는 NOT_RUN 표기를 유지한다.

## F2. 외부 레퍼런스 conformance — 초안 + 핀 요청
- conformance job 초안을 작성한다. 단, owner가 승인한 외부 소스 바이트·프로파일/스키마/해시 핀이 전제 조건이다.
- 핀이 아직 제공되지 않았다면, owner에게 필요한 핀의 구체적 목록을 요청한다.
- 핀 제공·owner 실행 승인 전까지는 NOT_RUN을 유지한다.

## F3. red-team 체크리스트 — 초안만, 수행은 별도 리뷰어
- red-team 체크리스트 문서 초안만 작성한다.
- ChatGPT 자신이 체크리스트를 "수행"하는 것은 독립 리뷰가 아님을 문서에 명시한다.
- 실제 수행·판정 기록은 별도 리뷰어(다른 에이전트 또는 인간)가 보관한다.

## 완료 조건
위 3개를 모두 수행하고 `evidence/evidence_v0.1.0-public-redacted-hotfix_followup.md` 파일을 만들어 완료 내용을 정리한다.
시작하기 전에 이 feedback 파일을 읽었다는 것을 먼저 확인한다.
