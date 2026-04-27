# Unreal Harness 템플릿

이 폴더는 Unreal Engine 프로젝트에 이식해서 사용하는 `Harness` 템플릿이다.

목표는 두 가지다.

1. 새 프로젝트에 `Harness`를 처음 넣을 때 빠르게 초기화할 수 있게 한다.
2. 이미 `Harness`를 쓰고 있는 프로젝트를 새 템플릿 버전으로 올릴 때, 기존 프로젝트 전용 기록과 설정을 잃지 않게 한다.

## 사용 시나리오

이 템플릿은 아래 같은 요청에 맞춰 사용한다.

- `"이 프로젝트 기준으로 Harness를 초기화해줘"`
- `"새로운 템플릿으로 이식해줘"`
- `"템플릿 버전 업 해서 이식해줘"`

세 요청은 비슷해 보여도 작업 방식이 다르다.

- `초기화`: 아직 `Harness`가 없거나 거의 비어 있을 때 템플릿을 기준으로 새로 세팅한다.
- `이식`: 기존 `Harness`가 있을 때 새 템플릿 구조를 가져오되, 프로젝트 전용 상태와 기록은 보존한다.
- `버전 업 이식`: 기존 `Harness`가 이미 사용 중일 때, 템플릿의 새 구조나 운영 규칙만 반영하고 기존 프로젝트 누적 자산은 최대한 유지한다.

## 1. 초기화 방법

1. Unreal 프로젝트 루트에 템플릿의 `Harness/`를 복사한다.
2. 템플릿의 `HARNESS.md`를 프로젝트 루트에 복사한다.
3. 루트 `AGENTS.md`가 없으면 템플릿의 얇은 `AGENTS.md`를 복사한다.
4. 루트 `AGENTS.md`가 이미 있으면 `HARNESS.md`를 읽으라는 짧은 라우팅 문구만 병합한다.
5. 루트 `README.md`가 없으면 프로젝트용 `README.md`를 만든다.
6. `Harness/config/project.json`을 실제 프로젝트 기준으로 채운다.
7. `Harness/state.md`에 현재 프로젝트 상태를 기록한다.
8. `Harness/next.md`에 다음 작업 후보와 수동 검증 필요 항목을 기록한다.
9. 작업 시작 날짜의 `Harness/cycles/YYYY-MM-DD.md`를 만들고 초기화 내용을 남긴다.

## 2. 새 템플릿으로 이식할 때

사용자가 `"새로운 템플릿으로 이식해줘"`라고 요청하면 기본적으로 아래 원칙으로 처리한다.

### 유지할 것

- 기존 `Harness/state.md`
- 기존 `Harness/next.md` 또는 기존 후속 작업 문서의 의미
- 기존 `Harness/cycles/`
- 기존 `Harness/doc/`
- 프로젝트 전용 `Harness/config/project.json`
- 프로젝트 전용 스크립트
- 프로젝트에서 실제로 쓰는 루트 `AGENTS.md`의 저장소별 규칙
- 프로젝트용 루트 `README.md`

### 새로 가져올 것

- `HARNESS.md`
- `Harness/config/agents.json`
- `Harness/config/cycle_policy.json`
- `Harness/config/README.md`
- `Harness/scripts/build_verify.ps1`
- `Harness/scripts/build_verify.cmd`
- 템플릿 쪽 `HARNESS.md`/`AGENTS.md`의 새 운영 규칙 중 현재 프로젝트에 필요한 부분

### 주의할 것

- 기존 파일을 무조건 템플릿 파일로 덮어쓰지 않는다.
- 프로젝트 전용 검증 마커, 자산 경로, 클래스 경로를 비우지 않는다.
- 기존 작업 기록과 프로젝트 전용 문서를 삭제하지 않는다.
- 구버전 후속 작업 문서가 있다면 바로 삭제하기보다, 먼저 `next.md`로 의미를 옮겼는지 확인한다.

## 3. 템플릿 버전 업 이식 시 고려사항

사용자가 `"템플릿 버전 업 해서 이식해줘"`라고 요청하면, 단순 복사가 아니라 `차이 비교 -> 병합 -> 검증 -> 기록` 흐름으로 간다.

### 먼저 비교할 것

1. 루트 `HARNESS.md`
2. 루트 `AGENTS.md`
3. 루트 `README.md`
4. `Harness/README.md`
5. `Harness/state.md`
6. `Harness/next.md`
7. `Harness/config/project.json`
8. `Harness/config/agents.json`
9. `Harness/config/cycle_policy.json`
10. `Harness/scripts/`

### 병합 원칙

- `state.md`는 템플릿 내용으로 덮지 않고 최신 프로젝트 사실만 유지한다.
- `next.md`는 프로젝트별 후속 작업을 유지하되, 템플릿의 운영 규칙이 바뀌었으면 구조만 반영한다.
- `project.json`은 프로젝트 전용 값이 핵심이므로, 템플릿에서 새 필드가 추가됐을 때만 병합한다.
- 루트 `HARNESS.md`는 Harness 운영 규칙의 기준 파일로 갱신한다.
- 루트 `AGENTS.md`는 가능하면 `HARNESS.md`를 가리키는 얇은 라우터로 유지하고, 저장소 전용 규칙이 이미 있으면 함께 유지한다.
- 루트 `README.md`는 기존 내용을 보존하면서 현재 프로젝트 소개 문서가 되도록 갱신한다.
- 템플릿 버전 업 시 `HARNESS.md`, `Harness/README.md`, `Harness/config/agents.json`, `Harness/config/cycle_policy.json`, `Harness/scripts/`는 갱신 대상이다.
- `Harness/state.md`, `Harness/next.md`, `Harness/cycles/`, `Harness/config/project.json`은 보존 대상이다.

### 특히 놓치기 쉬운 부분

- `Harness/config/project.json`에 새 `build` 필드가 추가됐는지
- `build_verify.*` 같은 새 스크립트가 들어왔는지
- `AGENTS.md`가 `HARNESS.md`를 읽도록 되어 있는지
- 루트 `README.md`가 아예 없거나, 새 운영 흐름을 반영하지 못하고 있는지

### 버전 업 이식 후 정리

- 더 이상 쓰지 않는 구버전 파일은 삭제한다.
- 템플릿 비교용 임시 폴더를 프로젝트 안에 넣었다면, 이식 완료 후 삭제 여부를 확인한다.
- 다만 사용자가 다시 비교할 가능성이 있으면, 바로 지우기 전에 먼저 확인한다.

다른 에이전트에게 맡길 때는 아래처럼 지시한다.

```text
이 템플릿을 기준으로 대상 프로젝트의 Harness를 버전 업해줘.
HARNESS.md와 운영 스크립트/설정은 갱신하고,
Harness/state.md, Harness/next.md, Harness/cycles/, Harness/config/project.json은 보존해줘.
```

## 4. 루트 AGENTS.md 병합 원칙

기존 프로젝트에 루트 `AGENTS.md`가 있으면 그대로 덮어쓰지 말고 아래 항목만 우선 병합한다.

- 작업 전 루트 `HARNESS.md`를 먼저 읽는 규칙
- 사용자가 "사이클", "반복", "최대 N회"처럼 말하면 `HARNESS.md`의 작업 루프와 기록 규칙을 적용하는 규칙
- 프로젝트별 추가 규칙은 기존 `AGENTS.md`에 짧게 유지하는 규칙

## 5. project.json 이식 체크리스트

버전 업 이식 시 최소한 아래 항목은 확인한다.

- `project_name`
- `uproject_file`
- `engine_version`
- `editor_startup_map`
- `harness_level_path`
- `default_game_mode_class`
- `required_classes`
- `required_assets`
- `required_source_markers`
- `required_config_markers`
- `required_uproject_plugins`
- `build.engine_root`
- `build.editor_target_name`
- `build.game_target_name`
- `build.platform`
- `build.configuration`

## 6. 검증 체크리스트

초기화든 이식이든 끝나면 가능한 가장 작은 검증을 한다.

- `Harness/config/project.json` 파싱 확인
- `Harness/scripts/verify_project.py` 실행 가능 여부 확인
- C++ 프로젝트면 `Harness/scripts/build_verify.cmd` 또는 `build_verify.ps1` 확인
- 루트 `AGENTS.md`가 `HARNESS.md`를 읽도록 되어 있는지 확인
- 루트 `HARNESS.md`와 `Harness/README.md`가 실제 현재 구조를 설명하는지 확인
- 루트 `README.md`가 현재 프로젝트 소개 문서로 존재하는지 확인

## 7. 권장 기록 방식

이식 또는 버전 업 작업이 끝나면 아래를 남긴다.

- `Harness/cycles/YYYY-MM-DD.md`: 무엇을 옮겼는지, 무엇을 유지했는지, 무엇을 삭제했는지
- `Harness/state.md`: 현재 `Harness` 구조가 어떤 버전 기준인지
- 필요 시 `Harness/next.md`: 남은 수동 정리나 검증 항목

## 8. 템플릿 사용 시 주의

- 이 템플릿은 프로젝트 설명서가 아니라 작업 운영 템플릿이다.
- 루트 `README.md`는 기존 내용을 보존하면서 현재 프로젝트 기준으로 갱신한다.
- 템플릿을 복사했다고 해서 프로젝트 전용 상태가 자동으로 맞는 것은 아니다.
- 가장 중요한 것은 `기존 프로젝트의 사실을 보존하면서 새 운영 구조만 안전하게 올리는 것`이다.
