# 작업 목록

## 바로 정렬할 작업

- 이 프로젝트 기준으로 `Harness/config/project.json`을 채운다.
- 실제 Source, Config, 에셋 기준으로 `Harness/state.md`를 갱신한다.
- Git 저장소를 사용할 예정이면 `.gitattributes`의 Git LFS 규칙을 팀 정책에 맞게 확인한다.
- `Harness/scripts/verify_project.py`를 실행하고 필수 검증 항목을 프로젝트 현실에 맞춘다.
- C++ 또는 모듈 작업이 예정되어 있으면 `Harness/scripts/build_verify.ps1`가 실행되도록 `build.engine_root`와 target 이름을 채운다.
- 오늘 날짜의 `Harness/cycles/YYYY-MM-DD.md`를 만들고 초기 Harness 설정 기록을 남긴다.

## 기능 작업

- 작성 필요: 기능 단위로 적고, 반복 지시가 있으면 최대 사이클 수와 성공 기준을 함께 적는다.

## 구조 개선 후보

- 작성 필요: 다음 사이클에서 처리할 후보를 작게 적는다.
- 후보마다 사용자 목표에 어떻게 기여하는지 함께 적는다.
- 로그 문구, 한글 깨짐, 주석, 포맷 정리는 기능 검증이나 디버깅을 막는 경우가 아니면 낮은 우선순위로 둔다.

## 수동 검증

- 작성 필요: 자동화로 확인할 수 없는 PIE 확인 항목을 기록한다.

## 알려진 문제

- 작성 필요
