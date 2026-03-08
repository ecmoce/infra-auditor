package collector

import (
	"context"
	"encoding/json"
	"log/slog"
	"os"
	"path/filepath"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// BondingCollector는 네트워크 본딩 관련 정보를 수집합니다.
type BondingCollector struct {
	*BaseCollector
}

// NewBondingCollector는 새 본딩 수집기를 생성합니다.
func NewBondingCollector() *BondingCollector {
	return &BondingCollector{
		BaseCollector: NewBaseCollector("bonding", "bonding"),
	}
}

// Collect는 본딩 관련 데이터를 수집합니다.
func (b *BondingCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("본딩 데이터 수집 시작")
	
	data := &types.BondingData{}
	
	// 본딩 인터페이스 정보
	if bonds, err := b.collectBonds(); err != nil {
		slog.Debug("본딩 정보 수집 실패", "error", err)
	} else {
		data.Bonds = bonds
	}
	
	// 슬레이브 정보
	if slaves, err := b.collectSlaves(); err != nil {
		slog.Debug("슬레이브 정보 수집 실패", "error", err)
	} else {
		data.Slaves = slaves
	}
	
	slog.Debug("본딩 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 본딩 수집기가 사용 가능한지 확인합니다.
func (b *BondingCollector) IsAvailable() bool {
	_, err := os.Stat("/proc/net/bonding")
	return err == nil
}

// collectBonds는 본딩 인터페이스 정보를 수집합니다.
func (b *BondingCollector) collectBonds() (json.RawMessage, error) {
	bonds := make(map[string]interface{})
	
	// /proc/net/bonding 디렉토리에서 본딩 인터페이스 찾기
	bondFiles, err := filepath.Glob("/proc/net/bonding/bond*")
	if err != nil {
		return nil, err
	}
	
	for _, bondFile := range bondFiles {
		bondName := filepath.Base(bondFile)
		
		if data, err := os.ReadFile(bondFile); err == nil {
			bonds[bondName] = b.parseBondingInfo(string(data))
		}
	}
	
	return json.Marshal(bonds)
}

// collectSlaves는 슬레이브 인터페이스 정보를 수집합니다.
func (b *BondingCollector) collectSlaves() (json.RawMessage, error) {
	slaves := make(map[string]interface{})
	
	// /sys/class/net/*/bonding 에서 슬레이브 정보 수집
	bondDirs, err := filepath.Glob("/sys/class/net/*/bonding")
	if err != nil {
		return nil, err
	}
	
	for _, bondDir := range bondDirs {
		bondName := filepath.Base(filepath.Dir(bondDir))
		
		// slaves 파일 읽기
		slavesFile := filepath.Join(bondDir, "slaves")
		if data, err := os.ReadFile(slavesFile); err == nil {
			slaveList := strings.Fields(strings.TrimSpace(string(data)))
			slaves[bondName] = slaveList
		}
	}
	
	return json.Marshal(slaves)
}

// parseBondingInfo는 본딩 정보를 파싱합니다.
func (b *BondingCollector) parseBondingInfo(data string) map[string]interface{} {
	info := make(map[string]interface{})
	
	lines := strings.Split(data, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		if strings.Contains(line, ":") {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 {
				key := strings.TrimSpace(parts[0])
				value := strings.TrimSpace(parts[1])
				info[key] = value
			}
		}
	}
	
	return info
}