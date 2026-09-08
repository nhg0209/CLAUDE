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

### 3. Obsidian Git 플러그인

Claude가 push한 것이 알아서 내려오게 하는 부분입니다.

1. **Settings → Community plugins → Turn on community plugins**
2. **Browse** → `Obsidian Git` 검색 → Install → Enable

> [!warning] vault마다 따로 설치·설정해야 합니다
> 한쪽 볼트에서 켠 것이 다른 쪽에 적용되지 않습니다. 두 볼트 모두에서 반복하세요.

#### 3-1. 설정값 — 두 모드 중 하나를 고르세요

설정 화면의 **섹션 이름 → 항목 이름** 순으로 적었습니다.

**모드 A. 읽기 위주** — Claude가 쓰고 나는 읽는다 (권장 기본)

| 섹션 → 항목 | 값 |
|---|---|
| Pull → **Pull on startup** | ✅ |
| Automatic → **Auto pull interval (minutes)** | `5` |
| Automatic → **Auto commit-and-sync interval (minutes)** | `0` (끔) |

내가 노트를 고쳤을 때만 `Ctrl/Cmd+P` → **`Git: Commit-and-sync`** 를 직접 실행합니다.
**충돌이 날 여지가 가장 적습니다.**

**모드 B. 나도 자주 쓴다** — 양방향 자동

| 섹션 → 항목 | 값 | 이유 |
|---|---|---|
| Pull → **Pull on startup** | ✅ | |
| Automatic → **Auto pull interval (minutes)** | `5` | |
| Automatic → **Auto commit-and-sync interval (minutes)** | `10` | 너무 짧으면 커밋이 지저분해집니다 |
| Automatic → **Auto commit-and-sync after stopping file edits** | ✅ | 타이핑 도중에 커밋하지 않게 |
| Commit-and-sync → **Push on commit-and-sync** | ✅ | |
| Commit-and-sync → **Pull on commit-and-sync** | ✅ | **⚠️ 필수** — 아래 참조 |

> [!danger] 모드 B에서 **Pull on commit-and-sync**를 반드시 켜세요
> Claude가 원격에 커밋을 먼저 올려두면 내 push는 **non-fast-forward로 거부**됩니다.
> 이 옵션이 켜져 있으면 push 전에 pull을 먼저 해서 자동으로 풀립니다.
> 안 켜두면 *"밀리는데 이유를 모르겠는"* 상태가 됩니다.

> [!note] 예전 이름과 다릅니다
> 플러그인이 **"Backup" → "Commit-and-sync"** 로 용어를 바꿨습니다.
> 오래된 블로그 글의 `Vault backup interval`·`Auto backup after file change`는
> 지금의 `Auto commit-and-sync interval`·`Auto commit-and-sync after stopping file edits`입니다.

#### 3-2. 인증

**push하려면 필요합니다.** 저장소가 private이면 pull에도 필요합니다.

OS 자격증명 관리자에 맡기는 게 가장 간단합니다 (Windows는 Git Credential Manager가 기본,
macOS는 keychain). 그게 안 되면 플러그인에서 직접:

- Authentication/commit author → **Username on your git server** = `nhg0209`
- Authentication/commit author → **Password/Personal access token** = GitHub PAT
  (GitHub → Settings → Developer settings → Personal access tokens, `repo` 권한)

커밋 작성자를 구분하고 싶으면 같은 섹션의 **Author name for commit** / **Author email for commit**.

> [!tip] PAT는 저장소에 올라가지 않습니다
> 플러그인 설정은 `.obsidian/plugins/obsidian-git/data.json`에 저장되는데,
> 이 볼트의 `.gitignore`가 `.obsidian/plugins/`를 통째로 제외합니다.

#### 3-3. 자주 쓰는 명령 (`Ctrl/Cmd+P`)

| 명령 | 용도 |
|---|---|
| **`Git: Pull`** | 즉시 받기. 이것만 알아도 됩니다 |
| **`Git: Commit-and-sync`** | 내 수정을 커밋 + push |
| **`Git: Open source control view`** | 변경된 파일 확인·스테이징 (사이드바) |
| **`Git: Open history view`** | 커밋 히스토리 |

#### 3-4. 안 될 때

| 증상 | 해결 |
|---|---|
| **"Cannot run Git command"** | git 실행 파일을 못 찾는 것. Advanced → **Custom Git binary path** 에 `which git`(mac) / `where.exe git`(Windows) 결과를 그대로 넣습니다. 또는 Advanced → **Additional PATH environment variable paths** 에 `/opt/homebrew/bin` 추가 후 **Reload with new environment variables** 실행 |
| **알림이 너무 잦다** | Miscellaneous → **Hide notifications for no changes** ✅, **Disable informative notifications** ✅ |
| **충돌** | Pull → **Merge strategy on conflicts** 확인 후, 아래 「충돌이 났을 때」 절 |
| **이 기기에서만 끄고 싶다** | Advanced → **Disable on this device** (이 설정은 다른 기기로 전파되지 않습니다) |

> [!tip] 잘 되고 있는지 확인
> 상태 표시줄에 브랜치 이름이 뜹니다 (Miscellaneous → **Show branch status bar**).
> 이 볼트라면 `OFFROAD`, RL 볼트라면 `RL`이 떠야 정상입니다.
> **다른 이름이 떠 있으면 볼트를 잘못 연 것입니다.**
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
| `MOC/` | 지도 노트 — [[오프로드 지도]], [[용어 사전]] |
| `Papers/` | 논문 한 편당 노트 하나 |
| `Concepts/` | 여러 논문이 공유하는 개념 |
| `Questions/` | 질문 로그 색인 |
| `Templates/` | 논문 정리 템플릿 |

## 여기서부터 보세요

- **[[오프로드 지도]]** — 세 축별 논문 **색인**. 서지 정보만 있고 내용은 비어 있습니다
- **[[용어 사전]]** — traversability·slip·CVaR 등 이 분야 표기 대조표
- **[[질문 로그]]** — 지금까지 나온 질문 전체

## 이 볼트의 목표

**연구 주제 탐색.** 특정 시스템을 재현하는 것이 아니라,
오프로드 주행에서 **무엇이 열린 문제인지**를 파악하고 붙을 자리를 정하는 것.

> [!important] 읽은 것만 적습니다
> 「오프로드 지도」는 지금 **색인**입니다 — 논문의 제목·저자·연도·arXiv만 있습니다.
> 내용·해석·계보는 **세션에서 실제로 읽은 뒤에** 채웁니다.
> 초록만 보고 쓴 요약은 그럴듯한데 틀린 곳을 짚어낼 수 없어서,
> 읽기도 전에 잘못된 지도를 신뢰하게 만들기 때문입니다.
>
> 그래프 뷰의 빈 노드가 "아직 안 읽은 논문"입니다.

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
