# UI 컨셉 및 인터페이스 설계

## 설계 철학

> "뻔한 대시보드"가 아닌 **실제 운영에 유용한** 인터페이스

### 핵심 원칙
1. **액션 지향적**: 문제 발견 즉시 해결 방안 제시
2. **컨텍스트 인식**: 역할, 지역, 시간대별 맞춤 정보
3. **노이즈 최소화**: 중요한 정보만 시각적으로 강조
4. **운영자 워크플로우 최적화**: 일상 업무 패턴에 맞춘 UI/UX

## 전체 레이아웃

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Logo] Infra Auditor    🌍 Region: All ▼  👤 Admin ▼  🔔 3     │
├─────────────────────────────────────────────────────────────────────┤
│  📍 Topology  📊 Compliance  📈 Trends  🔧 Remediation  ⚙️ Settings │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│                        [메인 콘텐츠 영역]                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 1. 홈 대시보드: "Mission Control"

### 1.1 상단 Alert Zone (긴급 관심 영역)
```
┌─────────────────────────────────────────────────────────────────┐
│ 🚨 CRITICAL ISSUES (3)                                        │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│ │ 💥 Seoul-DC1    │ │ 💥 Tokyo-DC2    │ │ ⚠️  US-West     │   │
│ │ 23 servers      │ │ 8 servers       │ │ 45 servers      │   │
│ │ swappiness=60   │ │ C-states=6      │ │ dirty_ratio=80  │   │
│ │ [FIX NOW]       │ │ [FIX NOW]       │ │ [SCHEDULE]      │   │
│ └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 지역별 상태 맵
```
      Seoul (🟢 89%)        Tokyo (🟡 76%)        Singapore (🟢 92%)
      ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
      │ Control: 🟢 │       │ Control: 🟢 │       │ Control: 🟢 │
      │ Compute: 🟡 │       │ Compute: 🔴 │       │ Compute: 🟢 │
      │ Network: 🟢 │       │ Network: 🟡 │       │ Network: 🟢 │
      │ Ceph: 🟢    │       │ Ceph: 🟡    │       │ Ceph: 🟢    │
      │ S3: 🟢      │       │ S3: 🟢      │       │ S3: 🟢      │
      └─────────────┘       └─────────────┘       └─────────────┘
      
                              US-West (🟡 72%)
                              ┌─────────────┐
                              │ Control: 🟢 │
                              │ Compute: 🟡 │ 
                              │ Network: 🔴 │
                              │ Ceph: 🟡    │
                              │ S3: 🟢      │
                              └─────────────┘
```

### 1.3 Quick Actions
```
[🔧 Generate Ansible Playbook]  [📊 Compliance Report]  [🎯 Run Targeted Scan]
```

## 2. Topology View: "Infrastructure Map"

### 2.1 계층적 뷰
```
🌍 Global
├── 🏢 Seoul-DC1 (89% compliance)
│   ├── 🏗️ Rack-A01 
│   │   ├── 🖥️ ctrl-01 (🟢 95%) [Control]
│   │   ├── 🖥️ ctrl-02 (🟢 94%) [Control]
│   │   └── 🖥️ ctrl-03 (🟡 87%) [Control] ⚠️ 3 warnings
│   ├── 🏗️ Rack-A02
│   │   ├── 💻 comp-01 (🟡 78%) [Compute] 🔥 Critical: hugepages
│   │   ├── 💻 comp-02 (🟢 91%) [Compute]
│   │   └── 💻 comp-03 (🔴 45%) [Compute] 💥 Multiple criticals
│   └── 🏗️ Rack-A03
│       ├── 🌐 elb-01 (🟢 96%) [Network]
│       └── 💾 ceph-01 (🟡 82%) [Storage-Ceph]
```

### 2.2 필터 및 검색
```
🔍 Search: [                    ] 
🏷️ Role: [All ▼] [Control] [Compute] [Network] [Ceph] [S3]
📊 Compliance: [All ▼] [Critical Issues] [< 80%] [> 90%]
🏢 Region: [All ▼] [Seoul] [Tokyo] [Singapore] [US-West]
```

### 2.3 서버 상세 팝오버 (호버 시)
```
┌─────────────────────────────────────────┐
│ 🖥️ comp-01.seoul.internal              │
│ ├─ Role: Compute (KVM)                  │
│ ├─ Last Scan: 2 hours ago               │
│ ├─ Compliance: 78% (🟡)                 │
│ ├─ Issues:                              │
│ │  💥 vm.swappiness = 60 (should be 1)  │
│ │  ⚠️  CPU governor = ondemand           │
│ │  ⚠️  No hugepages configured          │
│ └─ [View Details] [Quick Fix]           │
└─────────────────────────────────────────┘
```

## 3. Compliance Dashboard: "Health Check Central"

### 3.1 역할별 Compliance Heatmap
```
Role\Region    │ Seoul  │ Tokyo  │ Singapore │ US-West │ Average
───────────────┼────────┼────────┼───────────┼─────────┼─────────
Control        │  🟢 92 │  🟢 94 │   🟢 96   │  🟢 88  │  🟢 92.5
Compute        │  🟡 78 │  🔴 62 │   🟢 89   │  🟡 74  │  🟡 75.8
Network        │  🟢 96 │  🟡 81 │   🟢 93   │  🔴 68  │  🟡 84.5
Storage-Ceph   │  🟢 85 │  🟡 79 │   🟢 91   │  🟡 77  │  🟡 83.0
Storage-S3     │  🟢 93 │  🟢 90 │   🟢 94   │  🟢 89  │  🟢 91.5
```

### 3.2 Top Issues (Quick Win 기회)
```
🎯 HIGH IMPACT / LOW EFFORT
┌─────────────────────────────────────────────────────────────┐
│ Issue                │ Affected │ Impact │ Fix Time │ Action │
├─────────────────────────────────────────────────────────────┤
│ vm.swappiness = 60   │ 127 서버 │  +25%  │ 2 min   │ [FIX]  │
│ CPU governor wrong   │  89 서버 │  +15%  │ 1 min   │ [FIX]  │  
│ No hugepages        │  45 서버 │  +30%  │ 5 min   │ [PLAN] │
│ TCP buffer too small │  23 서버 │  +20%  │ 2 min   │ [FIX]  │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Compliance Trends
```
   Score %
100 ┤ 
 90 ┤     ⚬
 80 ┤    ⚬     ⚬──⚬ ← Recent improvement
 70 ┤ ⚬──⚬            
 60 ┤          
 50 └────────────────────────────
    1wk  5d  3d  1d  now
    
📈 +5% improvement this week
🔧 23 issues auto-fixed
⚠️  8 new issues discovered
```

## 4. Drift Detection: "Change Tracker"

### 4.1 변경 사항 타임라인
```
📅 Last 7 Days - Infrastructure Changes

🕐 2024-03-07 14:30
├─ 🔧 Seoul-DC1: 12 servers updated vm.swappiness 60→1
├─ 📈 Compliance +8% (Region average: 81%→89%)
└─ 👤 Applied by: ansible-automation

🕐 2024-03-06 09:15  
├─ ⚠️  Tokyo-DC2: 3 compute nodes C-states changed 1→6
├─ 📉 Performance impact detected (-15% latency)
└─ 🔍 Cause: Kernel update (5.15.1→5.15.3)

🕐 2024-03-05 16:45
├─ ✅ US-West: Network bonding mode corrected  
├─ 📈 Network throughput +25%
└─ 👤 Fixed by: ops-team-alice
```

### 4.2 Configuration Drift Map
```
Expected vs Actual Configuration

🎯 vm.swappiness = 1
┌─────────────────────────────────────────┐
│ Seoul:  ████████████████░░░░  80% (✓16 ✗4) │
│ Tokyo:  ████░░░░░░░░░░░░░░░░  20% (✓4 ✗16) │ 🚨
│ Sing:   ██████████████████░░  90% (✓18 ✗2) │
│ US-W:   ████████░░░░░░░░░░░░  40% (✓8 ✗12) │ ⚠️
└─────────────────────────────────────────┘
[Schedule fix for non-compliant servers]

🎯 CPU governor = performance  
┌─────────────────────────────────────────┐
│ Seoul:  ██████████████████████  100%     │ ✅
│ Tokyo:  ██████████████░░░░░░░░  70%      │
│ Sing:   ████████████████████░░  95%      │ 
│ US-W:   ██████████░░░░░░░░░░░░  50%      │ ⚠️
└─────────────────────────────────────────┘
```

## 5. Remediation Center: "Fix-It Hub"

### 5.1 Action Center
```
🔧 REMEDIATION ACTIONS

┌─ IMMEDIATE FIXES (No Downtime) ──────────────────────────────┐
│ ✅ sysctl parameter changes                                  │
│ ✅ Service configuration updates                             │  
│ ✅ Network buffer adjustments                                │
│ [🚀 APPLY ALL] [📝 Generate Script] [📋 Create Ticket]      │
└──────────────────────────────────────────────────────────────┘

┌─ SCHEDULED FIXES (Maintenance Required) ─────────────────────┐
│ ⚠️  Hugepages allocation (requires reboot)                   │
│ ⚠️  Kernel parameter changes (requires reboot)               │
│ ⚠️  Driver updates (requires downtime)                       │  
│ [📅 Schedule] [📋 Maintenance Plan] [👥 Assign Team]        │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Generated Ansible Playbook 
```yaml
---
# Generated by Infra-Auditor on 2024-03-07
# Fixes 23 compliance issues across 127 servers

- name: Seoul-DC1 Performance Optimization
  hosts: seoul_compute
  become: yes
  tasks:
    - name: Set vm.swappiness to 1
      sysctl:
        name: vm.swappiness
        value: '1'
        state: present
        reload: yes
        
    - name: Set CPU governor to performance
      shell: |
        echo performance > /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
      notify: persist_governor
      
  handlers:
    - name: persist_governor
      lineinfile:
        path: /etc/default/cpufrequtils
        line: 'GOVERNOR="performance"'
```

### 5.3 Batch Operations
```
📦 BATCH FIXES

🎯 Target: 45 servers in US-West region
🕒 Estimated time: 15 minutes  
🎨 Impact: +18% average compliance

┌─ Execution Plan ─────────────────────────┐
│ 1. Pre-flight checks        (2 min)     │
│ 2. Apply sysctl changes     (5 min)     │ 
│ 3. Restart services         (3 min)     │
│ 4. Validation scan          (5 min)     │
└──────────────────────────────────────────┘

[▶️ START] [⏸️ DRY RUN] [📋 REVIEW PLAN]
```

## 6. Anomaly Detection: "Outlier Finder"

### 6.1 Role-based Anomaly Detection
```
🔍 CONFIGURATION ANOMALIES

📊 Compute Servers (156 total)
┌─────────────────────────────────────────────────┐
│ Normal Pattern (142 servers):                   │
│ • vm.swappiness = 1                             │
│ • hugepages = 80% of RAM                        │ 
│ • CPU isolation = cores 0,1                     │
│                                                 │
│ 🚨 Outliers (14 servers):                      │
│ • comp-tokyo-15: swappiness=10 (manual override)│ ⚠️
│ • comp-seoul-03: no hugepages (hardware issue?) │ 🔥  
│ • comp-usw-08: different CPU isolation          │ ❓
│                                                 │
│ [INVESTIGATE] [APPROVE EXCEPTION] [STANDARDIZE] │
└─────────────────────────────────────────────────┘
```

### 6.2 Performance Correlation
```
📈 PERFORMANCE vs COMPLIANCE CORRELATION

    Performance Score
100 ┤     ⚬ ← Perfect configs
 90 ┤   ⚬⚬⚬⚬  
 80 ┤ ⚬⚬⚬⚬⚬⚬⚬    ← Most servers 
 70 ┤⚬⚬⚬⚬⚬⚬
 60 ┤⚬⚬⚬    🔥 ← Problematic outliers
 50 └─────────────────────────
    50  60  70  80  90  100
           Compliance %

💡 Insight: Servers below 75% compliance show 40% worse performance
🎯 Quick win: Fix top 10 outliers for +12% fleet performance
```

## 7. Advanced Features

### 7.1 Smart Recommendations
```
🧠 AI INSIGHTS

Based on your infrastructure pattern analysis:

💡 "Seoul region shows 23% better performance with 
   intel_pstate=disable. Consider applying to other regions."
   
💡 "Compute nodes with >1TB RAM benefit from 1GB hugepages.
   Currently only 34% are configured optimally."
   
💡 "Network role servers peak at 18:00 UTC daily.
   Schedule maintenance during 06:00-10:00 window."
   
[APPLY SUGGESTION] [DISMISS] [LEARN MORE]
```

### 7.2 Integration Hub
```
🔗 INTEGRATIONS

┌─ Monitoring ─────────────────────┐
│ 📊 Grafana dashboards           │
│ 🚨 AlertManager rules           │
│ 📈 Prometheus metrics           │  
└──────────────────────────────────┘

┌─ Automation ─────────────────────┐
│ 🤖 Ansible Tower jobs           │
│ 🔄 GitOps workflows             │
│ 📝 Terraform plans              │
└──────────────────────────────────┘

┌─ Ticketing ──────────────────────┐
│ 🎫 Jira integration             │
│ 📧 Email notifications          │
│ 💬 Slack alerts                │
└──────────────────────────────────┘
```

## 8. Mobile Responsive Design

### 8.1 모바일 우선 위젯
```
📱 Mobile Dashboard (Emergency Response)

┌─────────────────┐
│ 🚨 ALERTS (3)   │
│ ┌─────────────┐ │
│ │ 💥 Critical │ │
│ │ 23 servers  │ │  
│ │ [FIX NOW]   │ │
│ └─────────────┘ │
│                 │
│ 📊 Fleet Health │
│ ████░░░░░░ 67%  │
│                 │
│ [View All]      │
│ [Quick Actions] │
└─────────────────┘
```

## 9. Performance Considerations

### 9.1 실시간 업데이트
- WebSocket을 통한 실시간 상태 업데이트  
- 큰 변화만 푸시 (노이즈 최소화)
- 지역별 배치 업데이트

### 9.2 대용량 데이터 처리
- 가상 스크롤링 (대량 서버 목록)
- 지연 로딩 (상세 정보)
- 클라이언트 캐싱

### 9.3 Progressive Web App
- 오프라인 기본 정보 캐싱
- 백그라운드 동기화
- 네이티브 앱 경험

## 10. 접근성 및 사용성

### 10.1 키보드 네비게이션
- Tab 순서 최적화
- 단축키 지원 (Ctrl+F: 검색, Ctrl+R: 새로고침)
- 스크린 리더 지원

### 10.2 다국어 지원
- 한국어/영어 토글
- 지역별 시간대 자동 인식
- 현지화된 단위 표시

이 UI 설계는 **실제 운영자의 일상 워크플로우**를 고려하여, 문제 발견부터 해결까지의 시간을 최소화하는 것을 목표로 합니다. 예쁜 차트보다는 **액션을 취할 수 있는 정보**에 중점을 두어 설계되었습니다.