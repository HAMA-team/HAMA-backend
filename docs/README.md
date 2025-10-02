# HAMA Backend 문서 구조

이 디렉터리는 HAMA Backend 프로젝트의 모든 문서를 포함합니다.

---

## 📁 문서 구조

```
docs/
├── README.md                          # 이 파일
├── PRD.md                             # 제품 요구사항 정의 (참조용)
├── progress.md                        # 진행 상황 추적 (계속 업데이트)
│
├── plan/                              # 현재 및 미래 계획
│   ├── next-steps.md                  # ⭐ 다음 단계 계획 (최신)
│   ├── agent-implementation-details.md # 에이전트 구현 상세 (Phase 2 참조)
│   └── data-sources-integration.md    # 데이터 소스 연동 (Phase 2 참조)
│
└── completed/                         # 완료된 문서 아카이브
    └── phase1/                        # Phase 1 완료 문서
        ├── schema.md                  # DB 스키마 설계 (완료)
        ├── setup-database.md          # PostgreSQL 설정 가이드 (완료)
        ├── 에이전트 아키텍쳐.md         # 에이전트 아키텍처 (완료)
        ├── phase1-overview.md         # Phase 1 개요 (완료)
        ├── tech-stack-setup.md        # 기술 스택 설정 (완료)
        └── timeline-phase1.md         # Phase 1 타임라인 (완료)
```

---

## 📚 문서 가이드

### 🔴 현재 작업 중 (읽어야 할 문서)

1. **[next-steps.md](plan/next-steps.md)** ⭐ 최우선
   - 다음 작업 계획
   - E2E 테스트 구현 가이드
   - Phase 2 준비 사항

2. **[progress.md](progress.md)**
   - 현재 진행 상황
   - 완료/미완료 체크리스트
   - 차단 사항

3. **[PRD.md](PRD.md)** (참조용)
   - 제품 요구사항
   - 핵심 기능 정의
   - Out of Scope

### 🟡 Phase 2에서 참조할 문서

4. **[agent-implementation-details.md](plan/agent-implementation-details.md)**
   - 에이전트별 상세 구현 가이드
   - Mock → Real 전환 방법

5. **[data-sources-integration.md](plan/data-sources-integration.md)**
   - pykrx, DART API 연동 방법
   - 데이터 수집 전략

### 🟢 완료된 문서 (아카이브)

6. **[completed/phase1/](completed/phase1/)**
   - Phase 1에서 완료된 모든 문서
   - 참조용으로만 사용
   - 수정 불필요

---

## 🎯 다음 작업

**즉시 실행**:
1. `plan/next-steps.md` 읽기
2. E2E 테스트 구현
3. `progress.md` 업데이트

**추후 작업**:
1. Phase 2 시작 전 `agent-implementation-details.md` 검토
2. 데이터 연동 시 `data-sources-integration.md` 참조

---

## 📝 문서 작성 규칙

### 새 문서 추가 시

1. **현재 작업 계획**: `plan/` 디렉터리에 추가
2. **완료된 문서**: `completed/phase{N}/` 으로 이동
3. **계속 업데이트**: 루트에 유지 (예: progress.md)

### 문서 네이밍

- 계획: `{주제}-plan.md` 또는 `next-steps.md`
- 가이드: `{주제}-guide.md`
- 리포트: `{주제}-report.md`
- 아카이브: 원래 이름 유지

### Markdown 컨벤션

- 제목: `# Title`
- 섹션: `## Section`
- 체크박스: `- [ ] Task` / `- [x] Done`
- 코드블록: ` ```language `
- 강조: `**bold**`, `*italic*`, `⭐ important`

---

## 🔄 업데이트 이력

| 날짜 | 변경 사항 | 담당자 |
|------|-----------|--------|
| 2025-10-02 | 문서 구조 정리 및 아카이브 | Claude |
| 2025-10-01 | Phase 1 문서 완성 | Claude |
| 2025-09-30 | PRD 작성 | Team |

---

## 📮 문서 관련 문의

문서 구조나 내용에 대한 질문은 팀 채널에 문의하세요.

**Happy Coding! 🚀**