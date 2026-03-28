# 🧴 Skinny — AI 기반 개인화 스킨케어 솔루션

> "좋은 성분을 찾는 것보다, 위험한 조합을 피하는 것이 더 중요하다"

피부 타입 기반 **성분 충돌 검증(Rule-based Validation)** 과 **RAG 기반 AI 추천**을 결합해,  
안전한 스킨케어 제품 선택을 돕는 백엔드 서비스입니다.

📄 [상세 설계 및 의사결정 기록 → Notion 포트폴리오](https://spiffy-plough-ddf.notion.site/AI-3034f89bc5e180f79176fe0b706f9628)

---

## 🗂 목차

- [프로젝트 배경](#프로젝트-배경)
- [기술 스택](#기술-스택)
- [시스템 아키텍처](#시스템-아키텍처)
- [핵심 설계: 3-Layer Validation Engine](#핵심-설계-3-layer-validation-engine)
- [주요 기능](#주요-기능)
- [트러블슈팅](#트러블슈팅)
- [테스트](#테스트)
- [실행 방법](#실행-방법)

---

## 프로젝트 배경

팀 프로젝트로 처음 개발했을 때의 구조는 단순했습니다.  
사용자 피부 고민을 프롬프트에 넣고 LLM이 제품을 추천하는 방식이었습니다.

실사용자 50명 운영 후 인터뷰(n=15)에서 3가지 문제가 반복됐습니다.

| 문제 | 원인 |
|---|---|
| 같은 입력인데 추천 결과가 달라짐 | LLM의 비결정적 특성 |
| 잘못된 성분 정보가 답변됨 | 검증 레이어 없이 LLM 결과를 그대로 전달 |
| 동시 요청 시 응답 불안정 | 모든 요청이 LLM 호출로 이어지는 단일 의존 구조 |

문제는 기능이 아니라 **구조**에 있었습니다.  
이를 바탕으로 **Validation 중심 구조**로 단독 리팩토링을 진행했습니다.

---

## 기술 스택

| 분류 | 기술 | 선택 이유 |
|---|---|---|
| Framework | FastAPI | RAG·OCR 등 Python 생태계 활용, 비동기 처리로 LLM I/O 대기 효율화 |
| Database | PostgreSQL | 성분·사용자·제품 간 관계형 데이터 정합성 관리 |
| Cache | Redis | 동일 피부코드+고민 조합의 중복 LLM 호출 차단 |
| Vector DB | Pinecone | RAG 파이프라인의 성분 Knowledge Base 검색 |
| AI | Claude API | RAG 기반 근거 있는 성분 설명 생성 |
| OCR | External OCR API | 핵심 흐름 검증 우선, 이후 오픈소스 전환 가능하도록 추상화 |
| Infra | Docker | 개발·운영 환경 일관성 확보 |
| Test | Pytest | 49개 테스트로 핵심 비즈니스 규칙 고정 |

---

## 시스템 아키텍처

```
OCR → 성분 파싱 → Validation Engine → RAG 기반 설명 → 추천 결과
```

**Validation Engine을 추천 파이프라인 앞에 배치한 이유:**  
LLM은 성분 충돌 여부를 매번 일관되게 판단하지 못합니다.  
Rule-based Validation으로 위험 후보를 사전 차단한 뒤 LLM이 개입하도록 해,  
안전성을 구조적으로 보장합니다.

![System Architecture](./docs/architecture.png)

---

## 핵심 설계: 3-Layer Validation Engine

LLM에게 안전 판단을 맡기지 않는 것이 이 프로젝트의 핵심 원칙입니다.

| 레이어 | 검증 내용 | 적용 범위 |
|---|---|---|
| Layer 1 | 성분 쌍 충돌 검사 | 모든 사용자 |
| Layer 2 | 개인 회피 성분 경고 | 로그인 사용자 |
| Layer 3 | 피부 타입 기반 경고 | 로그인 사용자 |

**설계에서 신경 쓴 것:**

- `(A, B)`와 `(B, A)` 중복 저장 방지 → `ingredient_a_id < ingredient_b_id` 조건으로 저장 방향 고정
- OCR 스캔과 수동 입력 모두 동일한 ValidationService를 거치도록 설계 → 입력 경로에 관계없이 일관된 검증 결과 보장
- 트러블 로그 기반 회피 성분은 `suggested_avoid_ingredients`로 먼저 제안 후, 사용자 confirm 시에만 등록 → 오탐으로 인한 잘못된 필터링 방지

---

## 주요 기능

### OCR 기반 성분 스캔
화장품 라벨 이미지 → OCR 텍스트 추출 → INCI명/alias 정규화 → Validation Engine 전달  
실이미지 기준 OCR → scan API → 성분 매핑까지 검증 완료

**성분 정규화를 별도 레이어로 분리한 이유:**  
OCR과 검증 로직의 책임을 분리하고, 스캔/수동 입력/검색 등 여러 경로에서 동일한 정규화 규칙을 재사용하기 위해서입니다.

### 트러블 로그 기반 개인화
반복 트러블 성분 자동 감지 → 회피 성분 후보 제안 → 사용자 confirm → Validation Layer 2 반영  
트러블 로그는 soft delete로 관리해 분석 이력 보존

### RAG 파이프라인 *(설계 완료, 구현 진행 중)*
```
User Query → Vector Search (Pinecone) → Knowledge Retrieval → LLM Generation (Claude)
```
LLM이 성분 정보를 직접 생성하지 않고 Knowledge Base 기반으로 답하도록 해 Hallucination을 구조적으로 억제합니다.

---

## 트러블슈팅

| 문제 | 태그 | 상태 |
|---|---|---|
| 추천 필터가 너무 공격적으로 동작하던 문제 | Validation, 비즈니스 규칙, 테스트 | ✅ 해결 완료 |
| RAG에서 근거 없는 설명이 생성될 수 있는 문제 | LLM, RAG, 예외처리 | ✅ 해결 완료 |

📄 [상세 트러블슈팅 내용 → Notion 포트폴리오](https://spiffy-plough-ddf.notion.site/AI-3034f89bc5e180f79176fe0b706f9628)

---

## 테스트

```bash
pytest
```

Pytest 기반 **49개 테스트**로 핵심 비즈니스 규칙을 고정합니다.

| 계층 | 검증 내용 |
|---|---|
| Core | alias 처리, 충돌 쌍 조회, OCR 노이즈 엣지 케이스 |
| Service | Validation 레이어 통합, 추천 fallback |
| Repository | DB 쿼리 정합성 |
| API | 엔드포인트 응답 형식 |

정책 수정 시 발생할 수 있는 회귀 오류를 사전에 방지하는 것이 목표입니다.

---

## 실행 방법

```bash
# 1. 저장소 클론
git clone https://github.com/SKi1NNY/ski1nny_server.git
cd ski1nny_server

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 및 DB 정보 입력

# 3. Docker로 실행
docker-compose up -d

# 4. 테스트 실행
pytest
```

---

> 개발 기간: 2026.03 ~ 진행 중  
> 개인 프로젝트 (팀 프로젝트 리팩토링)