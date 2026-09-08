# 오프로드 주행 논문 아카이브 (Obsidian 볼트)

**오프로드 자율주행(off-road autonomous driving)** 논문을 읽으며 정리한 노트를 담는 **Obsidian 볼트**입니다.
Claude가 원격 세션에서 `.md`를 작성해 push하고, 로컬 Obsidian이 pull로 받아 봅니다.

```
Claude (원격)  ──push──▶  GitHub (OFFROAD 브랜치)  ──pull──▶  Obsidian (로컬)
```

> [!important] 볼트가 두 개입니다
> 같은 저장소의 **`RL` 브랜치에 RL 논문 볼트**가 따로 있습니다.
> 브랜치가 다르면 **작업 디렉터리도 따로**여야 하므로, 아래처럼 **두 번 클론**합니다.
> Obsidian에서도 **각각 별도 vault로** 엽니다.

---

## 처음 세팅 (한 번만)

### 0. 운영체제별 준비

이 볼트는 **파일명이 한글**이라 OS마다 한 번씩 확인할 게 있습니다.

#### 🪟 Windows

> [!danger] 1순위 — 볼트를 **OneDrive 안에 두지 마세요**
> Windows는 `문서`·`바탕 화면`을 기본으로 OneDrive에 동기화합니다.
> 그 안에 git 저장소 + Obsidian 볼트를 두면 **OneDrive와 git이 같은 파일을 두고 싸웁니다**:
> 파일 잠금으로 pull 실패, `.git` 손상, `오프로드 지도-DESKTOP-ABC 1.md` 같은 중복 파일.
>
> → `C:\Users\<사용자>\Vaults\` 처럼 **동기화 밖 경로**에 두세요.
> OneDrive 폴더인지 헷갈리면 탐색기에서 폴더 아이콘에 ☁️/✔ 표시가 있는지 보면 됩니다.

**① Git 설치** — [Git for Windows](https://git-scm.com/download/win).
설치 후 PowerShell에서 아래가 나와야 Obsidian Git 플러그인이 동작합니다 (플러그인이 시스템 git을 씁니다):

```powershell
git --version
```

**② 한글 파일명 설정** (한 번만, 전역):

```powershell
git config --global core.quotepath false   # git 출력에 한글이 \354\240... 로 안 깨짐
git config --global core.longpaths true    # 260자 경로 제한 해제
```

**③ 터미널** — **Windows Terminal** 또는 **PowerShell 7**을 쓰세요.
구형 `cmd.exe`는 한글 출력이 깨집니다.

> [!note] 안 해도 되는 것
> - `core.precomposeunicode` — **macOS 전용**입니다. Windows에서는 설정하지 마세요
> - 줄바꿈(CRLF) — Git for Windows 기본값(`core.autocrlf=true`) 그대로 두면 됩니다.
>   이 볼트는 **pull이 주 용도**라 CRLF 변환이 충돌을 만들지 않습니다

#### 🍎 macOS

한글 파일명이 자모 분리(`ㅈㅣㄷㅗ`)되는 것을 막습니다:

```bash
git config --global core.precomposeunicode true
```

#### 🐧 Linux

별도 설정 없음.

---

### 1. 볼트 클론

노트를 두고 싶은 위치에서 (Windows는 위 ⚠️대로 **OneDrive 밖**):

```bash
git clone -b OFFROAD https://github.com/nhg0209/CLAUDE.git Offroad-Papers
cd Offroad-Papers
```

RL 볼트를 아직 안 받았다면 **다른 폴더에** 따로:

```bash
git clone -b RL https://github.com/nhg0209/CLAUDE.git RL-Papers
```

> [!tip] 이미 RL 볼트를 클론해 뒀다면
> 같은 폴더에서 브랜치를 갈아타면 **RL 노트가 사라진 것처럼 보입니다** (정상입니다 — 다른 브랜치니까).
> 두 볼트를 동시에 열고 싶으면 위처럼 **폴더를 두 개** 두거나, `git worktree`를 씁니다.
>
> macOS / Linux:
> ```bash
> cd RL-Papers
> git worktree add ../Offroad-Papers OFFROAD
> ```
> Windows (PowerShell):
> ```powershell
> cd C:\Users\<사용자>\Vaults\RL-Papers
> git worktree add ..\Offroad-Papers OFFROAD
> ```
> worktree는 `.git`을 공유하므로 **디스크를 덜 먹고 fetch도 한 번만** 하면 됩니다.
> 대신 폴더 하나를 지울 땐 `git worktree remove`를 써야 합니다.

### 2. Obsidian에서 열기

Obsidian 실행 → **Open folder as vault** → 방금 클론한 `Offroad-Papers` 폴더 선택.
RL 볼트와 **별개의 vault**로 열립니다. 좌하단 vault 스위처로 오갈 수 있습니다.

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

**vault마다 따로 설정해야 합니다.** RL 볼트에서 켠 것이 이쪽에 적용되지 않습니다.

---

## 권장 플러그인

| 플러그인 | 용도 |
|---|---|
| **Obsidian Git** | 필수. 자동 동기화 |
| **Dataview** | frontmatter로 논문 목록 쿼리 (아래 예시) |
| **Excalidraw** | 파이프라인 구조도 손그림 |
| **Zotero Integration** | 논문 서지·PDF 주석 연동 |
| **Latex Suite** | 수식 입력 가속 (RL 볼트만큼은 아니지만 B축에서 쓰임) |

### Dataview 쿼리 예시

아무 노트에나 아래를 넣으면 축별 논문 목록이 생깁니다.

````
```dataview
TABLE 축, 연도, 플랫폼, 이해도
FROM #paper
SORT 연도 DESC
```
````

A축(지형 인지)만 보려면:

````
```dataview
TABLE 연도, 지형, supervision
FROM #paper
WHERE 축 = "A"
SORT 연도 ASC
```
````

아직 안 잡힌 논문만:

````
```dataview
LIST FROM #paper WHERE 이해도 = "🔴"
```
````

---

## 폴더 구조

| 경로 | 용도 |
|---|---|
| `MOC/` | 지도 노트 — [[오프로드 지도]], [[용어 사전]], [[읽기 경로]] |
| `Papers/` | 논문 한 편당 노트 하나 |
| `Concepts/` | 여러 논문이 공유하는 개념 |
| `Questions/` | 질문 로그 색인 |
| `Templates/` | 논문 정리 템플릿 |

## 여기서부터 보세요

- **[[읽기 경로]]** — 뭘 먼저 읽을지. **처음이면 여기부터**
- **[[오프로드 지도]]** — 분야 전체 지도. 세 축의 계보와 검증된 논문 색인
- **[[용어 사전]]** — traversability·slip·CVaR 등 이 분야 표기 대조표
- **[[질문 로그]]** — 지금까지 나온 질문 전체

## 이 볼트의 목표

**연구 주제 탐색.** 특정 시스템을 재현하는 것이 아니라,
오프로드 주행에서 **무엇이 열린 문제인지**를 파악하고 붙을 자리를 정하는 것.

그래서 논문 하나의 완결성보다 **계보와 대조**가 우선입니다.
그래프 뷰의 빈 노드가 "다음에 읽을 논문"입니다.

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
