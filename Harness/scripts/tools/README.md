# Harness 도구 보관소

이 폴더는 작업 중 에이전트가 반복 비용을 줄이기 위해 추가하는 작은 CLI 도구를 둔다.

## 추가 기준

- 같은 탐색, 검증, 요약, 기록 작업을 2번 이상 반복할 가능성이 있다.
- 결과가 사람이 읽을 수 있는 짧은 출력이나 JSON으로 명확하게 드러난다.
- 프로젝트 전용 값은 `Harness/config/project.json` 또는 명령행 인자로 분리할 수 있다.
- 기본 실행은 읽기 전용이고, 파일 수정은 명시적 옵션으로만 수행한다.

## 피할 것

- 한 번만 쓸 임시 변환
- 에이전트 판단이 많이 필요한 리팩터링
- Unreal Editor 내부 상태에 강하게 의존해 CLI 검증이 불안정한 작업
- 기존 스크립트 옵션 추가로 충분한 중복 도구

## 등록 규칙

새 도구를 추가하면 `tool_manifest.json`에 아래 정보를 함께 기록한다.

- `name`: 도구 이름
- `path`: 저장소 루트 기준 경로
- `purpose`: 도구가 줄이는 반복 비용
- `inputs`: 주요 입력
- `outputs`: 주요 출력
- `writes_files`: 기본 동작 또는 명시 옵션에서 파일을 쓰는지 여부
- `safe_by_default`: 기본 실행이 읽기 전용이며 실패해도 프로젝트 파일을 망가뜨리지 않는지 여부
- `verify`: 최소 검증 명령

## 권장 형태

```powershell
python Harness/scripts/tools/example_tool.py --help
python Harness/scripts/tools/example_tool.py --json
python Harness/scripts/tools/example_tool.py --write
```

도구는 작게 유지하고, 커지면 목적별로 나눈다.

## 기본 제공 도구

- `harness_context.py`: 작업 시작용 짧은 Harness 브리핑을 출력한다.
- `harness_doctor.py`: Harness 문서, 설정, manifest 일관성을 점검한다.
- `harness_scan.py`: Unreal 프로젝트 구조와 `project.json` 후보를 요약한다.
- `harness_cycle.py`: 사이클 로그 항목을 만들고, `--write`가 있을 때만 기록한다.
- `harness_diff_guard.py`: 변경 파일과 Unreal 위험 신호를 짧게 점검한다.
- `harness_handoff.py`: 다른 에이전트나 새 세션으로 넘길 최소 브리프를 만든다.
- `harness_verify_all.py`: 작업 종료 전 가벼운 표준 검증 묶음을 한 번에 실행한다.
- `harness_migration_audit.py`: 구버전 Harness 프로젝트 이식 전 보존/갱신/정리 항목을 점검한다.
- `harness_doc_check.py`: Harness 문서가 길어지거나 최신 상태와 이력이 섞이는지 점검한다.

예:

```powershell
python Harness/scripts/tools/harness_context.py
python Harness/scripts/tools/harness_doctor.py --json
python Harness/scripts/tools/harness_scan.py --json
python Harness/scripts/tools/harness_cycle.py "입력 수정" --changed "..." --verified "..." --remaining "..."
python Harness/scripts/tools/harness_diff_guard.py
python Harness/scripts/tools/harness_handoff.py --request "락온 기능 보강"
python Harness/scripts/tools/harness_verify_all.py
python Harness/scripts/tools/harness_migration_audit.py --target C:\Path\To\OldProject
python Harness/scripts/tools/harness_doc_check.py --target C:\Path\To\Project
```

Windows에서 `python`이 Microsoft Store 별칭으로 잡히면 실제 Python 3 실행 파일이나 작업 환경의 번들 Python 경로를 사용한다.
