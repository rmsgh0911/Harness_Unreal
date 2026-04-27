# Unreal Harness 템플릿

이 폴더는 Unreal Engine 프로젝트에 복사해서 쓰는 Harness 템플릿이다.

## 사용 방법

1. 새 Unreal 프로젝트 루트에 이 템플릿의 `Harness/`를 복사한다.
2. 대상 프로젝트에 루트 `AGENTS.md`가 없으면 이 템플릿의 `AGENTS.md`를 복사한다.
3. 대상 프로젝트에 이미 `AGENTS.md`가 있으면 기존 파일을 덮어쓰지 말고 Harness 사용 규칙만 병합한다.
4. 이후 "이 프로젝트 기준으로 Harness를 초기화해줘" 라고 명령한다.
5. `Harness/config/project.json`을 해당 프로젝트 기준으로 수정한다.
6. `Harness/state.md`에 실제 프로젝트 상태를 기록한다.
7. `Harness/next.md`에 다음 작업 후보와 알려진 문제를 기록한다.
8. 필요한 기획서나 참고 문서는 `Harness/doc/`에 넣는다.
9. 작업을 시작한 날짜의 `Harness/cycles/YYYY-MM-DD.md`를 만들고 기록을 시작한다.

## 이식 후 최소 정리

- `project_name`, `uproject_file`을 실제 값으로 바꾼다.
- `editor_startup_map`이 있다면 실제 시작 맵으로 바꾼다.
- `required_classes`, `required_assets`, `required_source_markers`는 처음에는 작게 시작한다.
- `verify_project.py`가 통과할 때까지 검증 기준을 프로젝트 현실에 맞춘다.
- 빌드 검증을 돌릴 예정이면 `build.engine_root`, `build.editor_target_name`, `build.game_target_name`을 실제 프로젝트 기준으로 채운다.
- `create_level.py`의 기본 테스트 배치가 프로젝트 성격에 맞지 않으면 해당 프로젝트에서만 수정한다.

## 권장 운영 방식

- `AGENTS.md`는 범용 Unreal 작업 규칙으로 유지한다.
- `Harness/README.md`는 Harness 운영 방식만 설명한다.
- `Harness/state.md`는 현재 실제 상태만 적는다.
- `Harness/next.md`는 앞으로 할 일과 알려진 문제를 적는다.
- 프로젝트마다 다른 값은 가능한 한 `Harness/config/project.json`에 둔다.

## 기능 구현 루프

기능을 지시하면 기본 흐름은 아래와 같다.

1. 요청과 성공 기준을 짧게 정리한다.
2. 관련 코드와 설정만 읽는다.
3. 최소 변경으로 기능을 구현한다.
4. 가능한 가장 작은 검증을 실행한다.
5. 변경 내용을 Unreal 관점에서 자기 리뷰한다.
6. 안전한 저위험 개선 1건이 있으면 반영한다.
7. `Harness/cycles/YYYY-MM-DD.md`와 `Harness/state.md`에 결과를 남긴다.

## 추천 지시 문장

아래처럼 짧게 말해도 되게 만드는 것이 이 템플릿의 목표다.

- `"이 프로젝트 기준으로 Harness를 초기화해줘."`
- `"장비 UI 만들어줘. 최대 6사이클."`
- `"락온 기능 고쳐줘. 빌드 통과까지 반복해."`
- `"상점 검색창 추가해줘. 성공 기준은 빈 검색어 처리까지. 최대 8사이클."`

지시가 짧아도 되지만, 아래 3개가 있으면 결과가 더 안정적이다.

- 무엇을 만들거나 고칠지
- 최대 몇 사이클까지 허용할지
- 성공 기준이 무엇인지

예:

- `"보스 체력바 HUD 만들어줘. 최대 5사이클. 체력 감소 반영과 빈 상태 처리까지."`

## 검증 원칙

- `verify_project.py`는 구조, 에셋, 클래스, 마커 확인용으로 사용한다.
- 실제 성공 판정은 가능한 한 빌드 검증과 필요한 수동 검증까지 포함한다.
- C++나 모듈 변경이 있으면 `Harness/scripts/build_verify.ps1` 같은 표준 빌드 검증 경로를 먼저 맞춘다.
- `cycles/` 기록은 짧게 유지하고, 최신 상태는 `state.md`로 올린다.
