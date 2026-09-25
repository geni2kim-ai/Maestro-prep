# Astra-Prep 외부 어댑터 계약 (배포 아님)

공식 Astra-Prep 정본은 이 ZIP에 제공되지 않으므로 내용을 재작성하거나 유사 구현으로 위장하지 않는다. 현재 노드가 승인한 `SKILL.md` 실제 SHA-256을 `lock.astra.skill_sha256`에 핀한다. 외부 공식 도구 호출은 기존 Leonardo/Skill Loader가 수행하며 Maestro-Prep은 원본 또는 비밀 프롬프트를 받지 않는다.

Astra가 해당 노드 로컬에서 공식 작업 준비를 완료했다면 외부 어댑터가 `ASTRA_PREP_CAPTURE_V1` 영수증을 별도 생성해 로컬 개인 증거 루트에 저장한다. 필요한 키:

`schema, work_unit, node_id, astra_skill_sha256, plan_sha256, plan_file, status, captured_at_utc`

`status=READY_FOR_LOCAL_CANDIDATE_WORK`는 후보 계획에 한정된다. `plan_file`은 개인 증거 루트 내 상대경로이며 `plan_sha256`은 해당 파일의 SHA-256이다. 운영 승인/실행/서명/릴레이 채택/다른 노드 승인으로 승격되지 않는다. 원본 Astra의 실제 스키마와 다르면 여기서 임의 변환하지 말고 소유자가 별도 매핑을 승인해야 한다.
