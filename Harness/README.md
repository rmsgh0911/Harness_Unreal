# Harness

`Harness`는 Unreal Engine 프로젝트에서 에이전트와 사람이 현재 상태를 빠르게 파악하고, 작은 단위로 검증하며, 다음 작업자에게 맥락을 넘기기 위한 운영 폴더다.

이 폴더는 가볍게 유지한다. 프로젝트별 사실은 `state.md`, `next.md`, `cycles/`, `config/project.json`에 둔다. 원본 기획서나 참고 문서는 `doc/`에 둔다.

## 읽는 순서

1. `Harness/README.md`
2. `Harness/state.md`
3. 오늘 날짜의 `Harness/cycles/YYYY-MM-DD.md`
4. `Harness/next.md`
5. 필요한 `Source/`, `Config/`, `Content/`, `Plugins/`, `Harness/scripts/` 파일

## 폴더 역할

- `config/project.json`: Harness 스크립트가 읽는 프로젝트별 설정 파일
- `state.md`: 현재 검증된 프로젝트 상태. 의도보다 실제 코드와 실행 결과를 우선한다.
- `next.md`: 우선순위가 있는 작업 후보와 알려진 문제
- `cycles/`: 날짜별 작업 기록
- `doc/`: 기획서, 참고 문서, 원본 자료
- `scripts/`: Unreal/Python 기반의 작은 검증 또는 설정 보조 스크립트

## 운영 규칙

- `state.md`는 사실 위주로 최신 상태를 유지한다.
- 추측, 후보 작업, 앞으로 할 일은 `next.md`에 적는다.
- 기획 문서와 실제 Source 상태가 다르면 실제 코드와 실행 결과를 우선하고, 차이를 기록한다.
- 스크립트 검증은 작고 명확하게 유지한다.
- Harness 스크립트가 실제 프로젝트 콘텐츠를 수정한다면 스크립트 이름과 문서에서 그 동작을 분명히 알 수 있어야 한다.
- 프로젝트별 상수는 스크립트에 직접 쓰지 말고 가능한 한 `config/project.json`에 둔다.
- `cycles/`는 긴 작업 일지가 아니라 짧은 사이클 로그로 유지한다.
- 최신 상태는 `state.md`, 다음 작업은 `next.md`, 이번 시도 결과는 `cycles/`에 나눠 적는다.

## 기능 작업 사이클

기능 지시를 받으면 아래 순서를 기본값으로 따른다.

1. 요청과 성공 기준을 짧게 정리한다.
2. 관련 코드와 설정만 읽는다.
3. 최소 변경으로 기능을 구현한다.
4. 가능한 가장 작은 검증을 실행한다.
5. 변경 내용을 Unreal 관점에서 자기 리뷰한다.
6. 안전한 저위험 개선 1건이 있으면 반영한다.
7. `cycles/YYYY-MM-DD.md`와 `state.md`에 결과를 남긴다.

기능 구현 후 자동 개선은 항상 작은 범위로만 수행한다. Blueprint 공개 API, Build.cs, 저장 구조, 여러 모듈에 걸친 구조 변경이 필요하면 개선 단계로 처리하지 말고 별도 작업으로 분리한다.

사용자가 "최대 N회 사이클"을 지시하면 위 흐름을 N회까지 반복한다. 첫 사이클은 기능 구현을 우선하고, 이후 사이클은 검증 실패 수정, 자기 리뷰에서 발견한 안전한 개선, 기록 정리를 우선한다. 성공 기준을 만족하거나 안전한 다음 작업이 없으면 N회 전이라도 멈춘다.

반복 사이클은 사소한 정리로 흐르지 않게 관리한다. 후보는 안전성만으로 고르지 말고 사용자 목표에 가까워지는 정도를 함께 본다.

우선순위:

1. 요청된 기능이 실제로 동작하게 만들기
2. 검증 실패 또는 빌드 실패 수정
3. 기능 사용성, 빈 상태, 실패 상태, 입력 처리 보강
4. null 체크, 라이프사이클, delegate 정리 같은 안정성 보강
5. 기록 정리

로그 문구, 한글 깨짐, 주석, 포맷 정리는 현재 기능 검증이나 디버깅을 막는 경우가 아니면 반복 사이클의 주 작업으로 삼지 않는다.

권장 기록 형식:

```markdown
## HH:MM 검색창 구현 사이클

- 요청: 검색창을 만든다. 최대 10회 사이클.
- 사이클: 1/10
- 목표 기여:
- 변경:
- 검증:
- 자기 리뷰:
- 다음 사이클 여부:
```

권장 길이:

- 각 사이클 기록은 5~10줄 안쪽으로 유지한다.
- 같은 설명을 반복해서 적지 않는다.
- 자세한 배경 설명이 필요하면 `state.md` 또는 `doc/`로 올린다.

## 추천 지시 방식

사용자는 아래처럼 짧게 지시하면 된다.

- `"이 프로젝트 기준으로 Harness를 초기화해줘."`
- `"무기 교체 기능 만들어줘. 최대 5사이클."`
- `"조준 오프셋 버그 고쳐줘. 빌드 통과까지 반복."`

더 안정적으로 굴리고 싶으면 아래를 같이 적는다.

- 성공 기준
- 허용 가능한 최대 사이클 수
- 꼭 확인해야 하는 수동 검증 항목

예:

- `"보스전 시작 연출 만들어줘. 최대 6사이클. 레벨 시작 시 카메라 전환과 플레이어 입력 복귀까지 확인."`

## 검증 도구

- `verify_project.py`: 구조, 클래스, 에셋, 설정, Harness 테스트 레벨 확인
- `create_level.py`: Harness 테스트 레벨 생성 또는 갱신
- `build_verify.ps1`: UBT 기반 빌드 또는 프로젝트 파일 재생성

`verify_project.py`가 통과해도 C++ 변경이 있으면 가능한 범위에서 실제 빌드 검증을 추가한다.

## 표준 명령

아래 명령은 로컬 Unreal Engine 설치 경로와 프로젝트 경로에 맞게 조정한다.

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

빌드 검증 스크립트 사용 예:

```powershell
& 'C:\Path\To\Project\Harness\scripts\build_verify.ps1' -Mode Editor
```
