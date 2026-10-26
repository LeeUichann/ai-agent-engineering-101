# Week 07-2 작업본

기존 `../week-07`은 보존하고, 이 폴더에서 필수 도전 증거 분석과 추가 코드를 검증한다.
공식 제출 경로는 여전히 `submissions/26520024/week-07/`이다. 아직 덮어쓰기나 push는 하지 않았다.
결과와 한계는 [REPORT.md](REPORT.md), 과정은 [PROCESS.md](PROCESS.md)를 참고한다.

## 추가 내용

- `collect_evidence.py`: 실제 원본 로그의 거래·가격·불일치·회피 사례 분석, 수정 없는 구간 보존.
- `prepare_history.py`: 출처 검증 후 과거 관찰을 새 DB로 가져오기, 기존 기억은 읽기 전용 backup.
- `pricing.py`, `pricing_policy.json`: 실제 품목별 평균 수락가 기반 첫 제안 목표 103/184/269.
- `trade_memory.py`: 과거 사건을 새로운 거래와 구분하고 이름별 최근 관찰 3개를 모델에 전달.
- `replay_avoidance.py`: 실제 과거 목록을 사용하는 선택 재생. 외부 전송 승인 전에는 실행하지 않음.
- 서명, 예산 보호, 최저가 보호, 선택형 RPS 할인은 기존 검증 코드를 재사용했다.

## 환경과 검사

기존 `eraseanything` 기반 week-07 `.venv`를 링크로 재사용한다. 환경을 설치·갱신하지 않는다.
원본과 같은 참가자 신원을 위한 키 링크는 Git에서 제외한다. 키를 출력하거나 새로 만들지 않는다.

저장소 루트에서:

```bash
export CODEX_BIN=/home/uichan/.vscode-server/extensions/openai.chatgpt-26.901.22334-linux-x64/bin/linux-x86_64/codex
submissions/26520024/week-07-2/.venv/bin/python submissions/26520024/week-07-2/run_lab1_checks.py --phase lab2
submissions/26520024/week-07-2/.venv/bin/python scripts/check_week07.py submissions/26520024/week-07-2 --github LeeUichann
```

재현 순서: `collect_evidence.py --label <새-이름>`은 기존 로그를 읽어 새 증거 폴더를 생성한다.
고정된 현재 결과는 `logs/historical-verified/`다. `prepare_history.py`는 이 고정 증거를 검증한다.
`summarize_evidence.py`는 저장된 스냅샷으로 전후 측정표를 다시 계산한다.
공식 테스트는 로컬 규칙 기반 가게와 실제 모델을 사용하지만 공개 시장에 주문을 내지 않는다.
오프라인 테스트는 scripted fixture다. 두 종류를 실제 시장 거래와 혼동하지 않는다.

## tmux에서 운영

먼저 기존 week-07 키트가 실행 중이지 않은지 확인한다. 같은 참가자를 중복 실행하지 않는다.
tmux 안에서 현재 `MARKET_OWNER`를 안전하게 설정한 다음:

```bash
cd /nas/home/uichan/ai-agent-engineering-101
export CODEX_BIN=/home/uichan/.vscode-server/extensions/openai.chatgpt-26.901.22334-linux-x64/bin/linux-x86_64/codex
bash submissions/26520024/week-07-2/start_market.sh
```

시작 스크립트는 인증값·기존 키·환경이 없으면 중단한다. 기존 이름과 키를 사용하므로 시장
실적을 초기화하지 않는다. `Ctrl+B` 후 `D`로 분리하고, 실행 자체를 멈출 때만 `Ctrl+C`를 사용한다.
코드 변경 후에는 키트를 재시작해야 판매자 변경이 반영된다.

## 로그와 제출 주의

`logs/historical/`는 최초 분석, `logs/historical-verified/`는 주문 상관관계를 보강한 분석이다.
첫 분석의 상대 미확인 사건 1건은 채택하지 않는다. 실패·불확실성도 삭제하지 않고 보존했다.
`logs/market-kit.log`는 기존 실제 로그의 약 1MiB 접두 구간이며 전체 파일이 아니다.
원본 약 733MB는 기존 폴더에 그대로 있다. 다른 구간은 `provenance.json`의 바이트 범위와
SHA-256으로 확인한다. 새 키트 실행 시부터 이 작업본 로그에 새 이벤트가 추가된다.

공식 경로 반영 때 `.venv`, `.market`, `*.pem`, 캐시를 복사하거나 커밋하지 않는다.
보존된 실제 시장 증거, 새 소스·정책, 최신 `test-report.json`, 보고서와 검사 로그를 함께 검토한다.
새 폴더의 키 링크를 공식 폴더로 복사하면 자기 자신을 가리킬 수 있으므로 옮기지 않는다.
