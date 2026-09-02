# RL 논문 아카이브 (Obsidian 볼트)

강화학습 논문을 읽으며 정리한 노트를 담는 **Obsidian 볼트**입니다.
Claude가 원격 세션에서 `.md`를 작성해 push하고, 로컬 Obsidian이 pull로 받아 봅니다.

```
Claude (원격)  ──push──▶  GitHub (RL 브랜치)  ──pull──▶  Obsidian (로컬)
```

---

## 처음 세팅 (한 번만)

### 1. 볼트 클론

노트를 두고 싶은 위치에서:

```bash
git clone -b RL https://github.com/nhg0209/CLAUDE.git RL-Papers
cd RL-Papers
```

> **macOS 사용자**: 한글 파일명이 자모 분리되는 것을 막으려면
> ```bash
> git config core.precomposeunicode true
> ```

### 2. Obsidian에서 열기

Obsidian 실행 → **Open folder as vault** → 방금 클론한 `RL-Papers` 폴더 선택

### 3. Obsidian Git 플러그인 (자동 pull)

이걸 설정해야 Claude가 push한 내용이 알아서 내려옵니다.

1. **Settings → Community plugins → Turn on community plugins**
2. **Browse** → `Obsidian Git` 검색 → Install → Enable
3. 플러그인 설정에서:

| 항목 | 값 |
|---|---|
| Auto pull interval (minutes) | `5` |
| Pull updates on startup | ✅ 켜기 |
| Auto backup after file change | ❌ 끄기 (내 수정과 Claude push가 충돌할 수 있음) |

이제 5분마다 자동으로 pull됩니다. 즉시 받고 싶으면 `Ctrl/Cmd+P` → `Git: Pull`.

---

## 권장 플러그인

| 플러그인 | 용도 |
|---|---|
| **Obsidian Git** | 필수. 자동 동기화 |
| **Latex Suite** | 수식 입력 가속 — RL 노트에서 체감이 큼 |
| **Dataview** | frontmatter로 논문 목록 쿼리 (아래 예시) |
| **Excalidraw** | 알고리즘 구조도 손그림 |
| **Zotero Integration** | 논문 서지·PDF 주석 연동 |

### Dataview 쿼리 예시

아무 노트에나 아래를 넣으면 논문 목록 테이블이 생깁니다.

````
```dataview
TABLE 계열, 연도, 이해도, 상태
FROM #paper
SORT 연도 DESC
```
````

아직 안 잡힌 논문만 보려면:

````
```dataview
LIST FROM #paper WHERE 이해도 = "🔴"
```
````

---

## 폴더 구조

| 경로 | 용도 |
|---|---|
| `MOC/` | 지도 노트 — [[RL 지도]], [[기호 사전]] |
| `Papers/` | 논문 한 편당 노트 하나 |
| `Concepts/` | 여러 논문이 공유하는 개념 |
| `Questions/` | 질문 로그 색인 |
| `Templates/` | 논문 정리 템플릿 |

## 여기서부터 보세요

- **[[RL 지도]]** — 전체 계보. 그래프 뷰의 빈 노드가 "다음에 읽을 논문"
- **[[기호 사전]]** — 논문마다 달라지는 표기 대조표
- **[[질문 로그]]** — 지금까지 나온 질문 전체

---

## 충돌이 났을 때

내가 로컬에서 노트를 고쳤는데 Claude도 같은 파일을 고쳤다면 pull이 실패합니다.

```bash
git stash          # 내 수정 잠시 치우기
git pull
git stash pop      # 되돌리고 충돌 부분 수동 병합
```

**예방**: 내가 직접 고칠 노트는 Claude에게 미리 알려주세요. 그 파일은 건드리지 않겠습니다.

## PDF에 대해

`.gitignore`가 `*.pdf`를 제외합니다. 저장소 용량을 지키기 위해서입니다.
논문 PDF도 함께 관리하고 싶으면 `.gitignore`에서 해당 줄을 지우세요.
