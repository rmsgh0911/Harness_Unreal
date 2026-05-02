# CLAUDE.md

이 저장소는 Harness 운영 방식을 사용한다.

작업 전 루트 `HARNESS.md`를 먼저 읽고 따른다.

사용자가 기능 구현, 버그 수정, 검증, 사이클, 반복, 최대 N회, 최대 N사이클 작업을 요청하면 `HARNESS.md`의 작업 루프와 기록 규칙을 적용한다.

## Claude Code 주 작업자 동작

- Codex 없이 Claude Code가 단독 주 작업자로 동작할 수 있다.
- 작업자 전환 기록이 필요하면 `HARNESS.md`의 작업자 전환 규칙을 따른다.
- 새 작업자로 이어받을 때는 긴 이전 대화보다 `Harness/state.md`, `Harness/next.md`, 오늘 `Harness/cycles/`, 현재 `git status/diff`를 우선 읽는다.

## Claude Code 고유 동작

- Plan Mode는 구현 범위가 넓거나 리스크가 있을 때만 사용한다. 단순 수정이나 범위가 명확한 작업은 바로 실행한다.
- 프로젝트 컨텍스트의 정식 기록은 `Harness/state.md`, `Harness/next.md`, `Harness/cycles/`다. Claude 메모리는 보조 수단으로만 사용한다.
- Worktree에서 작업 중이면 파일 경로는 항상 저장소 루트 기준으로 참조한다.

## 프로젝트별 추가 규칙

프로젝트별 추가 규칙이 필요하면 이 파일 아래에 짧게 덧붙인다.
