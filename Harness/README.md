# Harness 폴더

루트 `HARNESS.md`가 작업 규칙의 기준 파일이다. 이 문서는 `Harness/` 폴더의 역할과 표준 명령만 설명한다.

## 읽는 순서

1. 루트 `HARNESS.md`
2. `Harness/state.md`
3. `Harness/next.md`
4. 오늘 날짜의 `Harness/cycles/YYYY-MM-DD.md`
5. 현재 요청에 필요한 `Source/`, `Config/`, `Content/`, `Plugins/`, `Harness/scripts/` 파일

## 폴더 역할

- `config/project.json`: 프로젝트별 검증 설정
- `config/agents.json`: 지원 작업자와 루트 지시 파일 매핑
- `config/cycle_policy.json`: 단일 작업자 사이클, 기록, 중단 조건
- `state.md`: 최신 확정 상태만 유지
- `next.md`: 남은 작업, 보류 리스크, 사람 판단 필요 항목
- `cycles/`: 날짜별 짧은 작업 기록
- `doc/`: 기획서, 참고 문서, 원본 자료
- `scripts/`: Unreal/Python 기반 검증 또는 설정 보조 스크립트

## 기록 원칙

- `cycles/`는 긴 작업 일지가 아니라 짧은 사이클 로그로 유지한다.
- `state.md`는 누적 작업 일지가 아니며 최신 확정 사실만 둔다.
- `next.md`에는 아직 끝나지 않은 일만 둔다.
- 같은 내용을 `state.md`, `next.md`, `cycles/`에 중복해서 길게 남기지 않는다.

## 검증 도구

- `verify_project.py`: 구조, 클래스, 에셋, 설정, Harness 테스트 레벨 확인
- `create_level.py`: Harness 테스트 레벨 생성 또는 갱신
- `build_verify.ps1`: UBT 기반 빌드 또는 프로젝트 파일 재생성
- `build_verify.cmd`: Windows PowerShell 실행 정책을 우회해 `build_verify.ps1` 실행

`verify_project.py`가 통과해도 C++ 변경이 있으면 가능한 범위에서 실제 빌드 검증을 추가한다.

## 표준 명령

프로젝트 검증:

```powershell
& 'C:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'C:\Path\To\Project\ProjectName.uproject' -run=pythonscript -script='C:\Path\To\Project\Harness\scripts\verify_project.py' -unattended -nop4 -nosplash
```

Harness 테스트 레벨 생성 또는 갱신:

```powershell
& 'C:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'C:\Path\To\Project\ProjectName.uproject' -run=pythonscript -script='C:\Path\To\Project\Harness\scripts\create_level.py' -unattended -nop4 -nosplash
```

C++ 파일 추가 또는 삭제 후 IDE 프로젝트 파일 재생성:

```powershell
& 'C:\Program Files\Epic Games\UE_5.5\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe' -ProjectFiles -Project='C:\Path\To\Project\ProjectName.uproject' -Game -Engine
```

빌드 검증:

```powershell
& 'C:\Path\To\Project\Harness\scripts\build_verify.cmd' -Mode Editor
```
