# Unreal Harness 템플릿

이 저장소는 Codex, Claude Code 같은 AI 에이전트를 Unreal Engine 프로젝트의 주 작업자로 사용할 때 쓰는 Harness 운영 템플릿이다.

에이전트가 직접 따라야 하는 운영 지침은 이식 안정성을 위해 영어로 작성한다. 예를 들어 `HARNESS.md`, `AGENTS.md`, `CLAUDE.md`, `Harness/README.md`, `Harness/config/*.json`은 영어를 기본으로 한다.

반대로 이 루트 `README.md`는 사람이 템플릿을 이해하고 이식할 때 보는 안내 문서이므로 한국어로 작성한다. `Harness/docs/Progress.md`도 사람이 보는 진행 현황판이므로 한국어로 작성한다.

## 빠른 시작

```powershell
# 1. 프로젝트 구조를 스캔하고 project.json 후보를 확인한다.
python Harness/scripts/tools/harness_scan.py --json

# 2. 후보가 명확한 빈 필드를 채운다.
python Harness/scripts/tools/harness_project_fill.py --write

# 3. Harness 구조와 설정을 점검한다.
python Harness/scripts/tools/harness_doctor.py

# 4. 에이전트 작업 시작 전 짧은 브리핑을 확인한다.
python Harness/scripts/tools/harness_context.py
```

- 작업 규칙의 기준 파일은 `HARNESS.md`다.
- 에이전트는 `HARNESS.md`, `Harness/state.md`, `Harness/next.md` 순서로 읽는다.
- 도구 설명은 `Harness/README.md`와 `Harness/scripts/tools/README.md`에 있다.

## 목적

이 템플릿은 두 가지 상황을 지원한다.

1. 새 Unreal 프로젝트에 Harness를 처음 초기화한다.
2. 이미 Harness를 쓰는 프로젝트를 새 템플릿 버전으로 올리되, 프로젝트별 상태, 문서, 스크립트, 기록은 잃지 않는다.

## 사용 요청 예시

사용자는 보통 아래처럼 요청한다.

- `"이 프로젝트 기준으로 Harness를 초기화해줘"`
- `"새로운 템플릿으로 이식해줘"`
- `"템플릿 버전 업 해서 이식해줘"`
- `"이 작업을 최대 10사이클로 개선해줘"`

각 요청의 의미는 조금 다르다.

- `초기화`: 아직 Harness가 없거나 거의 비어 있을 때 새로 세팅한다.
- `이식`: Harness와 비슷한 기존 파일이 있는 프로젝트에 현재 템플릿 구조를 가져온다.
- `템플릿 버전 업 이식`: 기존 Harness 프로젝트에 새 운영 규칙과 도구를 병합한다.

## 초기화 방법

1. Unreal 프로젝트 루트에 `Harness/`를 복사한다.
2. 루트 `HARNESS.md`를 복사한다.
3. 루트 `AGENTS.md`가 없으면 템플릿의 `AGENTS.md`를 복사한다.
4. 루트 `AGENTS.md`가 이미 있으면 `HARNESS.md`를 읽으라는 짧은 라우팅 문구만 병합한다.
5. Claude Code를 사용할 프로젝트라면 `CLAUDE.md`도 복사하거나, 기존 `CLAUDE.md`에 `HARNESS.md` 라우팅 문구만 병합한다.
6. 프로젝트용 루트 `README.md`는 기존 프로젝트 내용을 우선한다.
7. 실제 Unreal 프로젝트 기준으로 `Harness/config/project.json`을 채운다.
8. 프로젝트 문서는 기본적으로 `Harness/docs/`에 둔다. 외부 문서 폴더를 쓸 때만 `Harness/config/docs.json`에 등록한다.
9. `Harness/state.md`에 현재 확인된 프로젝트 상태를 적는다.
10. `Harness/next.md`에 다음 작업과 수동 검증 필요 항목을 적는다.
11. 실제 프로젝트 작업 기록이 필요할 때만 `Harness/cycles/YYYY-MM-DD.md`를 만든다.

## 이식할 때 보존할 것

대상 프로젝트에 이미 Harness가 있다면 아래 항목은 보존한다.

- `Harness/state.md`
- `Harness/next.md` 또는 기존 후속 작업 문서의 의미
- `Harness/cycles/`
- `Harness/docs/`, `ProjectDocs/`, `Docs/`, `DesignDocs/` 같은 프로젝트 문서
- 프로젝트별 `Harness/config/project.json`
- 프로젝트별 `Harness/config/docs.json`
- 프로젝트별 스크립트와 표준 스크립트에 추가된 커스텀 로직
- 루트 `AGENTS.md`, `CLAUDE.md`의 저장소별 규칙
- 프로젝트 루트 `README.md`

템플릿에서 가져오거나 병합할 것은 아래 항목이다.

- `HARNESS.md`
- `AGENTS.md`, `CLAUDE.md`의 Harness 라우팅 문구
- `Harness/config/agents.json`
- `Harness/config/cycle_policy.json`의 새 필드와 정책
- `Harness/config/docs.json`의 새 필드와 정책
- `Harness/config/README.md`
- `Harness/scripts/` 아래 표준 스크립트와 도구
- 템플릿 문서에 추가된 새 운영 규칙

## 이식 시 주의할 점

- 기존 프로젝트 파일을 무조건 덮어쓰지 않는다.
- 프로젝트별 검증 마커, 에셋 경로, 클래스 경로, 문서, 로그를 삭제하지 않는다.
- 구버전 `Harness/doc/`에 의미 있는 문서가 있으면 `Harness/docs/`로 옮기거나 병합하고 `Harness/config/docs.json`을 갱신한다.
- 구버전 후속 작업 문서가 있으면 의미를 `Harness/next.md`로 옮긴 뒤 정리한다.
- 표준 스크립트에 프로젝트별 로직이 들어가 있으면 파일을 통째로 교체하지 말고 의미를 병합한다.

## 이식 감사

구버전 Harness 프로젝트를 새 템플릿으로 올리기 전에는 아래 도구로 보존, 갱신, 정리 대상을 먼저 확인한다.

```powershell
python Harness/scripts/tools/harness_migration_audit.py --target C:\Path\To\Project
```

그다음 아래 항목을 비교한다.

1. 루트 `HARNESS.md`
2. 루트 `AGENTS.md`
3. 루트 `CLAUDE.md`
4. 루트 `README.md`
5. `Harness/README.md`
6. `Harness/state.md`
7. `Harness/next.md`
8. `Harness/config/project.json`
9. `Harness/config/agents.json`
10. `Harness/config/cycle_policy.json`
11. `Harness/config/docs.json`
12. 프로젝트 문서 폴더
13. `Harness/scripts/unreal/`, `Harness/scripts/build/`, `Harness/scripts/tools/`

## 최종 점검

```powershell
python Harness/scripts/tools/harness_doctor.py
python Harness/scripts/tools/harness_verify_all.py
```

템플릿 저장소 자체에서는 `project.json`이 비어 있어도 된다. 실제 Unreal 프로젝트에 이식한 뒤에는 프로젝트 필드를 채우고 다시 점검한다.
