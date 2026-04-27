# Harness 리뷰

이 폴더는 외부 AI 리뷰에 전달한 컨텍스트와 리뷰 결과를 저장할 때 사용한다.

권장 파일 이름:

```text
YYYY-MM-DD-task-name-cycle-01-review-context.md
YYYY-MM-DD-task-name-cycle-01-gemini-review.md
YYYY-MM-DD-task-name-cycle-02-codex-review.md
```

`cycles/`는 짧게 유지한다. 현재 사실은 `state.md`, 다음 작업은 `next.md`, 리뷰어에게 넘기는 자세한 인수인계 내용은 이 폴더에 둔다.

리뷰 컨텍스트 파일에는 보통 다음 내용을 적는다.

- 작업 목표
- 사이클 번호
- 작업자와 리뷰어
- 변경 파일
- 변경 요약
- 검증 결과
- 알려진 리스크
- 리뷰 요청

한국어 diff나 긴 리뷰 요청은 셸 파이프로 바로 넘기지 말고, UTF-8 리뷰 컨텍스트 파일로 저장한 뒤 그 파일 경로를 외부 리뷰어에게 전달한다. Windows 셸 파이프는 한국어를 다시 인코딩해 외부 CLI에서 깨져 보일 수 있다.

Windows PowerShell에서 이 폴더의 한국어 문서를 읽거나 쓸 때는 가능한 한 `-Encoding UTF8`을 명시한다.

언어:

- 사용자가 한국어로 작업 중이면 리뷰 컨텍스트도 한국어로 작성한다.
- 외부 AI 리뷰 원문은 원문 언어를 유지할 수 있다.
- `state.md`, `next.md`, `cycles/`로 옮기는 요약은 한국어로 작성한다.
- 코드 식별자, 파일 경로, 명령어, 로그, 에러 메시지는 원문을 유지한다.

리뷰 지적사항이 자동으로 `next.md` 항목이 되지는 않는다. 미해결, 의도적으로 보류, 현재 범위 밖, 사람 판단 필요 항목만 `next.md`로 옮긴다.
