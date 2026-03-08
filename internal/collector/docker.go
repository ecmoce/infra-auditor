package collector

import (
	"context"
	"encoding/json"
	"log/slog"
	"os/exec"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// DockerCollector는 Docker 관련 정보를 수집합니다.
type DockerCollector struct {
	*BaseCollector
}

// NewDockerCollector는 새 Docker 수집기를 생성합니다.
func NewDockerCollector() *DockerCollector {
	return &DockerCollector{
		BaseCollector: NewBaseCollector("docker", "docker"),
	}
}

// Collect는 Docker 관련 데이터를 수집합니다.
func (d *DockerCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("Docker 데이터 수집 시작")
	
	data := &types.DockerData{}
	
	// Docker 컨테이너
	if containers, err := d.collectContainers(); err != nil {
		slog.Debug("컨테이너 정보 수집 실패", "error", err)
	} else {
		data.Containers = containers
	}
	
	// Docker 이미지
	if images, err := d.collectImages(); err != nil {
		slog.Debug("이미지 정보 수집 실패", "error", err)
	} else {
		data.Images = images
	}
	
	// Docker 정보
	if info, err := d.collectInfo(); err != nil {
		slog.Debug("Docker 정보 수집 실패", "error", err)
	} else {
		data.Info = info
	}
	
	slog.Debug("Docker 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 Docker 수집기가 사용 가능한지 확인합니다.
func (d *DockerCollector) IsAvailable() bool {
	_, err := exec.LookPath("docker")
	if err != nil {
		return false
	}
	
	// Docker 데몬이 실행 중인지 확인
	cmd := exec.Command("docker", "info")
	return cmd.Run() == nil
}

// collectContainers는 Docker 컨테이너 정보를 수집합니다.
func (d *DockerCollector) collectContainers() (json.RawMessage, error) {
	cmd := exec.Command("docker", "ps", "-a", "--format", "json")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	return json.RawMessage(output), nil
}

// collectImages는 Docker 이미지 정보를 수집합니다.
func (d *DockerCollector) collectImages() (json.RawMessage, error) {
	cmd := exec.Command("docker", "images", "--format", "json")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	return json.RawMessage(output), nil
}

// collectInfo는 Docker 시스템 정보를 수집합니다.
func (d *DockerCollector) collectInfo() (json.RawMessage, error) {
	cmd := exec.Command("docker", "info", "--format", "json")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	return json.RawMessage(output), nil
}