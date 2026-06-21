# Progress

사람이 현재 진행 상황을 빠르게 확인하기 위한 한국어 대시보드입니다. 에이전트는 이 파일을 직접 읽지 않습니다.

Harness의 다른 운영 문서는 이식 안정성을 위해 기본적으로 영어로 작성합니다. 이 파일만 사람 확인용으로 한국어를 사용합니다.

**에이전트 갱신 조건:** 사용자가 보이는 동작, 에셋, 레벨, 빌드/설정 동작이 바뀌었거나 사람 확인이 필요한 시점에만 간략히 갱신합니다. 아래 네 섹션과 섹션당 핵심 항목 3개 이내를 유지하고, 새 기록을 계속 덧붙이지 말고 기존 항목을 교체합니다. 기술 세부사항은 `Harness/work/state.md`에, 작업 기록은 `Harness/work/cycles/`에, 남은 일은 `Harness/work/next.md`에 남깁니다.

## 현재 상태

- 4라운드 깐깐한 전체 점검 완료, 총 13개 파일 수정

## 최근 완료

- `build_verify.ps1` 경로 깊이 버그 수정 (4단계 → 3단계, 빌드 스크립트 매번 실패하던 문제)
- `harness_release_check.py`에 `.claude/` 제외 추가 및 프로젝트명 누출 감지 기능 추가
- `harness_unreal_risk.py` `/Public/` 경로 false positive 수정 (문자열 포함 → 경로 컴포넌트 비교)

## 확인 필요

- 없음 (템플릿 전용 점검, UE 에셋/레벨 변경 없음)

## 다음 작업

- 필요 시 `harness_release_check.py --strict` 실행 후 `harness_release_pack.py --write`로 배포 패키지 생성
