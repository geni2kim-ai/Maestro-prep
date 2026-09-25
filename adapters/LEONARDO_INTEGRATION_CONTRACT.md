# Leonardo 외부 라우터 캡처 계약 (실행기 아님)

실제 Leonardo는 각 노드가 승인한 설치·정책으로 **별도로** 실행한다. 결과와 입력/정책/출력 파일을 해당 노드의 격리된 증거 루트에 보관하고 O-Prep v0.3 receipt index의 `router_input`, `router_policy`, `router_output`으로 해시 결합한다.

추가 `LEONARDO_ROUTE_CAPTURE_V1` 필드:
`schema, work_unit, node_id, router_version, task_sha256, policy_sha256, routing_output_sha256, exit_code, execution_state, captured_at_utc`.

모든 해시는 **실제 파일 바이트**에 대해 계산하고 `MAESTRO_PREP_LOCK_V1`의 승인 버전·정책 해시와 일치해야 한다. `READY`와 종료 코드 0을 기록하더라도 동일 프로세스 실행 영수증, 생산자 신원/정책 권한을 독립적으로 인증할 수 없으므로 `LOCAL_BYTES_ONLY_PRODUCER_RECEIPTS` 이상의 신뢰 등급으로 자동 승격하지 않는다. 미실행은 `NOT_RUN`으로 남긴다. 다른 노드의 라우터 영수증 재사용 금지.
