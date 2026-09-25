# Astra/O-Prep/Leonardo 분리 유지 규칙

이 배포 후보는 외부 승인된 Astra-Prep과 Leonardo를 의도적으로 포함하지 않으며, O-Prep v0.3은 이전 자체 후보 소스 두 개를 `components/o_prep_v0_3/src/`에 **별도 보관한 동일 바이트 복제본**이다. `SOURCE_PIN.json`이 기존 소스의 exact-byte 검사를 수행한다. O-Prep을 별도 버전으로 교체하고자 한다면 새 버전을 side-by-side 보관하고 공식 소스 버전/해시, 입출력 호환성, 신규 부정 테스트, 이전 61개 회귀 검증, 독립 리뷰와 롤백 후 새로운 Maestro-Prep lock을 만든다. 어떤 경우에도 이미 승인된 Astra-Prep/Leonardo 정본에 직접 패치하지 않는다.

이 패키지는 Astra-Prep을 내용 수준에서 병합한 릴리스가 아니다. 공식 정본/검증기가 아직 확보되지 않았으므로 그 부분은 **exact-hash 외부 receipt adapter**로만 연결한다. 실제 운영 통합에 필요한 Astra의 스킬 loader 명세, 라우팅 핀, 실제 수용 조건과 승인자 서명은 노드 소유자 증거 확보 이후에 반영한다.
