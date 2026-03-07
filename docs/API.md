# Aggregator API 명세

## 개요

Infra-Auditor Aggregator 서버의 RESTful API 문서입니다.

### 기본 정보
- **Base URL**: `https://aggregator.internal:8443/api`
- **API Version**: v1
- **Authentication**: API Key + TLS Client Certificate
- **Content-Type**: `application/json`
- **Rate Limiting**: 1000 requests/hour per API key

## 인증

### API Key 방식
```http
GET /api/v1/servers
Authorization: Bearer <api-key>
```

### TLS Client Certificate
- 상호 TLS 인증 필요
- 클라이언트 인증서는 관리자가 발급
- CN(Common Name)으로 권한 수준 결정

## 공통 응답 형식

### 성공 응답
```json
{
  "status": "success",
  "data": { ... },
  "meta": {
    "timestamp": "2024-03-07T07:48:00Z",
    "version": "1.0.0",
    "request_id": "uuid-v4"
  }
}
```

### 오류 응답
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid report format",
    "details": {
      "field": "metadata.timestamp",
      "reason": "Invalid ISO 8601 format"
    }
  },
  "meta": {
    "timestamp": "2024-03-07T07:48:00Z",
    "request_id": "uuid-v4"
  }
}
```

## 1. 리포트 관리 API

### 1.1 리포트 제출

**POST** `/api/v1/reports`

Agent가 스캔 결과를 제출합니다.

#### Request Body
```json
{
  "server_id": "comp-seoul-01.internal",
  "report": {
    // REPORT-SCHEMA.md 참조
  }
}
```

#### Response
```json
{
  "status": "success",
  "data": {
    "report_id": "uuid-v4",
    "received_at": "2024-03-07T07:48:00Z",
    "next_scan_recommended": "2024-03-08T07:48:00Z",
    "processing_status": "accepted"
  }
}
```

#### Error Codes
- `400` VALIDATION_ERROR: 스키마 검증 실패
- `401` UNAUTHORIZED: 인증 실패
- `429` RATE_LIMITED: 요청 한도 초과
- `413` PAYLOAD_TOO_LARGE: 리포트 크기 초과 (10MB)

### 1.2 배치 리포트 제출

**POST** `/api/v1/reports/batch`

여러 서버의 리포트를 한 번에 제출합니다.

#### Request Body
```json
{
  "reports": [
    {
      "server_id": "server-1",
      "report": { ... }
    },
    {
      "server_id": "server-2", 
      "report": { ... }
    }
  ]
}
```

#### Response
```json
{
  "status": "success",
  "data": {
    "batch_id": "uuid-v4",
    "total": 2,
    "accepted": 2,
    "rejected": 0,
    "results": [
      {
        "server_id": "server-1",
        "report_id": "uuid-v4",
        "status": "accepted"
      },
      {
        "server_id": "server-2",
        "report_id": "uuid-v4", 
        "status": "accepted"
      }
    ]
  }
}
```

### 1.3 리포트 조회

**GET** `/api/v1/reports/{server_id}`

특정 서버의 최신 리포트를 조회합니다.

#### Query Parameters
- `include_history`: 히스토리 포함 여부 (default: false)
- `limit`: 히스토리 개수 제한 (default: 10)

#### Response
```json
{
  "status": "success",
  "data": {
    "current_report": {
      // 전체 리포트 스키마
    },
    "history": [
      {
        "report_id": "uuid-v4",
        "timestamp": "2024-03-06T07:48:00Z",
        "compliance_score": 75
      }
    ]
  }
}
```

### 1.4 리포트 상세 조회

**GET** `/api/v1/reports/{server_id}/{report_id}`

특정 리포트의 상세 정보를 조회합니다.

#### Response
전체 리포트 스키마 반환

## 2. 서버 관리 API

### 2.1 서버 목록 조회

**GET** `/api/v1/servers`

등록된 서버 목록을 조회합니다.

#### Query Parameters
- `region`: 지역 필터 (예: seoul, tokyo)
- `role`: 역할 필터 (예: compute, storage-ceph)
- `compliance_min`: 최소 compliance 점수 (0-100)
- `compliance_max`: 최대 compliance 점수 (0-100)
- `status`: 상태 필터 (online, offline, error)
- `page`: 페이지 번호 (default: 1)
- `size`: 페이지 크기 (default: 50, max: 500)

#### Response
```json
{
  "status": "success",
  "data": {
    "servers": [
      {
        "server_id": "comp-seoul-01.internal",
        "hostname": "comp-seoul-01",
        "role": "compute",
        "region": "seoul",
        "last_scan": "2024-03-07T07:48:00Z",
        "compliance_score": 78,
        "status": "online",
        "critical_issues": 2,
        "warning_issues": 8,
        "info_issues": 12
      }
    ],
    "pagination": {
      "page": 1,
      "size": 50,
      "total": 1247,
      "total_pages": 25
    },
    "filters_applied": {
      "region": "seoul",
      "role": "compute"
    }
  }
}
```

### 2.2 서버 등록

**POST** `/api/v1/servers`

새로운 서버를 시스템에 등록합니다.

#### Request Body
```json
{
  "server_id": "new-server.internal",
  "hostname": "new-server",
  "role": "compute",
  "region": "seoul",
  "datacenter": "dc1",
  "rack": "rack-a01",
  "tags": {
    "team": "infrastructure",
    "project": "cloud-platform"
  }
}
```

### 2.3 서버 정보 수정

**PUT** `/api/v1/servers/{server_id}`

서버 메타데이터를 수정합니다.

### 2.4 서버 삭제

**DELETE** `/api/v1/servers/{server_id}`

서버를 시스템에서 제거합니다.

## 3. 대시보드 API

### 3.1 전체 상태 요약

**GET** `/api/v1/dashboard/summary`

전체 인프라의 요약 상태를 조회합니다.

#### Response
```json
{
  "status": "success",
  "data": {
    "overall": {
      "total_servers": 1247,
      "average_compliance": 82.5,
      "critical_issues": 23,
      "warning_issues": 156,
      "last_updated": "2024-03-07T07:48:00Z"
    },
    "regions": [
      {
        "name": "seoul",
        "servers": 312,
        "compliance": 89.2,
        "status": "healthy"
      },
      {
        "name": "tokyo", 
        "servers": 289,
        "compliance": 76.8,
        "status": "warning"
      }
    ],
    "roles": [
      {
        "name": "compute",
        "servers": 456,
        "compliance": 75.8,
        "status": "warning"
      },
      {
        "name": "control",
        "servers": 124,
        "compliance": 92.5,
        "status": "healthy"
      }
    ]
  }
}
```

### 3.2 Compliance 히트맵

**GET** `/api/v1/dashboard/compliance-heatmap`

역할별/지역별 compliance 히트맵 데이터를 조회합니다.

#### Response
```json
{
  "status": "success",
  "data": {
    "heatmap": [
      {
        "region": "seoul",
        "role": "compute", 
        "compliance": 78.5,
        "server_count": 89,
        "critical_issues": 12
      }
    ],
    "regions": ["seoul", "tokyo", "singapore", "us-west"],
    "roles": ["control", "compute", "network", "storage-ceph", "storage-s3"]
  }
}
```

### 3.3 상위 이슈 목록

**GET** `/api/v1/dashboard/top-issues`

영향도가 높은 상위 이슈 목록을 조회합니다.

#### Query Parameters
- `limit`: 반환할 이슈 개수 (default: 10)
- `severity`: 심각도 필터 (critical, warning, info)

#### Response
```json
{
  "status": "success", 
  "data": {
    "issues": [
      {
        "item": "vm.swappiness",
        "current_value": "60",
        "recommended_value": "1",
        "affected_servers": 127,
        "regions_affected": ["tokyo", "us-west"],
        "severity": "critical",
        "impact_score": 25,
        "fix_complexity": "low",
        "estimated_fix_time_minutes": 2
      }
    ]
  }
}
```

## 4. 분석 API

### 4.1 트렌드 분석

**GET** `/api/v1/analytics/trends`

지정된 기간의 compliance 트렌드를 조회합니다.

#### Query Parameters
- `period`: 기간 (1d, 7d, 30d, 90d)
- `region`: 지역 필터 (선택사항)
- `role`: 역할 필터 (선택사항)

#### Response
```json
{
  "status": "success",
  "data": {
    "period": "7d",
    "datapoints": [
      {
        "timestamp": "2024-03-01T00:00:00Z",
        "compliance": 78.5,
        "server_count": 1245
      },
      {
        "timestamp": "2024-03-02T00:00:00Z", 
        "compliance": 79.2,
        "server_count": 1247
      }
    ],
    "summary": {
      "start_compliance": 78.5,
      "end_compliance": 82.1,
      "change_percent": 4.6,
      "trend": "improving"
    }
  }
}
```

### 4.2 이상치 탐지

**GET** `/api/v1/analytics/anomalies`

설정 이상치를 탐지합니다.

#### Query Parameters
- `role`: 역할별 분석 (required)
- `threshold`: 이상치 임계값 (default: 0.95)

#### Response
```json
{
  "status": "success",
  "data": {
    "role": "compute",
    "normal_pattern": {
      "vm.swappiness": "1",
      "hugepages_ratio": "80%",
      "cpu_governor": "performance"
    },
    "outliers": [
      {
        "server_id": "comp-tokyo-15",
        "anomalies": [
          {
            "parameter": "vm.swappiness",
            "value": "10",
            "deviation_score": 0.8
          }
        ],
        "requires_investigation": true
      }
    ],
    "total_servers": 456,
    "outlier_count": 14
  }
}
```

### 4.3 변경 이력 분석

**GET** `/api/v1/analytics/drift`

설정 변경 이력을 분석합니다.

#### Query Parameters
- `period`: 분석 기간 (1d, 7d, 30d)
- `server_id`: 특정 서버 (선택사항)
- `parameter`: 특정 매개변수 (선택사항)

#### Response
```json
{
  "status": "success",
  "data": {
    "changes": [
      {
        "timestamp": "2024-03-07T14:30:00Z",
        "server_id": "comp-seoul-01", 
        "parameter": "vm.swappiness",
        "old_value": "60",
        "new_value": "1",
        "change_source": "ansible-automation",
        "compliance_impact": 8.5
      }
    ],
    "summary": {
      "total_changes": 45,
      "compliance_improvements": 38,
      "compliance_regressions": 7,
      "net_compliance_change": 5.2
    }
  }
}
```

## 5. 자동화 API

### 5.1 Remediation 스크립트 생성

**POST** `/api/v1/remediation/generate`

지정된 서버들에 대한 remediation 스크립트를 생성합니다.

#### Request Body
```json
{
  "servers": ["comp-seoul-01", "comp-seoul-02"],
  "issues": ["vm.swappiness", "cpu_governor"],
  "format": "ansible|bash|terraform",
  "dry_run": true
}
```

#### Response
```json
{
  "status": "success",
  "data": {
    "script_id": "uuid-v4",
    "format": "ansible",
    "script": "---\n# Generated playbook\n...",
    "metadata": {
      "affected_servers": 2,
      "estimated_time_minutes": 5,
      "requires_reboot": false,
      "risk_level": "low"
    },
    "download_url": "/api/v1/remediation/download/uuid-v4"
  }
}
```

### 5.2 작업 스케줄링

**POST** `/api/v1/remediation/schedule`

remediation 작업을 스케줄링합니다.

#### Request Body
```json
{
  "script_id": "uuid-v4",
  "schedule": {
    "type": "immediate|scheduled",
    "datetime": "2024-03-08T02:00:00Z"
  },
  "approval_required": true,
  "notification_channels": ["slack", "email"]
}
```

### 5.3 작업 상태 조회

**GET** `/api/v1/remediation/jobs/{job_id}`

스케줄된 작업의 상태를 조회합니다.

#### Response
```json
{
  "status": "success",
  "data": {
    "job_id": "uuid-v4",
    "status": "pending|running|completed|failed",
    "progress": {
      "completed": 5,
      "total": 10,
      "current_task": "Applying sysctl changes"
    },
    "results": {
      "successful": ["server1", "server2"],
      "failed": ["server3"],
      "skipped": []
    }
  }
}
```

## 6. 관리 API

### 6.1 규칙 관리

**GET** `/api/v1/admin/rules`

현재 적용된 튜닝 규칙을 조회합니다.

**PUT** `/api/v1/admin/rules`

튜닝 규칙을 업데이트합니다.

### 6.2 시스템 상태

**GET** `/api/v1/admin/health`

시스템 상태를 확인합니다.

#### Response
```json
{
  "status": "success",
  "data": {
    "service": "healthy",
    "database": "healthy",
    "queue": "healthy",
    "last_report_received": "2024-03-07T07:48:00Z",
    "active_agents": 1247,
    "storage_usage_gb": 45.2,
    "memory_usage_percent": 68
  }
}
```

### 6.3 메트릭

**GET** `/api/v1/admin/metrics`

Prometheus 형태의 메트릭을 제공합니다.

```
# HELP infra_auditor_servers_total Total number of servers
# TYPE infra_auditor_servers_total gauge
infra_auditor_servers_total{region="seoul",role="compute"} 89

# HELP infra_auditor_compliance_score Compliance score by region and role  
# TYPE infra_auditor_compliance_score gauge
infra_auditor_compliance_score{region="seoul",role="compute"} 78.5
```

## 7. 웹훅 및 알림

### 7.1 웹훅 등록

**POST** `/api/v1/webhooks`

이벤트 웹훅을 등록합니다.

#### Request Body
```json
{
  "url": "https://your-system.com/webhook",
  "events": ["critical_issue", "compliance_change"],
  "filters": {
    "regions": ["seoul"],
    "severity": ["critical"]
  },
  "secret": "webhook-secret-key"
}
```

### 7.2 웹훅 이벤트 형식

```json
{
  "event": "critical_issue",
  "timestamp": "2024-03-07T07:48:00Z",
  "data": {
    "server_id": "comp-seoul-01",
    "issue": {
      "item": "vm.swappiness", 
      "current_value": "60",
      "recommended_value": "1",
      "severity": "critical"
    }
  },
  "signature": "sha256=..."
}
```

## 8. SDK 및 클라이언트

### Python SDK 예제
```python
from infra_auditor_client import InfraAuditorClient

client = InfraAuditorClient(
    base_url="https://aggregator.internal:8443",
    api_key="your-api-key",
    cert_file="client.pem",
    key_file="client-key.pem"
)

# 서버 목록 조회
servers = client.servers.list(region="seoul", role="compute")

# 리포트 제출
report_id = client.reports.submit(server_id="comp-01", report=report_data)

# 대시보드 데이터
summary = client.dashboard.summary()
```

## 9. 에러 코드 참조

| Code | Description |
|------|-------------|
| 400 | VALIDATION_ERROR: 요청 데이터 검증 실패 |
| 401 | UNAUTHORIZED: 인증 실패 |
| 403 | FORBIDDEN: 권한 없음 |
| 404 | NOT_FOUND: 리소스 없음 |
| 409 | CONFLICT: 리소스 충돌 |
| 413 | PAYLOAD_TOO_LARGE: 요청 크기 초과 |
| 429 | RATE_LIMITED: 요청 한도 초과 |
| 500 | INTERNAL_ERROR: 서버 내부 오류 |
| 502 | DATABASE_ERROR: 데이터베이스 오류 |
| 503 | SERVICE_UNAVAILABLE: 서비스 일시 중단 |

이 API는 RESTful 설계 원칙을 따르며, 확장성과 유지보수성을 고려하여 설계되었습니다. 모든 엔드포인트는 적절한 HTTP 상태 코드를 반환하고, 일관된 응답 형식을 유지합니다.