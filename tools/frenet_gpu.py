#!/usr/bin/env python3
"""배치 Frenet projector (torch, GPU). 256~4096 env 을 매 control step 마다 변환한다.

  from frenet_gpu import FrenetTrack, FrenetTracker
  trk = FrenetTrack("/workspace/assets/tracks/ifac_0824_mapping_3.npz", device="cuda:0")
  st  = FrenetTracker(trk, num_envs=256)
  st.reset(ids, xy, psi)          # 스폰 직후 (전역 탐색)
  out = st.step(xy, psi)          # 매 step  (증분 탐색)

★ 왜 스택의 frenet_converter.py 를 못 쓰는가 ─────────────────────────────
순수 numpy · 단발 조회용이다. 256 env × 50 Hz × 수천만 step 에는 못 쓴다.
대신 `gen_track.py` 가 낸 .npz 는 **s 격자가 정확히 균일**(ds 표준편차 2e-15)하므로
- 최근접 탐색을 고정 크기 window 의 병렬 argmin 으로 쓸 수 있고
- preview 는 탐색 없이 인덱스 산술로 뽑힌다.

★ 왜 전역 argmin 이 아니라 증분(windowed) 탐색인가 ──────────────────────
두 맵 모두에서 실측했다 — **경로상 3 m 이상 떨어진 구간끼리 유클리드 최소 2.61 m**
인데 **트랙 반폭은 최대 2.07~2.32 m** 다. 즉 트랙 한쪽 벽에 붙어 달리는 차가
경로상 한참 떨어진 엉뚱한 구간에 더 가까울 수 있다. 판정 기준은

    dmin > 2 × max_half_width      →  ifac_0824_mapping_3: 2.614 < 4.140  ❌
                                      ifac_roboracer     : 2.603 < 4.644  ❌

둘 다 탈락이므로 전역 argmin 은 쓸 수 없다. 이전 s 주변만 본다:
12 m/s · 50 Hz 면 한 step 에 0.24 m = 2.4 index 이므로 ±12 index(±1.2 m) 는 5배 여유이고,
동시에 3 m 이상 떨어진 branch 를 **후보에서 구조적으로 배제**한다.
(window 를 3 m 이상으로 키우면 그 보호가 사라진다. 키우지 말 것.)

★ waypoint 가 아니라 segment 에 투영한다 ──────────────────────────────
가장 가까운 waypoint 를 고르면 오차가 ds/2 = 5 cm 까지 난다 (트랙 반폭의 2.5%).
window 안의 모든 **선분**에 투영하고 clamp(u, 0, 1) 후 argmin 을 취하면
polyline 의 진짜 최근접점이 나온다. 비용은 (B × K) 뿐이다.

★ 정확도의 한계 — 코너에서의 동거리 무승부 ─────────────────────────────
볼록한 코너 바깥쪽(|d| 이 큰 곳)에서는 선분 j 의 수선발(u<1)과 선분 j+1 의 끝점(u=0)이
**거리가 같다**. float32 tie-break 이 어느 쪽을 고르든 d 는 1e-7 m 수준으로 일치하지만
s 는 최대 ~ds(10 cm) 까지 달라질 수 있다 (실측 최대 7.6 mm).
- d, e_psi, 벽 여유는 영향 없다.
- Δs 는 telescoping 이므로 한 랩 누적 오차가 0 이다 (실측 0.0000 m).
progress reward 에 step 단위로 ±8 mm 의 결정론적 jitter 가 섞이지만
같은 위치에서 항상 같은 값이므로 policy 에 편향을 주지 않는다.

★ 부호 규약 ───────────────────────────────────────────────────────────
d > 0 = 경로의 **왼쪽** (n = (−sin ψ, cos ψ), REP-103 과 일치).
따라서 왼쪽 벽까지 여유 = d_left − d,  오른쪽 벽까지 여유 = d_right + d.
e_psi = wrap(psi_car − psi_path(s)).
"""

from __future__ import annotations

import numpy as np
import torch

TWO_PI = 2.0 * np.pi


def wrap(x: torch.Tensor) -> torch.Tensor:
    """(−π, π] 로 접는다."""
    return torch.remainder(x + np.pi, TWO_PI) - np.pi


class FrenetTrack:
    """reference path 를 device 에 올린 읽기 전용 테이블. stateless."""

    def __init__(self, npz_path, device="cuda:0", dtype=torch.float32,
                 window=12, preview_n=None, preview_stride=None):
        z = np.load(npz_path, allow_pickle=False)
        self.map_name = str(z["map_name"])
        self.npz_path = str(npz_path)
        self.device = torch.device(device)
        self.dtype = dtype

        s = z["s"].astype(np.float64)
        self.N = int(len(s))
        self.ds = float(z["ds"])
        self.lap = float(z["lap_length"])
        # 균일 격자 가정을 여기서 검증한다. 깨지면 preview 인덱싱이 조용히 틀린다.
        step = np.diff(np.append(s, self.lap))
        # npz 가 s 를 float32 로 담으므로 42 m 에서 eps ≈ 5e-6 m 는 저장 오차다.
        # 원본(float64)에서는 표준편차 2e-15 로 측정됐다. 기준을 ds 의 0.1% 로 둔다.
        self.grid_dev = float(np.abs(step - self.ds).max())
        if self.grid_dev > 1e-3 * self.ds:
            raise ValueError(f"s 격자가 균일하지 않다 (최대 편차 {self.grid_dev:.3e} m, "
                             f"ds {self.ds:.6f}). preview 인덱싱 전제가 깨진다.")
        self.window = int(window)
        if self.window * self.ds >= 3.0:
            raise ValueError(f"window {self.window}×{self.ds:.4f} = "
                             f"{self.window*self.ds:.2f} m ≥ 3 m — 엉뚱한 branch 가 후보에 들어온다.")
        self.preview_n = int(preview_n if preview_n is not None else z["preview_n"])
        self.preview_stride = int(preview_stride if preview_stride is not None
                                  else z["preview_stride"])
        self.preview_horizon = self.preview_n * self.preview_stride * self.ds

        def t(a, d=None):
            return torch.as_tensor(np.ascontiguousarray(a), dtype=d or dtype, device=self.device)

        self.s = t(z["s"])
        self.xy = t(np.stack([z["x"], z["y"]], 1))
        self.psi = t(z["psi"])
        self.kappa = t(z["kappa"])
        self.d_left = t(z["d_left"])
        self.d_right = t(z["d_right"])
        self.vx_planner = t(z["vx_planner"])          # Pure Pursuit 베이스라인 전용
        self.left_bound = t(z["left_bound"])
        self.right_bound = t(z["right_bound"])

        nxt = torch.roll(torch.arange(self.N, device=self.device), -1)
        self.seg = self.xy[nxt] - self.xy                     # (N,2) chord
        self.seg_len2 = (self.seg * self.seg).sum(-1).clamp_min(1e-12)
        self.dpsi = wrap(self.psi[nxt] - self.psi)            # segment 내 heading 변화
        self.dkappa = self.kappa[nxt] - self.kappa
        self.dd_left = self.d_left[nxt] - self.d_left
        self.dd_right = self.d_right[nxt] - self.d_right

        self.max_half_width = float(torch.maximum(self.d_left, self.d_right).max())
        self._win_off = torch.arange(-self.window, self.window + 1, device=self.device)
        self._all_off = torch.arange(self.N, device=self.device)
        self._pv_off = (torch.arange(self.preview_n, device=self.device)
                        * self.preview_stride)
        self._ar = torch.arange(1024, device=self.device)

        # GPU 에서는 커널 실행 오버헤드가 지배한다 (B 가 작고 테이블이 422 행뿐이다).
        # 테이블을 미리 쌓아두면 gather 가 6~9 번에서 1 번으로 줄고, 이후 슬라이싱은 view 라 공짜다.
        self._Wtab = torch.stack([self.xy[:, 0], self.xy[:, 1],
                                  self.seg[:, 0], self.seg[:, 1], self.seg_len2], -1)
        self._Jtab = torch.stack([self.s, self.psi, self.dpsi,
                                  self.kappa, self.dkappa,
                                  self.d_left, self.dd_left,
                                  self.d_right, self.dd_right], -1)
        self._Ptab = torch.stack([self.xy[:, 0], self.xy[:, 1], self.psi,
                                  self.kappa, self.d_left, self.d_right], -1)

    def _arange(self, n):
        if self._ar.numel() < n:
            self._ar = torch.arange(n, device=self.device)
        return self._ar[:n]

    # ── 투영 ─────────────────────────────────────────────────────────
    def _project_on(self, xy, psi_car, cand):
        """cand (B,K) long 의 segment 들에 투영. 나머지는 공통."""
        W = self._Wtab[cand]                                   # (B,K,5) gather 1회
        P, S, L2 = W[..., 0:2], W[..., 2:4], W[..., 4]          # view, 공짜
        w = xy.unsqueeze(1) - P
        u = ((w * S).sum(-1) / L2).clamp(0.0, 1.0)
        rel = w - u.unsqueeze(-1) * S                           # 최근접점 → 질의점
        d2 = (rel * rel).sum(-1)
        k = d2.argmin(1)
        b = self._arange(cand.shape[0])

        j = cand[b, k]
        uu = u[b, k]
        rr = rel[b, k]
        SS = S[b, k]
        # 부호: segment 기준 왼쪽이면 +
        cross = SS[:, 0] * rr[:, 1] - SS[:, 1] * rr[:, 0]
        d = torch.sqrt(d2[b, k].clamp_min(0.0)) * torch.sign(cross)

        J = self._Jtab[j]                                       # (B,9) gather 1회
        # 호길이로 s 를 만든다 (chord 가 아니라 ds). 균일 격자이므로 s/ds 가 곧 분수 인덱스.
        return {
            "s": torch.remainder(J[:, 0] + uu * self.ds, self.lap),
            "d": d,
            "e_psi": wrap(psi_car - (J[:, 1] + uu * J[:, 2])),
            "kappa": J[:, 3] + uu * J[:, 4],
            "d_left": J[:, 5] + uu * J[:, 6],
            "d_right": J[:, 7] + uu * J[:, 8],
            "idx": j,
            "u": uu,
            "at_edge": (k == 0) | (k == cand.shape[1] - 1),
        }

    def project(self, xy, psi_car, prev_idx):
        """이전 index 주변 ±window 만 본다. xy (B,2), psi_car (B,), prev_idx (B,) long."""
        cand = torch.remainder(prev_idx.unsqueeze(1) + self._win_off, self.N)
        return self._project_on(xy, psi_car, cand)

    def locate(self, xy, psi_car):
        """전역 탐색. **reset 직후에만** 쓴다 — 엉뚱한 branch 를 잡을 수 있다."""
        B = xy.shape[0]
        cand = self._all_off.unsqueeze(0).expand(B, self.N)
        out = self._project_on(xy, psi_car, cand)
        out["at_edge"] = torch.zeros_like(out["at_edge"])     # 전역이면 경계 개념이 없다
        return out

    def idx_of(self, s):
        """s → segment index. 스폰처럼 s 를 아는 경우 locate 대신 쓴다 (탐색 없음)."""
        return torch.remainder(torch.floor(s / self.ds).long(), self.N)

    # ── 역변환 · preview ────────────────────────────────────────────
    def point_at(self, s, d=None):
        """(s, d) → (xy, psi). 스폰 위치 무작위화와 검증에 쓴다.

        오프셋 방향은 **chord 의 법선**이다 (보간된 psi 의 법선이 아니다).
        그래야 project() 의 정확한 역함수가 된다 — 스폰을 d 로 지정하면
        projector 가 보고하는 d 가 정확히 그 값이어서 벽 여유 검사가 어긋나지 않는다.
        psi 는 보간값을 그대로 돌려준다 (차량 yaw 는 경로 접선이 맞다).
        """
        f = torch.remainder(s, self.lap) / self.ds
        j = torch.remainder(torch.floor(f).long(), self.N)
        u = (f - torch.floor(f)).to(self.dtype)
        p = self.xy[j] + u.unsqueeze(-1) * self.seg[j]
        psi = self.psi[j] + u * self.dpsi[j]
        if d is not None:
            S = self.seg[j]
            n = torch.stack([-S[:, 1], S[:, 0]], -1) / torch.sqrt(self.seg_len2[j]).unsqueeze(-1)
            p = p + d.unsqueeze(-1) * n
        return p, wrap(psi)

    def margins_at(self, s):
        """(d_left, d_right) 보간. 스폰 시 유효한 d 범위를 알기 위해."""
        f = torch.remainder(s, self.lap) / self.ds
        j = torch.remainder(torch.floor(f).long(), self.N)
        u = (f - torch.floor(f)).to(self.dtype)
        return (self.d_left[j] + u * self.dd_left[j],
                self.d_right[j] + u * self.dd_right[j])

    def vx_at(self, s):
        """IQP 속도 프로파일 조회. **Pure Pursuit 베이스라인 전용** —
        ggv 가 자리표시자(19행 전부 5.0/4.5)라서 policy 관측에는 넣지 않는다."""
        f = torch.remainder(s, self.lap) / self.ds
        j = torch.remainder(torch.floor(f).long(), self.N)
        u = (f - torch.floor(f)).to(self.dtype)
        nxt = torch.remainder(j + 1, self.N)
        return self.vx_planner[j] + u * (self.vx_planner[nxt] - self.vx_planner[j])

    def preview(self, s, xy=None, psi_car=None):
        """앞쪽 preview_n 점. xy/psi_car 를 주면 **차량 좌표계**로 돌려준다.

        s 격자가 균일하므로 탐색이 없다: idx = (round(s/ds) + k·stride) % N.
        """
        i0 = torch.remainder(torch.round(s / self.ds).long(), self.N)
        j = torch.remainder(i0.unsqueeze(1) + self._pv_off, self.N)   # (B,n)
        T = self._Ptab[j]                                             # (B,n,6) gather 1회
        P, psi_p = T[..., 0:2], T[..., 2]
        out = {"kappa": T[..., 3], "d_left": T[..., 4], "d_right": T[..., 5], "idx": j}
        if xy is None:
            out["x"], out["y"], out["psi"] = P[..., 0], P[..., 1], psi_p
            return out
        rel = P - xy.unsqueeze(1)
        c, sn = torch.cos(psi_car).unsqueeze(1), torch.sin(psi_car).unsqueeze(1)
        out["x"] = c * rel[..., 0] + sn * rel[..., 1]        # 전방 +
        out["y"] = -sn * rel[..., 0] + c * rel[..., 1]       # 좌측 +
        out["psi"] = wrap(psi_p - psi_car.unsqueeze(1))
        return out

    def progress(self, s_new, s_old):
        """랩을 넘어가도 맞는 Δs. |Δs| > lap/2 는 뒤로 간 것으로 본다."""
        return torch.remainder(s_new - s_old + 0.5 * self.lap, self.lap) - 0.5 * self.lap

    def __repr__(self):
        return (f"FrenetTrack({self.map_name}, N={self.N}, ds={self.ds:.6f}, "
                f"lap={self.lap:.4f}, window=±{self.window*self.ds:.2f} m, "
                f"preview={self.preview_n}×{self.preview_stride*self.ds:.2f}="
                f"{self.preview_horizon:.1f} m, dev={self.device})")


class FrenetTracker:
    """env 당 이전 index·s 를 들고 있는 얇은 상태 래퍼."""

    def __init__(self, track: FrenetTrack, num_envs: int):
        self.trk = track
        self.n = num_envs
        d, N = track.device, track.N
        self.idx = torch.zeros(num_envs, dtype=torch.long, device=d)
        self.s = torch.zeros(num_envs, dtype=track.dtype, device=d)
        # 누적 주행거리. 랩 수를 s 의 wrap 감지로 세면 s≈0 에서 스폰할 때
        # 첫 step 에 허수 랩이 하나 잡힌다 (reset 의 s 가 lap−ε 로 나올 수 있다).
        # 누적값에서 나누는 쪽이 그 경계에 둔감하다.
        self.s_total = torch.zeros(num_envs, dtype=track.dtype, device=d)
        self.edge_hits = torch.zeros(num_envs, dtype=torch.long, device=d)

    def reset(self, ids, xy, psi_car, s0=None):
        """ids 만 초기화. s0 를 알면(스폰을 s 로 지정했을 때) 전역 탐색을 건너뛴다."""
        if s0 is not None:
            out = self.trk.project(xy, psi_car, self.trk.idx_of(s0))
        else:
            out = self.trk.locate(xy, psi_car)
        self.idx[ids] = out["idx"]
        self.s[ids] = out["s"]
        self.s_total[ids] = 0.0
        self.edge_hits[ids] = 0
        out["ds"] = torch.zeros_like(out["s"])
        out["s_total"] = self.s_total[ids]
        out["lap_count"] = self.lap_count[ids]
        return out

    @property
    def lap_count(self):
        return torch.floor(self.s_total / self.trk.lap).long()

    def step(self, xy, psi_car):
        """모든 env 투영 + Δs. 반환 dict 에 'ds'(진행량), 'lap_count' 포함."""
        out = self.trk.project(xy, psi_car, self.idx)
        d_s = self.trk.progress(out["s"], self.s)
        self.s_total = self.s_total + d_s
        self.edge_hits += out["at_edge"].long()
        self.idx = out["idx"]
        self.s = out["s"]
        out["ds"] = d_s
        out["s_total"] = self.s_total
        out["lap_count"] = self.lap_count
        return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()
    print(FrenetTrack(a.npz, device=a.device))
