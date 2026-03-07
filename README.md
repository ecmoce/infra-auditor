# infra-auditor

온프레미스 클라우드 인프라 OS 튜닝 점검 에이전트

## Overview

대규모 온프레미스 클라우드(AWS-like) 환경에서 서버 역할별 OS 설정을 자동으로 점검하고,
하드웨어 스펙에 맞는 최적 설정을 제안하는 시스템.

## Infrastructure Context

- **Hardware**: Intel Xeon 4th/5th Gen (2-socket), Mellanox ConnectX-5/6 (4 NICs bonded), 1-2TB RAM
- **OS**: CentOS 7, Ubuntu 22.04/24.04, Rocky Linux 9
- **Regions**: 4 global regions
- **Server Roles**:
  - `control` — Platform management
  - `compute` — VM hypervisor (KVM/QEMU)
  - `network` — ELB/Load Balancer
  - `storage-ceph` — Ceph distributed storage
  - `storage-s3` — S3-compatible object storage

## Architecture

```
[Agent] → per-host audit → JSON report
   ↓
[Aggregator] → regional dashboard → compliance overview
```

## Tech Stack

- Agent: Python 3.8+ (CentOS 7 compat)
- Dashboard: FastAPI + Modern Web UI
- Docker: Testing & verification
- CI/CD: GitHub Actions

## License

MIT
