# Harness 폴더

루트 `HARNESS.md`가 작업 규칙의 기준 파일이다. 이 문서는 `Harness/` 폴더의 역할과 표준 명령만 설명한다.

## 읽는 순서

1. 루트 `HARNESS.md`
2. `Harness/state.md`
3. `Harness/next.md`
4. 오늘 날짜의 `Harness/cycles/YYYY-MM-DD.md`
5. 사이클, 반복, 최대 N회, 최대 N사이클 요청이면 `Harness/config/cycle_policy.json`
6. 문서 참고가 필요하면 `Harness/config/docs.json`과 등록된 프로젝트 문서의 관련 항목
7. 현재 요청에 필요한 `Source/`, `Config/`, `Content/`, `Plugins/`, `Harness/scripts/` 파일

## 폴더 역할

- `config/project.json`: 프로젝트별 검증 설정
- `config/agents.json`: 지원 작업자와 루트 지시 파일 매핑
- `config/cycle_policy.json`: 단일 작업자 사이클, 사이클 횟수 해석, 기록, 도구 추가, 중단 조건
- `config/docs.json`: 프로젝트 문서 위치와 필요할 때만 읽는 참조 정책
- `state.md`: 최신 확정 상태만 유지
- `next.md`: 남은 작업, 보류 리스크, 사람 판단 필요 항목
- `cycles/`: 날짜별 짧은 작업 기록
- `scripts/`: Harness 실행 스크립트 루트
- `scripts/unreal/`: Unreal Editor 안에서 실행되는 Python 스크립트
- `scripts/build/`: UBT 빌드와 프로젝트 파일 생성 보조 스크립트
- `scripts/tools/`: 작업 중 반복 비용을 줄이기 위해 에이전트가 추가하는 작은 CLI 도구

## 기록 원칙

- `cycles/`는 긴 작업 일지가 아니라 짧은 사이클 로그로 유지한다.
- `state.md`는 누적 작업 일지가 아니며 최신 확정 사실만 둔다.
- `next.md`에는 아직 끝나지 않은 일만 둔다.
- 같은 내용을 `state.md`, `next.md`, `cycles/`에 중복해서 길게 남기지 않는다.

## 프로젝트 문서

기획서, 구현기준서, 시뮬레이션 시나리오, 검증 기준, 회고 문서는 `Harness/` 안에 두지 않는다.

기본 권장 위치는 루트 `ProjectDocs/`이며, 실제 위치와 읽기 정책은 `Harness/config/docs.json`에 둔다. 에이전트는 사용자가 문서 참고를 요청했거나 작업 의도 확인이 필요할 때만 관련 문서를 읽는다.

## 검증 도구

- `unreal/verify_project.py`: 구조, 클래스, 에셋, 설정, Harness 테스트 레벨 확인
- `unreal/create_level.py`: Harness 테스트 레벨 생성 또는 갱신
- `build/build_verify.ps1`: UBT 기반 빌드 또는 프로젝트 파일 재생성
- `build/build_verify.cmd`: Windows PowerShell 실행 정책을 우회해 `build_verify.ps1` 실행
- `tools/tool_manifest.json`: 에이전트가 추가한 보조 도구 목록과 안전 규칙

`verify_project.py`가 통과해도 C++ 변경이 있으면 가능한 범위에서 실제 빌드 검증을 추가한다.

## 사이클 작업

사용자가 "최대 N사이클"처럼 요청하면 한 사이클은 `구현 또는 개선 -> 최소 검증 -> 자기 리뷰 -> 짧은 기록 -> 계속 여부 판단`을 뜻한다.

최대 횟수는 상한선이다. 성공 기준을 만족하면 더 적은 사이클에서 멈추고, 같은 실패가 반복되거나 예상보다 큰 변경이 필요하면 이유와 다음 선택지를 남긴다.

## 에이전트 추가 도구

작업 중 같은 탐색, 검증, 요약, 기록을 반복하게 되면 에이전트는 `Harness/scripts/tools/` 아래에 작은 CLI 도구를 추가할 수 있다.

기본 제공 도구:

- `harness_context.py`: 작업 시작용 짧은 Harness 브리핑
- `harness_doctor.py`: Harness 구조와 정책 파일 점검
- `harness_docs_check.py`: `ProjectDocs`와 `docs.json`의 문서 발견/읽기 정책 점검
- `harness_scan.py`: Unreal 프로젝트 구조와 `project.json` 후보 요약
- `harness_cycle.py`: 사이클 로그 항목 생성, `--write`가 있을 때만 기록
- `harness_diff_guard.py`: 변경 범위와 Unreal 위험 신호 점검
- `harness_handoff.py`: 새 에이전트 또는 새 세션용 최소 전달 브리프 생성
- `harness_verify_all.py`: 작업 종료 전 표준 경량 검증 묶음 실행
- `harness_migration_audit.py`: 구버전 Harness 이식 전 보존/갱신/정리 항목 점검
- `harness_doc_check.py`: Harness 문서 길이, 구버전 경로, state/이력 혼합 점검

도구 추가 원칙:

- 기본 실행은 읽기 전용으로 둔다.
- 파일 수정은 `--write`, `--apply`, `--update` 같은 명시적 옵션으로만 수행한다.
- 프로젝트 전용 값은 도구 코드에 하드코딩하지 않고 `Harness/config/project.json` 또는 명령행 인자로 받는다.
- 새 도구를 추가하면 `Harness/scripts/tools/tool_manifest.json`에 목적, 입력, 출력, 쓰기 여부, 최소 검증 명령을 기록한다.
- 도구 추가 후 `--help`, dry run, JSON 파싱 확인 등 가능한 가장 작은 검증을 실행한다.

작업 요청이 프로젝트 문서를 참고해야 하는지 애매하면 아래처럼 시작 브리핑에 요청을 함께 넘긴다.

```powershell
python Harness/scripts/tools/harness_context.py --request "시뮬레이션 요구사항 보고 검증 기준 맞춰줘"
```

## 표준 명령

프로젝트 검증:

```powershell
& 'C:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'C:\Path\To\Project\ProjectName.uproject' -run=pythonscript -script='C:\Path\To\Project\Harness\scripts\unreal\verify_project.py' -unattended -nop4 -nosplash
```

Harness 테스트 레벨 생성 또는 갱신:

```powershell
& 'C:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'C:\Path\To\Project\ProjectName.uproject' -run=pythonscript -script='C:\Path\To\Project\Harness\scripts\unreal\create_level.py' -unattended -nop4 -nosplash
```

C++ 파일 추가 또는 삭제 후 IDE 프로젝트 파일 재생성:

```powershell
& 'C:\Program Files\Epic Games\UE_5.5\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe' -ProjectFiles -Project='C:\Path\To\Project\ProjectName.uproject' -Game -Engine
```

빌드 검증:

```powershell
& 'C:\Path\To\Project\Harness\scripts\build\build_verify.cmd' -Mode Editor
```
