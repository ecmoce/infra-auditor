package collector

import (
	"context"
	"encoding/json"
	"log/slog"
	"os/exec"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// OVSCollector는 Open vSwitch 관련 정보를 수집합니다.
type OVSCollector struct {
	*BaseCollector
}

// NewOVSCollector는 새 OVS 수집기를 생성합니다.
func NewOVSCollector() *OVSCollector {
	return &OVSCollector{
		BaseCollector: NewBaseCollector("ovs", "ovs"),
	}
}

// Collect는 OVS 관련 데이터를 수집합니다.
func (o *OVSCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("OVS 데이터 수집 시작")
	
	data := &types.OVSData{}
	
	// 브리지 정보
	if bridges, err := o.collectBridges(); err != nil {
		slog.Debug("OVS 브리지 수집 실패", "error", err)
	} else {
		data.Bridges = bridges
	}
	
	// 포트 정보
	if ports, err := o.collectPorts(); err != nil {
		slog.Debug("OVS 포트 수집 실패", "error", err)
	} else {
		data.Ports = ports
	}
	
	// OVS 버전
	if version, err := o.collectVersion(); err != nil {
		slog.Debug("OVS 버전 수집 실패", "error", err)
	} else {
		data.Version = version
	}
	
	slog.Debug("OVS 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 OVS 수집기가 사용 가능한지 확인합니다.
func (o *OVSCollector) IsAvailable() bool {
	_, err := exec.LookPath("ovs-vsctl")
	return err == nil
}

// collectBridges는 OVS 브리지 정보를 수집합니다.
func (o *OVSCollector) collectBridges() (json.RawMessage, error) {
	cmd := exec.Command("ovs-vsctl", "list", "bridge")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	return json.RawMessage(output), nil
}

// collectPorts는 OVS 포트 정보를 수집합니다.
func (o *OVSCollector) collectPorts() (json.RawMessage, error) {
	cmd := exec.Command("ovs-vsctl", "show")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	return json.RawMessage(output), nil
}

// collectVersion는 OVS 버전을 수집합니다.
func (o *OVSCollector) collectVersion() (string, error) {
	cmd := exec.Command("ovs-vsctl", "--version")
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	
	lines := strings.Split(string(output), "\n")
	if len(lines) > 0 {
		return strings.TrimSpace(lines[0]), nil
	}
	
	return "", nil
}