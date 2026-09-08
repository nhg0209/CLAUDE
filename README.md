# RL 논문 아카이브 (Obsidian 볼트)

강화학습 논문을 읽으며 정리한 노트를 담는 **Obsidian 볼트**입니다.
Claude가 원격 세션에서 `.md`를 작성해 push하고, 로컬 Obsidian이 pull로 받아 봅니다.

```
Claude (원격)  ──push──▶  GitHub (RL 브랜치)  ──pull──▶  Obsidian (로컬)
```

---

## 처음 세팅 (한 번만)

### 0. 운영체제별 준비

이 볼트는 **파일명이 한글**이라 OS마다 한 번씩 확인할 게 있습니다.

#### 🪟 Windows

> [!danger] 1순위 — 볼트를 **OneDrive 안에 두지 마세요**
> Windows는 `문서`·`바탕 화면`을 기본으로 OneDrive에 동기화합니다.
> 그 안에 git 저장소 + Obsidian 볼트를 두면 **OneDrive와 git이 같은 파일을 두고 싸웁니다**:
> 파일 잠금으로 pull 실패, `.git` 손상, `RL 지도-DESKTOP-ABC 1.md` 같은 중복 파일.
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

> [!danger] 1순위 — 볼트를 **iCloud Drive 안에 두지 마세요**
> 시스템 설정에서 *"데스크탑 및 문서 폴더"* 동기화가 켜져 있으면 `~/Desktop`·`~/Documents`가 iCloud Drive입니다.
> 거기에 git 저장소를 두면 **`.git`이 깨집니다.** `.git` 안에는 object·ref·lock·log 같은
> 작은 파일 수천 개가 계속 바뀌는데, iCloud는 문서 동기화용이라 이 부하를 감당하지 못합니다.
>
> 실제 보고되는 증상:
> - **iCloud가 `.git` 폴더를 `git 2` 라는 파일로 바꿔버려 저장소가 통째로 죽음**
> - 동시 편집이 없는데도 가짜 merge conflict
> - 업로드 배지가 끝나지 않고 `bird` 프로세스가 CPU를 계속 먹음
>
> → `~/Vaults/` 처럼 **동기화 밖 경로**에 두세요. 백업은 GitHub 원격이 이미 하고 있습니다.

**① Git 확인**

```bash
git --version
```

안 나오면 `xcode-select --install`(Apple 기본 git) 또는 `brew install git`.

**② 한글 파일명 설정** — **macOS에서 가장 중요합니다**

```bash
git config --global core.precomposeunicode true
git config --get core.precomposeunicode      # true 가 나와야 함
```

macOS(HFS+/APFS)는 파일명을 **NFD(자모 분리)** 로 저장하고, Linux·Windows는 **NFC(조합형)** 를 씁니다.
이 볼트는 **파일명이 전부 한글**이라 이 설정이 없으면 같은 파일이
`git status`에 **삭제 + 미추적으로 동시에** 뜨고, pull이 중복 파일을 만듭니다.
git 버전에 따라 clone 시 자동으로 켜지기도 하지만 **전역으로 박아두는 편이 확실합니다.**

**③ Obsidian Git이 "Cannot run Git command"라고 하면 — PATH 문제입니다**

Dock·Finder·Spotlight로 띄운 Obsidian은 `~/.zshrc`를 읽지 않아 **셸 PATH를 물려받지 않습니다.**
그래서 Homebrew git(Apple Silicon `/opt/homebrew/bin/git`, Intel `/usr/local/bin/git`)이 안 보입니다.

→ 플러그인 설정에서 **git 실행 파일 경로를 직접 지정**하세요. 경로는 터미널에서:

```bash
which git
```

Apple 기본 git(`/usr/bin/git`)을 쓰면 이 문제가 나지 않습니다.

> [!note] 안 해도 되는 것
> `core.longpaths` — **Windows 전용**입니다. macOS에서는 설정하지 마세요.

#### 🐧 Linux

별도 설정 없음. `~/Documents`가 클라우드 동기화 대상이 아닌지만 확인하세요.

---

### 1. 볼트 클론

노트를 두고 싶은 위치에서 (Windows는 위 ⚠️대로 **OneDrive 밖**):

```bash
git clone -b RL https://github.com/nhg0209/CLAUDE.git RL-Papers
cd RL-Papers
```

> [!tip] 오프로드 볼트도 있습니다
> 같은 저장소의 **`OFFROAD` 브랜치**에 오프로드 주행 논문 볼트가 따로 있습니다.
> 브랜치가 다르면 **작업 디렉터리도 달라야** 하므로, 같은 폴더에서 브랜치를 갈아타지 말고
> 폴더를 두 개 두거나 `git worktree`를 쓰세요.
>
> macOS / Linux:
> ```bash
> git worktree add ../Offroad-Papers OFFROAD
> ```
> Windows (PowerShell):
> ```powershell
> git worktree add ..\Offroad-Papers OFFROAD
> ```
> Obsidian에서는 **별개의 vault**로 엽니다. 좌하단 vault 스위처로 오갑니다.
> ⚠️ 위키링크는 볼트 경계를 넘지 않습니다.

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
| `docs/` | 기존 문서. `RL_ROADMAP.md` (Stage 1~7 학습 로드맵) |

## 여기서부터 보세요

- **[[프로젝트 스택]]** — 프로젝트 스택 전체 지도. 하드웨어 / 기존 classical 스택 / RL 전환 계획
- **`docs/RL_ROADMAP.md`** — 학습 로드맵. 무엇을 어떤 순서로 볼지
- **[[RL 지도]]** — 논문 계보. 그래프 뷰의 빈 노드가 "다음에 읽을 논문"
- **[[기호 사전]]** — 논문마다 달라지는 표기 대조표
- **[[질문 로그]]** — 지금까지 나온 질문 전체

## 이 볼트의 목표

**RL 사전지식 0 → TM07 리포트**(*Asymmetric SAC + Sim-to-Real*로 E2E 자율주행 레이싱)
수준의 스택을 직접 재현·개선할 수 있는 지점까지.

우선순위 논문 4편: SAC(1801.01290) → SAC v2(1812.05905) → Asymmetric Actor-Critic(1710.06542) → TM07 리포트

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
