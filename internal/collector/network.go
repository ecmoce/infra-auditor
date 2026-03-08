package collector

import (
	"context"
	"encoding/json"
	"log/slog"
	"os"
	"os/exec"
	"strconv"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// NetworkCollector는 네트워크 관련 정보를 수집합니다.
type NetworkCollector struct {
	*BaseCollector
}

// NewNetworkCollector는 새 네트워크 수집기를 생성합니다.
func NewNetworkCollector() *NetworkCollector {
	return &NetworkCollector{
		BaseCollector: NewBaseCollector("network", "network"),
	}
}

// Collect는 네트워크 관련 데이터를 수집합니다.
func (n *NetworkCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("네트워크 데이터 수집 시작")
	
	data := &types.NetworkData{}
	
	// 1. 네트워크 인터페이스 정보
	if interfaces, err := n.collectInterfaces(); err != nil {
		slog.Warn("인터페이스 정보 수집 실패", "error", err)
	} else {
		data.Interfaces = interfaces
	}
	
	// 2. 라우팅 테이블
	if routes, err := n.collectRoutes(); err != nil {
		slog.Debug("라우팅 테이블 수집 실패", "error", err)
	} else {
		data.Routes = routes
	}
	
	// 3. 네트워크 통계
	if netstat, err := n.collectNetstat(); err != nil {
		slog.Debug("네트워크 통계 수집 실패", "error", err)
	} else {
		data.NetStat = netstat
	}
	
	// 4. TCP 설정
	if tcpSettings, err := n.collectTCPSettings(); err != nil {
		slog.Debug("TCP 설정 수집 실패", "error", err)
	} else {
		data.TCPSettings = tcpSettings
	}
	
	// 5. 버퍼 크기 설정
	if bufferSizes, err := n.collectBufferSizes(); err != nil {
		slog.Debug("버퍼 크기 수집 실패", "error", err)
	} else {
		data.BufferSizes = bufferSizes
	}
	
	// 6. 방화벽 정보
	if firewall, err := n.collectFirewall(); err != nil {
		slog.Debug("방화벽 정보 수집 실패", "error", err)
	} else {
		data.Firewall = firewall
	}
	
	// 7. Conntrack 설정
	if conntrack, err := n.collectConntrack(); err != nil {
		slog.Debug("conntrack 설정 수집 실패", "error", err)
	} else {
		data.Conntrack = conntrack
	}
	
	slog.Debug("네트워크 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 네트워크 수집기가 사용 가능한지 확인합니다.
func (n *NetworkCollector) IsAvailable() bool {
	_, err := os.Stat("/proc/net/dev")
	return err == nil
}

// collectInterfaces는 네트워크 인터페이스 정보를 수집합니다.
func (n *NetworkCollector) collectInterfaces() (json.RawMessage, error) {
	interfaces := make(map[string]interface{})
	
	// /proc/net/dev에서 인터페이스 통계
	if data, err := os.ReadFile("/proc/net/dev"); err == nil {
		interfaces["statistics"] = n.parseNetDev(string(data))
	}
	
	// ip link show 결과
	if cmd := exec.Command("ip", "link", "show"); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			interfaces["link_info"] = n.parseIpLink(string(output))
		}
	}
	
	// ip addr show 결과
	if cmd := exec.Command("ip", "addr", "show"); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			interfaces["addr_info"] = n.parseIpAddr(string(output))
		}
	}
	
	return json.Marshal(interfaces)
}

func (n *NetworkCollector) parseNetDev(data string) map[string]interface{} {
	result := make(map[string]interface{})
	
	lines := strings.Split(data, "\n")
	if len(lines) < 3 {
		return result
	}
	
	// 헤더 스킵하고 인터페이스 정보 파싱
	for _, line := range lines[2:] {
		if strings.TrimSpace(line) == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) >= 17 {
			ifaceName := strings.TrimSuffix(fields[0], ":")
			ifaceStats := map[string]interface{}{
				"rx_bytes":      parseIntSafe(fields[1]),
				"rx_packets":    parseIntSafe(fields[2]),
				"rx_errs":       parseIntSafe(fields[3]),
				"rx_drop":       parseIntSafe(fields[4]),
				"tx_bytes":      parseIntSafe(fields[9]),
				"tx_packets":    parseIntSafe(fields[10]),
				"tx_errs":       parseIntSafe(fields[11]),
				"tx_drop":       parseIntSafe(fields[12]),
			}
			result[ifaceName] = ifaceStats
		}
	}
	
	return result
}

func (n *NetworkCollector) parseIpLink(data string) []map[string]string {
	var result []map[string]string
	
	lines := strings.Split(data, "\n")
	var currentIface map[string]string
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		if strings.Contains(line, ":") && !strings.HasPrefix(line, " ") {
			if currentIface != nil {
				result = append(result, currentIface)
			}
			currentIface = make(map[string]string)
			
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				currentIface["name"] = strings.TrimSuffix(parts[1], ":")
				if len(parts) >= 3 {
					currentIface["flags"] = parts[2]
				}
			}
		} else if currentIface != nil {
			// 추가 정보 파싱
			if strings.Contains(line, "link/") {
				currentIface["link"] = line
			}
		}
	}
	
	if currentIface != nil {
		result = append(result, currentIface)
	}
	
	return result
}

func (n *NetworkCollector) parseIpAddr(data string) []map[string]interface{} {
	var result []map[string]interface{}
	
	lines := strings.Split(data, "\n")
	var currentIface map[string]interface{}
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		if strings.Contains(line, ":") && !strings.HasPrefix(line, " ") {
			if currentIface != nil {
				result = append(result, currentIface)
			}
			currentIface = make(map[string]interface{})
			
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				currentIface["name"] = strings.TrimSuffix(parts[1], ":")
				currentIface["addresses"] = []string{}
			}
		} else if currentIface != nil && strings.Contains(line, "inet") {
			if addresses, ok := currentIface["addresses"].([]string); ok {
				currentIface["addresses"] = append(addresses, line)
			}
		}
	}
	
	if currentIface != nil {
		result = append(result, currentIface)
	}
	
	return result
}

// collectRoutes는 라우팅 테이블 정보를 수집합니다.
func (n *NetworkCollector) collectRoutes() (json.RawMessage, error) {
	routes := make(map[string]interface{})
	
	// ip route show
	if cmd := exec.Command("ip", "route", "show"); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			routes["ipv4"] = strings.Split(strings.TrimSpace(string(output)), "\n")
		}
	}
	
	// ip -6 route show
	if cmd := exec.Command("ip", "-6", "route", "show"); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			routes["ipv6"] = strings.Split(strings.TrimSpace(string(output)), "\n")
		}
	}
	
	return json.Marshal(routes)
}

// collectNetstat는 네트워크 통계를 수집합니다.
func (n *NetworkCollector) collectNetstat() (json.RawMessage, error) {
	netstat := make(map[string]interface{})
	
	// /proc/net/snmp
	if data, err := os.ReadFile("/proc/net/snmp"); err == nil {
		netstat["snmp"] = n.parseSnmp(string(data))
	}
	
	// /proc/net/netstat
	if data, err := os.ReadFile("/proc/net/netstat"); err == nil {
		netstat["netstat"] = n.parseNetstat(string(data))
	}
	
	return json.Marshal(netstat)
}

func (n *NetworkCollector) parseSnmp(data string) map[string]interface{} {
	result := make(map[string]interface{})
	
	lines := strings.Split(data, "\n")
	for i := 0; i < len(lines)-1; i += 2 {
		headerLine := strings.TrimSpace(lines[i])
		dataLine := strings.TrimSpace(lines[i+1])
		
		if headerLine == "" || dataLine == "" {
			continue
		}
		
		headers := strings.Fields(headerLine)
		values := strings.Fields(dataLine)
		
		if len(headers) > 0 && len(headers) == len(values) {
			protocol := headers[0]
			protocolData := make(map[string]interface{})
			
			for j := 1; j < len(headers); j++ {
				protocolData[headers[j]] = parseIntSafe(values[j])
			}
			
			result[protocol] = protocolData
		}
	}
	
	return result
}

func (n *NetworkCollector) parseNetstat(data string) map[string]interface{} {
	return n.parseSnmp(data) // 같은 형식
}

// collectTCPSettings는 TCP 관련 설정을 수집합니다.
func (n *NetworkCollector) collectTCPSettings() (map[string]interface{}, error) {
	settings := make(map[string]interface{})
	
	tcpParams := []string{
		"tcp_congestion_control",
		"tcp_window_scaling",
		"tcp_timestamps",
		"tcp_sack",
		"tcp_fack",
		"tcp_syncookies",
		"tcp_fin_timeout",
		"tcp_keepalive_time",
		"tcp_keepalive_probes",
		"tcp_keepalive_intvl",
		"tcp_max_syn_backlog",
		"tcp_max_tw_buckets",
	}
	
	for _, param := range tcpParams {
		if data, err := os.ReadFile("/proc/sys/net/ipv4/" + param); err == nil {
			value := strings.TrimSpace(string(data))
			if intVal, err := strconv.Atoi(value); err == nil {
				settings[param] = intVal
			} else {
				settings[param] = value
			}
		}
	}
	
	return settings, nil
}

// collectBufferSizes는 네트워크 버퍼 크기 설정을 수집합니다.
func (n *NetworkCollector) collectBufferSizes() (map[string]int, error) {
	bufferSizes := make(map[string]int)
	
	bufferParams := map[string]string{
		"rmem_default":     "/proc/sys/net/core/rmem_default",
		"rmem_max":         "/proc/sys/net/core/rmem_max",
		"wmem_default":     "/proc/sys/net/core/wmem_default",
		"wmem_max":         "/proc/sys/net/core/wmem_max",
		"netdev_max_backlog": "/proc/sys/net/core/netdev_max_backlog",
	}
	
	for key, path := range bufferParams {
		if data, err := os.ReadFile(path); err == nil {
			if value, err := strconv.Atoi(strings.TrimSpace(string(data))); err == nil {
				bufferSizes[key] = value
			}
		}
	}
	
	return bufferSizes, nil
}

// collectFirewall는 방화벽 정보를 수집합니다.
func (n *NetworkCollector) collectFirewall() (json.RawMessage, error) {
	firewall := make(map[string]interface{})
	
	// iptables 규칙 확인
	if cmd := exec.Command("iptables", "-L", "-n"); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			firewall["iptables"] = strings.Split(strings.TrimSpace(string(output)), "\n")
		}
	}
	
	// firewalld 상태 확인
	if cmd := exec.Command("firewall-cmd", "--state"); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			firewall["firewalld_state"] = strings.TrimSpace(string(output))
		}
	}
	
	return json.Marshal(firewall)
}

// collectConntrack는 conntrack 설정을 수집합니다.
func (n *NetworkCollector) collectConntrack() (map[string]interface{}, error) {
	conntrack := make(map[string]interface{})
	
	conntrackParams := map[string]string{
		"max":     "/proc/sys/net/netfilter/nf_conntrack_max",
		"count":   "/proc/sys/net/netfilter/nf_conntrack_count",
		"buckets": "/proc/sys/net/netfilter/nf_conntrack_buckets",
	}
	
	for key, path := range conntrackParams {
		if data, err := os.ReadFile(path); err == nil {
			if value, err := strconv.Atoi(strings.TrimSpace(string(data))); err == nil {
				conntrack[key] = value
			}
		}
	}
	
	return conntrack, nil
}

func parseIntSafe(s string) interface{} {
	if val, err := strconv.ParseInt(s, 10, 64); err == nil {
		return val
	}
	return s
}