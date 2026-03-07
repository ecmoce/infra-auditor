# Contributing to infra-auditor

## 개발 환경 설정

```bash
git clone https://github.com/ecmoce/infra-auditor.git
cd infra-auditor
pip install -e ".[dev,server]"
cd frontend && npm ci && cd ..
```

## 브랜치 전략

- `main`: 안정 브랜치
- `feature/*`: 기능 개발
- `fix/*`: 버그 수정

## 커밋 컨벤션

[Conventional Commits](https://www.conventionalcommits.org/) 형식:

```
feat: 새 기능 추가
fix: 버그 수정
docs: 문서 변경
test: 테스트 추가/수정
ci: CI/CD 변경
refactor: 코드 리팩터링
chore: 기타 변경
```

## 테스트

```bash
# 단위 테스트
make test

# Docker 통합 테스트
make docker-test
```

PR 제출 전 모든 테스트가 통과하는지 확인하세요.

## PR 프로세스

1. `feature/*` 또는 `fix/*` 브랜치 생성
2. 변경 사항 구현 + 테스트 추가
3. `make test` 통과 확인
4. PR 생성 (설명에 관련 이슈 번호 포함)
5. CI 통과 후 리뷰 요청

## 프로젝트 구조

```
infra_auditor/     # Agent: 수집기, 규칙 엔진, CLI
aggregator/        # Aggregator: FastAPI 서버
frontend/          # Frontend: React + TypeScript
tests/             # 테스트
scripts/           # 스크립트 (Docker 테스트 등)
```
