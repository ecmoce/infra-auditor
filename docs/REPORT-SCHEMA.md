# JSON 리포트 스키마

## 개요

Agent가 생성하고 Aggregator가 수집하는 JSON 리포트의 표준 스키마를 정의합니다.

## 전체 스키마 구조

```json
{
  "metadata": { ... },
  "server_info": { ... },
  "hardware_info": { ... },
  "scan_results": { ... },
  "compliance": { ... },
  "errors": [ ... ]
}
```

## 상세 스키마

### metadata (메타데이터)

```json
{
  "metadata": {
    "version": "1.0.0",
    "agent_version": "0.1.0",
    "scan_id": "uuid-v4",
    "timestamp": "2024-03-07T07:48:00Z",
    "scan_duration_seconds": 45.2,
    "scan_type": "full|quick|targeted",
    "scan_parameters": {
      "focus_areas": ["cpu", "memory", "network", "storage"],
      "skip_areas": ["security"],
      "deep_scan": true
    }
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| version | string | Y | 스키마 버전 |
| agent_version | string | Y | 에이전트 버전 |
| scan_id | string | Y | 스캔 고유 식별자 (UUID) |
| timestamp | string | Y | 스캔 시작 시각 (ISO 8601) |
| scan_duration_seconds | number | Y | 스캔 소요 시간 (초) |
| scan_type | string | Y | 스캔 유형 (full/quick/targeted) |
| scan_parameters | object | N | 스캔 매개변수 |

### server_info (서버 정보)

```json
{
  "server_info": {
    "hostname": "compute-node-01.region-kr.internal",
    "fqdn": "compute-node-01.region-kr.internal.company.com",
    "role": "compute",
    "role_detection": {
      "method": "auto|manual",
      "confidence": 0.95,
      "detected_services": ["libvirtd", "qemu-kvm"],
      "evidence": {
        "processes": ["qemu-system-x86_64"],
        "packages": ["qemu-kvm", "libvirt-daemon"],
        "ports": [16509, 16514]
      }
    },
    "region": "kr-seoul",
    "datacenter": "dc1",
    "rack": "rack-a01",
    "environment": "production|staging|development",
    "tags": {
      "team": "infrastructure",
      "project": "cloud-platform",
      "maintenance_window": "sunday-03:00"
    }
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| hostname | string | Y | 서버 호스트명 |
| fqdn | string | N | 전체 도메인명 |
| role | string | Y | 서버 역할 (control/compute/network/storage-ceph/storage-s3) |
| role_detection | object | Y | 역할 감지 정보 |
| region | string | Y | 지역 식별자 |
| datacenter | string | N | 데이터센터 |
| rack | string | N | 랙 위치 |
| environment | string | Y | 환경 (production/staging/development) |
| tags | object | N | 추가 태그 정보 |

### hardware_info (하드웨어 정보)

```json
{
  "hardware_info": {
    "cpu": {
      "model": "Intel(R) Xeon(R) Gold 6348 CPU @ 2.60GHz",
      "architecture": "x86_64",
      "sockets": 2,
      "cores_per_socket": 28,
      "threads_per_core": 2,
      "total_cores": 56,
      "total_threads": 112,
      "numa_nodes": 2,
      "cache_l3_kb": 42240,
      "flags": ["avx2", "avx512f", "tsx"]
    },
    "memory": {
      "total_gb": 1024,
      "type": "DDR5",
      "speed_mhz": 4800,
      "dimms": [
        {
          "size_gb": 64,
          "type": "DDR5",
          "speed_mhz": 4800,
          "numa_node": 0
        }
      ]
    },
    "network": {
      "interfaces": [
        {
          "name": "ens1f0",
          "type": "ethernet",
          "driver": "mlx5_core",
          "model": "Mellanox ConnectX-6 Dx",
          "speed_gbps": 100,
          "numa_node": 0,
          "pci_slot": "0000:18:00.0",
          "bonding": {
            "master": "bond0",
            "mode": "802.3ad"
          }
        }
      ]
    },
    "storage": {
      "devices": [
        {
          "name": "/dev/nvme0n1",
          "type": "nvme",
          "model": "Samsung SSD 980 PRO 2TB",
          "size_gb": 2000,
          "interface": "PCIe 4.0",
          "numa_node": 0,
          "rotational": false
        }
      ],
      "raid": [
        {
          "device": "/dev/md0",
          "level": "raid10",
          "members": ["/dev/sda", "/dev/sdb", "/dev/sdc", "/dev/sdd"],
          "status": "clean"
        }
      ]
    }
  }
}
```

### scan_results (스캔 결과)

```json
{
  "scan_results": {
    "cpu": [
      {
        "category": "cpu",
        "subcategory": "governor",
        "item": "scaling_governor",
        "description": "CPU 주파수 조절 정책",
        "current_value": "ondemand",
        "recommended_value": "performance",
        "collection_method": "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
        "severity": "warning",
        "impact_description": "주파수 변경으로 인한 지연 시간 변동성 증가",
        "justification": "일관된 성능과 낮은 지연시간을 위해 performance 모드 권장",
        "remediation": {
          "command": "echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor",
          "persistent": "echo 'GOVERNOR=\"performance\"' | sudo tee /etc/default/cpufrequtils",
          "requires_reboot": false
        },
        "compliance": false,
        "score_impact": 10
      }
    ],
    "memory": [
      {
        "category": "memory",
        "subcategory": "virtual_memory",
        "item": "vm.swappiness",
        "description": "스왑 사용 적극성 설정",
        "current_value": "60",
        "recommended_value": "1",
        "collection_method": "cat /proc/sys/vm/swappiness",
        "severity": "critical",
        "impact_description": "불필요한 스왑으로 인한 심각한 성능 저하",
        "justification": "메모리 부족 시에만 스왑 사용하여 성능 보장",
        "remediation": {
          "command": "sysctl -w vm.swappiness=1",
          "persistent": "echo 'vm.swappiness = 1' | sudo tee -a /etc/sysctl.conf",
          "requires_reboot": false
        },
        "compliance": false,
        "score_impact": 25
      }
    ],
    "network": [ ... ],
    "storage": [ ... ],
    "kernel": [ ... ],
    "security": [ ... ],
    "service_specific": [
      {
        "category": "service_specific",
        "subcategory": "kvm",
        "item": "nested_virtualization",
        "description": "중첩 가상화 지원",
        "current_value": "N",
        "recommended_value": "Y",
        "collection_method": "cat /sys/module/kvm_intel/parameters/nested",
        "severity": "info",
        "impact_description": "VM 내부에서 가상화 기능 사용 불가",
        "justification": "컨테이너 환경 지원을 위한 중첩 가상화 활성화",
        "remediation": {
          "command": "echo 'options kvm_intel nested=Y' | sudo tee /etc/modprobe.d/kvm.conf",
          "persistent": "위와 동일 (모듈 로딩 시 적용)",
          "requires_reboot": true
        },
        "compliance": false,
        "score_impact": 5
      }
    ]
  }
}
```

### 항목별 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| category | string | Y | 대분류 (cpu/memory/network/storage/kernel/security/service_specific) |
| subcategory | string | Y | 중분류 (governor/hugepages/tcp_buffers 등) |
| item | string | Y | 구체적 항목명 |
| description | string | Y | 항목 설명 |
| current_value | string | Y | 현재 설정값 |
| recommended_value | string | Y | 권장 설정값 |
| collection_method | string | Y | 현재값 수집 방법 |
| severity | string | Y | 심각도 (critical/warning/info) |
| impact_description | string | Y | 영향 설명 |
| justification | string | Y | 권장사항 근거 |
| remediation | object | Y | 수정 방법 |
| compliance | boolean | Y | 준수 여부 |
| score_impact | number | Y | 점수 영향도 (0-100) |

### compliance (준수 점수)

```json
{
  "compliance": {
    "overall_score": 75,
    "max_possible_score": 100,
    "category_scores": {
      "cpu": {
        "score": 80,
        "max_score": 100,
        "compliant_items": 8,
        "total_items": 10
      },
      "memory": {
        "score": 60,
        "max_score": 100,
        "compliant_items": 6,
        "total_items": 10
      },
      "network": {
        "score": 90,
        "max_score": 100,
        "compliant_items": 18,
        "total_items": 20
      }
    },
    "severity_summary": {
      "critical": 2,
      "warning": 8,
      "info": 12
    },
    "recommendations": {
      "high_priority": [
        {
          "item": "vm.swappiness",
          "impact": 25,
          "effort": "low"
        }
      ],
      "medium_priority": [ ... ],
      "low_priority": [ ... ]
    }
  }
}
```

### errors (오류 정보)

```json
{
  "errors": [
    {
      "timestamp": "2024-03-07T07:48:15Z",
      "category": "collection",
      "item": "hugepages_status",
      "error_code": "PERMISSION_DENIED",
      "message": "Permission denied: /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages",
      "severity": "warning",
      "impact": "1GB hugepage 설정 확인 불가"
    },
    {
      "timestamp": "2024-03-07T07:48:20Z", 
      "category": "analysis",
      "item": "network_bond_status",
      "error_code": "PARSING_ERROR",
      "message": "Failed to parse bonding status from /proc/net/bonding/bond0",
      "severity": "error",
      "impact": "네트워크 본딩 상태 분석 실패"
    }
  ]
}
```

## 스키마 버전 관리

### 버전 1.0.0 (현재)
- 기본 구조 정의
- 5개 역할 지원
- 기본 메트릭 세트

### 향후 계획

#### 버전 1.1.0
- 성능 벤치마크 결과 추가
- 히스토리컬 데이터 비교
- 사용자 정의 규칙 지원

#### 버전 2.0.0
- 실시간 모니터링 데이터
- 예측 분석 결과
- 자동 remediation 실행 결과

## 사용 예제

### Agent에서 리포트 생성
```python
from infra_auditor.agent import Report

report = Report()
report.collect_system_info()
report.run_compliance_check()
report.save_json('/tmp/report.json')
```

### Aggregator에서 리포트 수신
```python
@app.post("/api/v1/reports")
async def receive_report(report: ReportSchema):
    # 스키마 검증
    validated_report = ReportSchema.parse_obj(report)
    
    # 데이터베이스 저장
    await store_report(validated_report)
    
    return {"status": "accepted", "report_id": validated_report.metadata.scan_id}
```

### 리포트 조회 API
```python
@app.get("/api/v1/reports/{server_id}")
async def get_latest_report(server_id: str):
    report = await get_report_by_server(server_id)
    return ReportSchema.from_orm(report)
```

## 데이터 검증

### 필수 검증 규칙
1. **metadata.timestamp**: ISO 8601 형식, 현재 시간 기준 24시간 이내
2. **server_info.hostname**: 유효한 호스트명 형식
3. **server_info.role**: 정의된 역할 중 하나
4. **compliance.overall_score**: 0-100 범위
5. **scan_results.severity**: critical/warning/info 중 하나

### 데이터 일관성 검증
1. **점수 계산**: category_scores 합계 = overall_score
2. **항목 개수**: 각 카테고리의 compliant_items ≤ total_items
3. **오류 영향**: errors가 있는 항목은 scan_results에 결과 없음 또는 부분 결과

### JSON Schema 파일
별도의 `report-schema.json` 파일로 JSON Schema 표준 형식도 제공하여 다양한 도구에서 검증 가능하도록 지원합니다.

이 스키마는 확장 가능하도록 설계되었으며, 새로운 요구사항에 따라 하위 호환성을 유지하면서 진화할 수 있습니다.