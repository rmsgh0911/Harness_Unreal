# ProjectDocs

이 폴더는 게임 기획서뿐 아니라 시뮬레이션 요구사항, 시스템 명세, UX 흐름, 검증 기준, 프로토타입 회고를 두는 프로젝트 문서 루트다.

Harness는 `Harness/config/docs.json`의 정책에 따라 필요할 때만 이 폴더의 관련 문서를 참고한다.
프로젝트마다 문서 참고 트리거가 다르면 `Harness/config/docs.json`의 `request_hints`를 조정한다.

## 권장 구조

- `Systems/`: 전투, 입력, 상호작용, 시뮬레이션 시스템 명세
- `Scenarios/`: 시뮬레이션 시나리오, 테스트 상황, 레벨 의도
- `UX/`: HUD, 메뉴, 조작 흐름, 사용자 피드백
- `Validation/`: 성공 기준, 수동 검증 체크리스트, 수용 기준
- `References/`: 외부 참고 자료 요약, 회고, 실험 기록

## 문서 지도

프로젝트에 문서를 추가하면 아래에 파일별 역할을 짧게 적는다.

- 작성 필요: `Systems/...`
- 작성 필요: `Scenarios/...`
- 작성 필요: `Validation/...`
