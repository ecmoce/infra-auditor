// Package types는 infra-auditor의 공통 타입 정의를 제공합니다.
package types

import (
	"encoding/json"
	"time"
)

// Severity는 이슈의 심각도를 나타냅니다.
type Severity string

const (
	SeverityCritical Severity = "critical"
	SeverityHigh     Severity = "high"
	SeverityMedium   Severity = "medium"
	SeverityLow      Severity = "low"
	SeverityInfo     Severity = "info"
)

// Status는 규칙 점검 결과 상태를 나타냅니다.
type Status string

const (
	StatusPass    Status = "pass"
	StatusFail    Status = "fail"
	StatusSkip    Status = "skip"
	StatusError   Status = "error"
	StatusUnknown Status = "unknown"
)

// Role은 서버의 역할을 나타냅니다.
type Role string

const (
	RoleCompute     Role = "compute"
	RoleController  Role = "controller"
	RoleNetwork     Role = "network"
	RoleStorage     Role = "storage"
	RoleDatabase    Role = "database"
	RoleWeb         Role = "web"
	RoleAuto        Role = "auto"
)

// SystemInfo는 시스템 기본 정보를 담습니다.
type SystemInfo struct {
	Hostname        string            `json:"hostname"`
	OS              string            `json:"os"`
	Kernel          string            `json:"kernel"`
	Architecture    string            `json:"architecture"`
	CPUCores        int               `json:"cpu_cores"`
	MemoryTotal     int64             `json:"memory_total"`
	DetectedRole    Role              `json:"detected_role"`
	Timestamp       time.Time         `json:"timestamp"`
	Environment     map[string]string `json:"environment,omitempty"`
}

// RuleResult는 개별 규칙 점검 결과를 나타냅니다.
type RuleResult struct {
	RuleID          string      `json:"rule_id"`
	RuleName        string      `json:"rule_name"`
	Category        string      `json:"category"`
	Status          Status      `json:"status"`
	Severity        Severity    `json:"severity"`
	CurrentValue    interface{} `json:"current_value,omitempty"`
	RecommendedValue interface{} `json:"recommended_value,omitempty"`
	Message         string      `json:"message"`
	Details         string      `json:"details,omitempty"`
	Remediation     string      `json:"remediation,omitempty"`
	References      []string    `json:"references,omitempty"`
	ExecutionTime   float64     `json:"execution_time_ms"`
	ErrorMessage    string      `json:"error_message,omitempty"`
}

// CollectorData는 수집된 시스템 데이터를 담습니다.
type CollectorData struct {
	CPU      *CPUData      `json:"cpu,omitempty"`
	Memory   *MemoryData   `json:"memory,omitempty"`
	Network  *NetworkData  `json:"network,omitempty"`
	Storage  *StorageData  `json:"storage,omitempty"`
	Kernel   *KernelData   `json:"kernel,omitempty"`
	Services *ServiceData  `json:"services,omitempty"`
	Docker   *DockerData   `json:"docker,omitempty"`
	SystemD  *SystemDData  `json:"systemd,omitempty"`
	OVS      *OVSData      `json:"ovs,omitempty"`
	Bonding  *BondingData  `json:"bonding,omitempty"`
}

// CPUData는 CPU 관련 수집 데이터입니다.
type CPUData struct {
	CPUInfo         json.RawMessage            `json:"cpuinfo"`
	Governor        string                     `json:"governor,omitempty"`
	ScalingDriver   string                     `json:"scaling_driver,omitempty"`
	MinFreq         int64                      `json:"min_freq,omitempty"`
	MaxFreq         int64                      `json:"max_freq,omitempty"`
	CurrentFreq     int64                      `json:"current_freq,omitempty"`
	Affinity        map[string]string          `json:"affinity,omitempty"`
	LoadAverage     [3]float64                 `json:"load_average"`
	Usage           map[string]float64         `json:"usage,omitempty"`
	ThermalState    string                     `json:"thermal_state,omitempty"`
	PowerManagement map[string]interface{}     `json:"power_management,omitempty"`
}

// MemoryData는 메모리 관련 수집 데이터입니다.
type MemoryData struct {
	MemInfo         json.RawMessage        `json:"meminfo"`
	VmStat          json.RawMessage        `json:"vmstat,omitempty"`
	Swappiness      int                    `json:"swappiness,omitempty"`
	HugePagesTotal  int                    `json:"hugepages_total,omitempty"`
	HugePagesFree   int                    `json:"hugepages_free,omitempty"`
	HugePagesSize   int                    `json:"hugepages_size,omitempty"`
	NumaStats       json.RawMessage        `json:"numa_stats,omitempty"`
	OOMKillCount    int                    `json:"oom_kill_count,omitempty"`
	Cgroups         map[string]interface{} `json:"cgroups,omitempty"`
}

// NetworkData는 네트워크 관련 수집 데이터입니다.
type NetworkData struct {
	Interfaces      json.RawMessage        `json:"interfaces"`
	Routes          json.RawMessage        `json:"routes,omitempty"`
	NetStat         json.RawMessage        `json:"netstat,omitempty"`
	TCPSettings     map[string]interface{} `json:"tcp_settings,omitempty"`
	BufferSizes     map[string]int         `json:"buffer_sizes,omitempty"`
	Firewall        json.RawMessage        `json:"firewall,omitempty"`
	Conntrack       map[string]interface{} `json:"conntrack,omitempty"`
}

// StorageData는 스토리지 관련 수집 데이터입니다.
type StorageData struct {
	DiskStats       json.RawMessage        `json:"diskstats"`
	Mounts          json.RawMessage        `json:"mounts,omitempty"`
	BlockDevices    json.RawMessage        `json:"block_devices,omitempty"`
	IOScheduler     map[string]string      `json:"io_scheduler,omitempty"`
	ReadAhead       map[string]int         `json:"read_ahead,omitempty"`
	QueueDepth      map[string]int         `json:"queue_depth,omitempty"`
	FileSystem      map[string]interface{} `json:"filesystem,omitempty"`
}

// KernelData는 커널 관련 수집 데이터입니다.
type KernelData struct {
	SysctlParams    map[string]string      `json:"sysctl_params"`
	Modules         json.RawMessage        `json:"modules,omitempty"`
	Version         string                 `json:"version"`
	CommandLine     string                 `json:"cmdline,omitempty"`
	LoadedModules   []string               `json:"loaded_modules,omitempty"`
	KernelConfig    map[string]interface{} `json:"kernel_config,omitempty"`
}

// ServiceData는 서비스 관련 수집 데이터입니다.
type ServiceData struct {
	RunningServices []ServiceInfo          `json:"running_services,omitempty"`
	ListeningPorts  []PortInfo             `json:"listening_ports,omitempty"`
	ProcessCount    int                    `json:"process_count,omitempty"`
	LoadedServices  map[string]interface{} `json:"loaded_services,omitempty"`
}

// SystemDData는 SystemD 관련 수집 데이터입니다.
type SystemDData struct {
	Units           json.RawMessage        `json:"units,omitempty"`
	FailedUnits     []string               `json:"failed_units,omitempty"`
	Services        json.RawMessage        `json:"services,omitempty"`
	Timers          json.RawMessage        `json:"timers,omitempty"`
	SystemState     string                 `json:"system_state,omitempty"`
	JournalSize     int64                  `json:"journal_size,omitempty"`
}

// DockerData는 Docker 관련 수집 데이터입니다.
type DockerData struct {
	Containers      json.RawMessage        `json:"containers,omitempty"`
	Images          json.RawMessage        `json:"images,omitempty"`
	Networks        json.RawMessage        `json:"networks,omitempty"`
	Volumes         json.RawMessage        `json:"volumes,omitempty"`
	Info            json.RawMessage        `json:"info,omitempty"`
	Version         string                 `json:"version,omitempty"`
	Stats           map[string]interface{} `json:"stats,omitempty"`
}

// OVSData는 Open vSwitch 관련 수집 데이터입니다.
type OVSData struct {
	Bridges         json.RawMessage        `json:"bridges,omitempty"`
	Ports           json.RawMessage        `json:"ports,omitempty"`
	Flows           json.RawMessage        `json:"flows,omitempty"`
	Controllers     json.RawMessage        `json:"controllers,omitempty"`
	Version         string                 `json:"version,omitempty"`
	Statistics      map[string]interface{} `json:"statistics,omitempty"`
}

// BondingData는 네트워크 본딩 관련 수집 데이터입니다.
type BondingData struct {
	Bonds           json.RawMessage        `json:"bonds,omitempty"`
	Slaves          json.RawMessage        `json:"slaves,omitempty"`
	Mode            string                 `json:"mode,omitempty"`
	Status          string                 `json:"status,omitempty"`
	ActiveSlave     string                 `json:"active_slave,omitempty"`
	Configuration   map[string]interface{} `json:"configuration,omitempty"`
}

// ServiceInfo는 개별 서비스 정보입니다.
type ServiceInfo struct {
	Name        string            `json:"name"`
	Status      string            `json:"status"`
	PID         int               `json:"pid,omitempty"`
	Memory      int64             `json:"memory,omitempty"`
	CPU         float64           `json:"cpu,omitempty"`
	StartTime   string            `json:"start_time,omitempty"`
	Description string            `json:"description,omitempty"`
	User        string            `json:"user,omitempty"`
	Metadata    map[string]string `json:"metadata,omitempty"`
}

// PortInfo는 개별 포트 정보입니다.
type PortInfo struct {
	Port        int    `json:"port"`
	Protocol    string `json:"protocol"`
	ProcessName string `json:"process_name,omitempty"`
	PID         int    `json:"pid,omitempty"`
	User        string `json:"user,omitempty"`
	State       string `json:"state,omitempty"`
	Address     string `json:"address,omitempty"`
}

// AuditReport는 전체 점검 결과 보고서입니다.
type AuditReport struct {
	ReportID        string         `json:"report_id"`
	SystemInfo      SystemInfo     `json:"system_info"`
	CollectorData   CollectorData  `json:"collector_data,omitempty"`
	RuleResults     []RuleResult   `json:"rule_results"`
	Summary         ReportSummary  `json:"summary"`
	Metadata        ReportMetadata `json:"metadata"`
	GeneratedAt     time.Time      `json:"generated_at"`
}

// ReportSummary는 보고서 요약 정보입니다.
type ReportSummary struct {
	TotalRules      int              `json:"total_rules"`
	PassedRules     int              `json:"passed_rules"`
	FailedRules     int              `json:"failed_rules"`
	SkippedRules    int              `json:"skipped_rules"`
	ErrorRules      int              `json:"error_rules"`
	SeverityCount   map[Severity]int `json:"severity_count"`
	CategoryCount   map[string]int   `json:"category_count"`
	ComplianceScore float64          `json:"compliance_score"`
	ExecutionTime   float64          `json:"execution_time_ms"`
}

// ReportMetadata는 보고서 메타데이터입니다.
type ReportMetadata struct {
	Version         string                 `json:"version"`
	Schema          string                 `json:"schema"`
	Generator       string                 `json:"generator"`
	TargetRole      Role                   `json:"target_role"`
	RulesetVersion  string                 `json:"ruleset_version"`
	Environment     string                 `json:"environment,omitempty"`
	Tags            []string               `json:"tags,omitempty"`
	CustomFields    map[string]interface{} `json:"custom_fields,omitempty"`
}

// DriftReport는 드리프트 분석 결과입니다.
type DriftReport struct {
	ReportID        string            `json:"report_id"`
	PreviousReport  string            `json:"previous_report"`
	CurrentReport   string            `json:"current_report"`
	Changes         []DriftChange     `json:"changes"`
	Summary         DriftSummary      `json:"summary"`
	GeneratedAt     time.Time         `json:"generated_at"`
}

// DriftChange는 개별 드리프트 변경사항입니다.
type DriftChange struct {
	RuleID          string      `json:"rule_id"`
	ChangeType      string      `json:"change_type"` // "status_change", "value_change", "new_rule", "removed_rule"
	PreviousStatus  Status      `json:"previous_status,omitempty"`
	CurrentStatus   Status      `json:"current_status,omitempty"`
	PreviousValue   interface{} `json:"previous_value,omitempty"`
	CurrentValue    interface{} `json:"current_value,omitempty"`
	Impact          Severity    `json:"impact"`
	Description     string      `json:"description"`
}

// DriftSummary는 드리프트 요약 정보입니다.
type DriftSummary struct {
	TotalChanges    int              `json:"total_changes"`
	StatusChanges   int              `json:"status_changes"`
	ValueChanges    int              `json:"value_changes"`
	NewIssues       int              `json:"new_issues"`
	ResolvedIssues  int              `json:"resolved_issues"`
	ImpactCount     map[Severity]int `json:"impact_count"`
	DriftScore      float64          `json:"drift_score"`
}

// RemediationScript는 자동 수정 스크립트입니다.
type RemediationScript struct {
	ScriptID        string           `json:"script_id"`
	TargetRules     []string         `json:"target_rules"`
	Commands        []Command        `json:"commands"`
	Prerequisites   []string         `json:"prerequisites,omitempty"`
	Risks           []string         `json:"risks,omitempty"`
	Backup          []BackupAction   `json:"backup,omitempty"`
	Verification    []Command        `json:"verification,omitempty"`
	Rollback        []Command        `json:"rollback,omitempty"`
	ExecutionTime   float64          `json:"execution_time_estimate_seconds"`
	RequiresReboot  bool             `json:"requires_reboot"`
	GeneratedAt     time.Time        `json:"generated_at"`
}

// Command는 실행할 명령어입니다.
type Command struct {
	Description     string            `json:"description"`
	Command         string            `json:"command"`
	WorkingDir      string            `json:"working_dir,omitempty"`
	Environment     map[string]string `json:"environment,omitempty"`
	Timeout         int               `json:"timeout_seconds,omitempty"`
	IgnoreErrors    bool              `json:"ignore_errors"`
	RequiresSudo    bool              `json:"requires_sudo"`
	Validation      string            `json:"validation,omitempty"`
}

// BackupAction는 백업 작업입니다.
type BackupAction struct {
	Type            string `json:"type"` // "file", "command", "service"
	Source          string `json:"source"`
	Destination     string `json:"destination,omitempty"`
	Command         string `json:"command,omitempty"`
	Description     string `json:"description"`
}

// Report는 AuditReport의 별칭입니다.
type Report = AuditReport