// Package collector는 시스템 정보 수집 기능을 제공합니다.
package collector

import (
	"context"
	"log/slog"
	"time"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Collector는 시스템 데이터 수집기 인터페이스입니다.
type Collector interface {
	// Name은 수집기 이름을 반환합니다.
	Name() string
	
	// Category는 수집기 카테고리를 반환합니다.
	Category() string
	
	// Collect는 데이터를 수집하고 결과를 반환합니다.
	Collect(ctx context.Context) (interface{}, error)
	
	// IsAvailable은 현재 시스템에서 수집 가능한지 확인합니다.
	IsAvailable() bool
}

// BaseCollector는 공통 수집기 기능을 제공하는 기본 구조체입니다.
type BaseCollector struct {
	name     string
	category string
}

// NewBaseCollector는 새 기본 수집기를 생성합니다.
func NewBaseCollector(name, category string) *BaseCollector {
	return &BaseCollector{
		name:     name,
		category: category,
	}
}

// Name은 수집기 이름을 반환합니다.
func (bc *BaseCollector) Name() string {
	return bc.name
}

// Category는 수집기 카테고리를 반환합니다.
func (bc *BaseCollector) Category() string {
	return bc.category
}

// Manager는 여러 수집기를 관리하는 매니저입니다.
type Manager struct {
	collectors map[string]Collector
}

// NewManager는 새 수집기 매니저를 생성합니다.
func NewManager() *Manager {
	return &Manager{
		collectors: make(map[string]Collector),
	}
}

// Register는 수집기를 등록합니다.
func (m *Manager) Register(collector Collector) {
	m.collectors[collector.Name()] = collector
	slog.Debug("수집기 등록됨", "name", collector.Name(), "category", collector.Category())
}

// CollectAll은 모든 사용 가능한 수집기를 실행하여 데이터를 수집합니다.
func (m *Manager) CollectAll(ctx context.Context, categories []string) (*types.CollectorData, error) {
	slog.Info("데이터 수집 시작", "total_collectors", len(m.collectors))
	
	data := &types.CollectorData{}
	
	for name, collector := range m.collectors {
		// 카테고리 필터 적용
		if len(categories) > 0 && !contains(categories, collector.Category()) {
			slog.Debug("카테고리 필터로 인해 수집기 건너뜀", "name", name, "category", collector.Category())
			continue
		}
		
		// 사용 가능성 확인
		if !collector.IsAvailable() {
			slog.Debug("수집기 사용 불가능", "name", name)
			continue
		}
		
		start := time.Now()
		
		result, err := collector.Collect(ctx)
		if err != nil {
			slog.Warn("데이터 수집 실패", "name", name, "error", err)
			continue
		}
		
		duration := time.Since(start)
		slog.Debug("데이터 수집 완료", "name", name, "duration_ms", duration.Milliseconds())
		
		// 결과를 적절한 필드에 할당
		if err := assignCollectorData(data, collector.Category(), result); err != nil {
			slog.Warn("데이터 할당 실패", "name", name, "error", err)
			continue
		}
	}
	
	slog.Info("데이터 수집 완료")
	return data, nil
}

// GetCollector는 지정된 이름의 수집기를 반환합니다.
func (m *Manager) GetCollector(name string) (Collector, bool) {
	collector, exists := m.collectors[name]
	return collector, exists
}

// ListCollectors는 등록된 모든 수집기 목록을 반환합니다.
func (m *Manager) ListCollectors() map[string]Collector {
	result := make(map[string]Collector)
	for name, collector := range m.collectors {
		result[name] = collector
	}
	return result
}

// assignCollectorData는 수집된 데이터를 적절한 필드에 할당합니다.
func assignCollectorData(data *types.CollectorData, category string, result interface{}) error {
	switch category {
	case "cpu":
		if cpuData, ok := result.(*types.CPUData); ok {
			data.CPU = cpuData
		}
	case "memory":
		if memData, ok := result.(*types.MemoryData); ok {
			data.Memory = memData
		}
	case "network":
		if netData, ok := result.(*types.NetworkData); ok {
			data.Network = netData
		}
	case "storage":
		if storageData, ok := result.(*types.StorageData); ok {
			data.Storage = storageData
		}
	case "kernel":
		if kernelData, ok := result.(*types.KernelData); ok {
			data.Kernel = kernelData
		}
	case "service":
		if serviceData, ok := result.(*types.ServiceData); ok {
			data.Services = serviceData
		}
	case "docker":
		if dockerData, ok := result.(*types.DockerData); ok {
			data.Docker = dockerData
		}
	case "systemd":
		if systemdData, ok := result.(*types.SystemDData); ok {
			data.SystemD = systemdData
		}
	case "ovs":
		if ovsData, ok := result.(*types.OVSData); ok {
			data.OVS = ovsData
		}
	case "bonding":
		if bondingData, ok := result.(*types.BondingData); ok {
			data.Bonding = bondingData
		}
	default:
		slog.Warn("알 수 없는 카테고리", "category", category)
	}
	
	return nil
}

// contains는 슬라이스에 특정 문자열이 포함되어 있는지 확인합니다.
func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

// CreateDefaultManager는 기본 수집기들이 등록된 매니저를 생성합니다.
func CreateDefaultManager() *Manager {
	manager := NewManager()
	
	// 모든 기본 수집기 등록
	manager.Register(NewCPUCollector())
	manager.Register(NewMemoryCollector())
	manager.Register(NewNetworkCollector())
	manager.Register(NewStorageCollector())
	manager.Register(NewKernelCollector())
	manager.Register(NewServiceCollector())
	manager.Register(NewDockerCollector())
	manager.Register(NewSystemDCollector())
	manager.Register(NewOVSCollector())
	manager.Register(NewBondingCollector())
	
	return manager
}