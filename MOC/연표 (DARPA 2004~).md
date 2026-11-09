---
tags: [MOC, reference]
갱신: 2026-11-09
범위: DARPA Grand Challenge (2004) ~ 현재
조사방법: 웹 검색. darpa.mil 은 세션 네트워크에서 차단되어 **공식 페이지를 확인하지 못했다**
---

# 연표 — DARPA 2004 ~ 현재

> [!danger] 이 노트가 담지 않는 것
> **논문 내용이 없다.** 아래는 **사건(대회·프로그램)의 연표**와 **서지 정보**뿐이다.
> 볼트 규칙상 논문 내용은 세션에서 함께 읽은 뒤에만 쓴다.
> 각 논문이 *무엇을 했는지*는 그 논문을 읽는 세션에서 `Papers/`에 채운다.
>
> 사용자가 **계보 파악을 명시적으로 요청**해서 만든 메타 노트다 (2026-11-09).

> [!warning] 출처의 질
> **`darpa.mil` 이 차단되어 공식 프로그램 페이지를 못 봤다.** 대회·프로그램 사실은
> 위키 미러·업계 매체(IEEE Spectrum, Defense News, Army Technology 등) 기반이다.
> **논문 서지는 CMU RI·DBLP·출판사 레코드로 교차 확인**했으므로 그쪽이 더 믿을 만하다.

---

## 1. 대회 — 무대가 만들어진 3년

| 날짜 | 대회 | 코스 | 결과 | 확인 |
|---|---|---|---|---|
| **2004-03-13** | DARPA Grand Challenge (1회) | Barstow CA → Primm NV, 사막 | **완주 차량 없음.** CMU Red Team 이 최장 **11.8 km (7.4 mi)** | ⚠️ 위키 기반 |
| **2005-10-08** | DARPA Grand Challenge (2회) | **212.4 km (132 mi)** 사막 | **Stanford "Stanley" 우승**, 약 6h 53m 58s, 상금 $2M. **5대 완주** | ⚠️ 위키 기반 |
| **2007-11-03** | DARPA **Urban** Challenge | 전 George AFB, Victorville CA | **Tartan Racing (CMU) "Boss" 1위**, 4:10:20 | ⚠️ 위키 기반 |

> [!note] 2007 Urban Challenge 는 **도심**이다
> 교통 법규·타 차량 상호작용이 주제여서, 지형 자체가 문제인 오프로드와는 축이 다르다.
> 오프로드 쪽 흐름은 아래 **군용 UGV 프로그램** 라인이다.

> [!question] 상금에 대한 출처 충돌
> 2007 대회 상금을 "$2M/$1M/$500K" 로 적은 출처와 "2006-10-02 에 DARPA 가 무상금 발표" 라고
> 적은 출처가 같이 나왔다. **화해되지 않았다.** 공식 기록 확인 필요.

---

## 2. 군용 UGV 프로그램 — 오프로드 라인

| 프로그램 | 이름 풀이 | 시기 | 비고 | 확인 |
|---|---|---|---|---|
| **PerceptOR** | Perception for Off-Road Robotics | 2000년대 초 | CMU RI 프로젝트 페이지 존재. 종료 | ⚠️ 연도 ❓ |
| **UGCV** | Unmanned Ground Combat Vehicle | 2000년대 초 | 플랫폼(Spinner) 쪽 | ⚠️ 연도 ❓ |
| **UPI** | **UGCV PerceptOR Integrated** — 위 둘의 통합 | 2000년대 중후반 | 차량 **Crusher** (Spinner 기반, 6륜 하이브리드 전기). 주관 **CMU NREC**, 책임 **Anthony Stentz** | ⚠️ 연도 ❓ |
| **LAGR** | **Learning Applied to Ground Robots** | 2000년대 중반 | **"학습을 오프로드 주행에 쓴다"의 출발점으로 인용되는 프로그램.** 공통 플랫폼을 참가팀에 배포, 제3자 평가팀이 측정 | ⚠️ 연도 ❓ |
| **RACER** | **Robotic Autonomy in Complex Environments with Resiliency** | **2021 ~** | 아래 별도 절 | ⚠️ 업계 매체 기반 |

> [!tip] LAGR 이 중요한 이유 (이것만은 출처가 여러 곳에서 일치)
> 후대 논문들이 "현장에서 적응하는 시스템의 첫 시도"로 LAGR 계열을 인용한다.
> **near-field(스테레오·proprioceptive)로 라벨을 만들어 far-field(비전)를 지도학습**시키는 구조 —
> 지금 읽은 [[WVN (Mattamala 2024)]] 의 자기지도 라벨 생성과 **구조가 같은 계열**이다.
> ⚠️ 이 문장은 **검색된 초록·인용문 기준**이다. LAGR 논문을 직접 읽은 것이 아니다.

### RACER (2021 ~ ) — 현재진행형

⚠️ **전부 업계 매체 기반.** darpa.mil 공식 페이지 미확인.

| 항목 | 값 |
|---|---|
| 목표 | GPS·사전 지도 **없이** 비정형 오프로드를 **임무 속도**로 주행 |
| 기간 | 2021 시작, **FY2025 까지** 2단계 ⚠️ "지금 종료 중" 보도와 날짜가 어긋남 |
| 속도 목표 | 프로그램 종료 시 **19 mph** (≈ 8.5 m/s) |
| 플랫폼 | **RHP** (RACER Heavy Platform) = Textron M5 기반, Carnegie Robotics 통합 · **RFV** (RACER Fleet Vehicle) |
| 3차 실험 실적 | RFV **12대**로 **246 miles / 24.6 h** 주행 |
| Phase 1 종료 | 2023-04-11 발표된 시험으로 마감 |

> [!note] 숫자의 의미
> **19 mph ≈ 8.5 m/s 가 "현재 국가 프로그램 수준의 목표치"** 라는 점이 기준선으로 쓸 만하다.
> 우리 후보 목록의 논문들이 보고하는 속도를 이것과 비교할 수 있다.

---

## 3. 서지 — DARPA 시대 논문 (내용 미확인)

**교차 확인된 것만.** 내용은 읽은 뒤에 `Papers/`에 쓴다.

| 논문 | 서지 | 확인 |
|---|---|---|
| Thrun, Montemerlo, Dahlkamp, Stavens 외 — *Stanley: The Robot that Won the DARPA Grand Challenge* | **JFR 23(9):661–692, 2006** · `10.1002/rob.20147` | ✅ CMU RI + DBLP + Wiley |
| Urmson 외 — *Autonomous driving in urban environments: Boss and the Urban Challenge* | **JFR 25(8):425–466, 2008** · `10.1002/rob.20255` · *Special Issue on the 2007 DARPA Urban Challenge, Part I* | ✅ CMU RI + DBLP + PDF 헤더 |
| Hadsell, (Sermanet), Ben, Erkan, Scoffier, Kavukcuoglu, Muller, LeCun — *Learning long-range vision for autonomous off-road driving* | **JFR 26(2):120–144, 2009** · `10.1002/rob.20276` · LAGR 로봇에서 시험 | ✅ 권·호·페이지 <br> ⚠️ **저자 목록 충돌** — Sermanet 포함 여부가 출처마다 다름 |
| Hadsell 외 — *Deep Belief Net Learning in a Long-Range Vision System for Autonomous Off-Road Driving* | IROS 2008 ⚠️ · 권·페이지 ❓ | ⚠️ |
| Kelly, Stentz 외 — *Toward Reliable Off Road Autonomous Vehicles Operating in Challenging Environments* | **IJRR 25(6), 2006** ⚠️ · 페이지 ❓ · PerceptOR 팀 | ⚠️ CMU 페이지 스니펫만 |
| Bagnell, Bradley, Silver, Sofman, Stentz — *Learning for Autonomous Navigation* | **IEEE Robotics & Automation Magazine 2010** ⚠️ · 권·페이지 ❓ · UPI/Crusher 시스템 | ⚠️ |
| Bajracharya 외 — *Autonomous off-road navigation with end-to-end learning for the LAGR program* | 2009 ⚠️ · **학회·저널 ❓** | ⚠️ |
| Sofman 외 — *Improving Robot Navigation through Self-Supervised Online Learning* | 연도·게재지 ❓ | ❓ |
| Albus 외 — *Learning traversability models for autonomous mobile vehicles* | *Autonomous Robots* 2007 ⚠️ · 권·페이지 ❓ · LAGR 에서 구현·평가 | ⚠️ |

> [!danger] 위 표를 요약으로 쓰지 말 것
> 비고란은 **제목·게재지 레코드에서 읽을 수 있는 것**과 검색 스니펫이 전부다.
> "무엇을 어떻게 했는가"는 들어 있지 않고, 들어 있어서도 안 된다.

---

## 4. 2004 → 현재 사이의 빈칸

후보 목록의 가장 이른 논문은 **[[MPPI (Williams 2016)]]** 이다.
**2009 ~ 2016 사이 7년이 비어 있다.**

| 빈칸 | 상태 |
|---|---|
| 2010년대 초 오프로드 — LAGR 이후 ~ 딥러닝 이전 | ❓ 후보 목록에 없음 |
| terramechanics 고전 (Bekker, Wong 원전) | ❓ [[용어 사전]]에 용어로만 있음. 원전 서지 미확인 |
| Project Chrono · 시뮬레이터 계열의 등장 시점 | ❓ |

> [!question] 이 빈칸을 메우는 가장 빠른 길
> [[논문 목록]]의 **Min 외 (JFR 2026) 서베이 — 250편 이상 리뷰**.
> 아직 읽지 않았다. 이걸 함께 읽으면 연표의 빈칸이 **논문 내용 수준으로** 채워진다.

---

## 5. ❓ 확인 못 한 것

- **darpa.mil 전체** — 세션 네트워크에서 차단. PerceptOR·UGCV·UPI·LAGR·RACER 의 **공식 시작·종료 연도**를 못 봤다
- **LAGR 프로그램의 정확한 기간**과 참가 기관 목록
- **RACER 의 현재 상태** — "FY2025 까지" 와 "지금 종료 중" 보도가 어긋난다
- 2007 Urban Challenge **상금 여부** (§1 출처 충돌)
- **Hadsell 2009 의 저자 목록** (Sermanet 포함 여부)
- 2009 ~ 2016 구간 전체

---

**연결**: [[논문 목록]] · [[학회 지도]] · [[용어 사전]] · [[질문 로그]]
