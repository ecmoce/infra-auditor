// Package detector는 시스템 분석을 통한 서버 역할 자동 감지 기능을 제공합니다.
package detector

import (
	"bufio"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// DetectRole은 시스템을 분석하여 서버 역할을 자동으로 감지합니다.
func DetectRole() (types.Role, error) {
	slog.Debug("서버 역할 감지 시작")

	// 역할별 점수 계산
	scores := map[types.Role]int{
		types.RoleCompute:    0,
		types.RoleController: 0,
		types.RoleNetwork:    0,
		types.RoleStorage:    0,
		types.RoleDatabase:   0,
		types.RoleWeb:        0,
	}

	// 1. CPU 코어 수 확인 (Compute 역할 지표)
	if cpuCores, err := getCPUCores(); err == nil {
		if cpuCores >= 16 {
			scores[types.RoleCompute] += 3
		} else if cpuCores >= 8 {
			scores[types.RoleCompute] += 2
		} else if cpuCores >= 4 {
			scores[types.RoleCompute] += 1
		}
		slog.Debug("CPU 코어 수 확인", "cores", cpuCores)
	}

	// 2. 메모리 용량 확인 (Compute/Database 역할 지표)
	if memoryGB, err := getMemorySize(); err == nil {
		if memoryGB >= 64 {
			scores[types.RoleCompute] += 2
			scores[types.RoleDatabase] += 3
		} else if memoryGB >= 32 {
			scores[types.RoleCompute] += 1
			scores[types.RoleDatabase] += 2
		} else if memoryGB >= 16 {
			scores[types.RoleDatabase] += 1
		}
		slog.Debug("메모리 용량 확인", "memory_gb", memoryGB)
	}

	// 3. 네트워크 인터페이스 확인 (Network 역할 지표)
	if networkInterfaces, err := getNetworkInterfaces(); err == nil {
		if len(networkInterfaces) >= 4 {
			scores[types.RoleNetwork] += 3
		} else if len(networkInterfaces) >= 3 {
			scores[types.RoleNetwork] += 2
		} else if len(networkInterfaces) >= 2 {
			scores[types.RoleNetwork] += 1
		}
		slog.Debug("네트워크 인터페이스 확인", "count", len(networkInterfaces))
	}

	// 4. 스토리지 장치 확인 (Storage 역할 지표)
	if storageDevices, err := getStorageDevices(); err == nil {
		if len(storageDevices) >= 8 {
			scores[types.RoleStorage] += 3
		} else if len(storageDevices) >= 4 {
			scores[types.RoleStorage] += 2
		} else if len(storageDevices) >= 2 {
			scores[types.RoleStorage] += 1
		}
		slog.Debug("스토리지 장치 확인", "count", len(storageDevices))
	}

	// 5. 실행 중인 서비스 확인
	if services, err := getRunningServices(); err == nil {
		analyzeServices(services, scores)
		slog.Debug("서비스 분석 완료", "services_count", len(services))
	}

	// 6. 리스닝 포트 확인
	if ports, err := getListeningPorts(); err == nil {
		analyzePorts(ports, scores)
		slog.Debug("포트 분석 완료", "ports_count", len(ports))
	}

	// 7. 설치된 패키지 확인 (OpenStack, Kubernetes 등)
	if packages, err := getInstalledPackages(); err == nil {
		analyzePackages(packages, scores)
		slog.Debug("패키지 분석 완료", "packages_count", len(packages))
	}

	// 8. 프로세스 확인
	if processes, err := getRunningProcesses(); err == nil {
		analyzeProcesses(processes, scores)
		slog.Debug("프로세스 분석 완료", "processes_count", len(processes))
	}

	// 최고 점수 역할 선택
	maxScore := 0
	detectedRole := types.RoleCompute // 기본값

	for role, score := range scores {
		slog.Debug("역할 점수", "role", role, "score", score)
		if score > maxScore {
			maxScore = score
			detectedRole = role
		}
	}

	// 모든 점수가 낮으면 Compute로 설정
	if maxScore < 2 {
		slog.Info("명확한 역할 감지 안됨, Compute로 설정", "max_score", maxScore)
		return types.RoleCompute, nil
	}

	slog.Info("서버 역할 감지 완료", "role", detectedRole, "score", maxScore)
	return detectedRole, nil
}

// getCPUCores는 CPU 코어 수를 반환합니다.
func getCPUCores() (int, error) {
	data, err := os.ReadFile("/proc/cpuinfo")
	if err != nil {
		return 0, err
	}

	cores := 0
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "processor") {
			cores++
		}
	}

	return cores, nil
}

// getMemorySize는 메모리 크기를 GB 단위로 반환합니다.
func getMemorySize() (int, error) {
	data, err := os.ReadFile("/proc/meminfo")
	if err != nil {
		return 0, err
	}

	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "MemTotal:") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				memKB, err := strconv.Atoi(fields[1])
				if err != nil {
					return 0, err
				}
				return memKB / 1024 / 1024, nil // KB -> GB
			}
		}
	}

	return 0, fmt.Errorf("MemTotal not found in /proc/meminfo")
}

// getNetworkInterfaces는 네트워크 인터페이스 목록을 반환합니다.
func getNetworkInterfaces() ([]string, error) {
	data, err := os.ReadFile("/proc/net/dev")
	if err != nil {
		return nil, err
	}

	var interfaces []string
	lines := strings.Split(string(data), "\n")
	
	for _, line := range lines[2:] { // 헤더 스킵
		if strings.TrimSpace(line) == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) > 0 {
			iface := strings.TrimSuffix(fields[0], ":")
			// lo, docker 등 가상 인터페이스 제외
			if !strings.HasPrefix(iface, "lo") && 
			   !strings.HasPrefix(iface, "docker") &&
			   !strings.HasPrefix(iface, "veth") {
				interfaces = append(interfaces, iface)
			}
		}
	}

	return interfaces, nil
}

// getStorageDevices는 스토리지 장치 목록을 반환합니다.
func getStorageDevices() ([]string, error) {
	data, err := os.ReadFile("/proc/diskstats")
	if err != nil {
		return nil, err
	}

	var devices []string
	deviceMap := make(map[string]bool)
	
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		fields := strings.Fields(line)
		if len(fields) >= 3 {
			device := fields[2]
			// 파티션 번호가 없는 디스크만 (sda, sdb, nvme0n1 등)
			if matched, _ := regexp.MatchString(`^(sd[a-z]|nvme\d+n\d+|xvd[a-z])$`, device); matched {
				if !deviceMap[device] {
					devices = append(devices, device)
					deviceMap[device] = true
				}
			}
		}
	}

	return devices, nil
}

// getRunningServices는 실행 중인 시스템 서비스 목록을 반환합니다.
func getRunningServices() ([]string, error) {
	cmd := exec.Command("systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--no-legend")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	var services []string
	scanner := bufio.NewScanner(strings.NewReader(string(output)))
	
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		fields := strings.Fields(line)
		if len(fields) > 0 {
			serviceName := fields[0]
			services = append(services, serviceName)
		}
	}

	return services, nil
}

// getListeningPorts는 리스닝 포트 목록을 반환합니다.
func getListeningPorts() ([]int, error) {
	cmd := exec.Command("ss", "-tlnp")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	var ports []int
	portMap := make(map[int]bool)
	
	scanner := bufio.NewScanner(strings.NewReader(string(output)))
	for scanner.Scan() {
		line := scanner.Text()
		if strings.Contains(line, "LISTEN") {
			fields := strings.Fields(line)
			if len(fields) >= 4 {
				address := fields[3]
				if colonIdx := strings.LastIndex(address, ":"); colonIdx != -1 {
					portStr := address[colonIdx+1:]
					if port, err := strconv.Atoi(portStr); err == nil && port > 0 {
						if !portMap[port] {
							ports = append(ports, port)
							portMap[port] = true
						}
					}
				}
			}
		}
	}

	return ports, nil
}

// getInstalledPackages는 설치된 패키지 목록을 반환합니다.
func getInstalledPackages() ([]string, error) {
	var cmd *exec.Cmd
	
	// RPM 기반 시스템 (RHEL, CentOS, Fedora)
	if _, err := exec.LookPath("rpm"); err == nil {
		cmd = exec.Command("rpm", "-qa", "--queryformat", "%{NAME}\n")
	} else if _, err := exec.LookPath("dpkg"); err == nil {
		// Debian 기반 시스템 (Ubuntu, Debian)
		cmd = exec.Command("dpkg-query", "-f", "${Package}\n", "-W")
	} else {
		return nil, fmt.Errorf("지원되지 않는 패키지 관리자")
	}

	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	var packages []string
	scanner := bufio.NewScanner(strings.NewReader(string(output)))
	
	for scanner.Scan() {
		pkg := strings.TrimSpace(scanner.Text())
		if pkg != "" {
			packages = append(packages, pkg)
		}
	}

	return packages, nil
}

// getRunningProcesses는 실행 중인 프로세스 목록을 반환합니다.
func getRunningProcesses() ([]string, error) {
	cmd := exec.Command("ps", "-eo", "comm", "--no-headers")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	var processes []string
	processMap := make(map[string]bool)
	
	scanner := bufio.NewScanner(strings.NewReader(string(output)))
	for scanner.Scan() {
		process := strings.TrimSpace(scanner.Text())
		if process != "" && !processMap[process] {
			processes = append(processes, process)
			processMap[process] = true
		}
	}

	return processes, nil
}

// analyzeServices는 서비스 목록을 분석하여 역할 점수를 업데이트합니다.
func analyzeServices(services []string, scores map[types.Role]int) {
	for _, service := range services {
		serviceLower := strings.ToLower(service)
		
		// OpenStack 관련 서비스 (Controller)
		if strings.Contains(serviceLower, "keystone") ||
		   strings.Contains(serviceLower, "glance") ||
		   strings.Contains(serviceLower, "nova-api") ||
		   strings.Contains(serviceLower, "neutron-server") ||
		   strings.Contains(serviceLower, "cinder-api") ||
		   strings.Contains(serviceLower, "heat") {
			scores[types.RoleController] += 2
		}

		// Nova Compute (Compute)
		if strings.Contains(serviceLower, "nova-compute") ||
		   strings.Contains(serviceLower, "libvirtd") ||
		   strings.Contains(serviceLower, "qemu") {
			scores[types.RoleCompute] += 3
		}

		// Network 서비스 (Network)
		if strings.Contains(serviceLower, "neutron-l3") ||
		   strings.Contains(serviceLower, "neutron-dhcp") ||
		   strings.Contains(serviceLower, "openvswitch") ||
		   strings.Contains(serviceLower, "ovs-") {
			scores[types.RoleNetwork] += 2
		}

		// Storage 서비스 (Storage)
		if strings.Contains(serviceLower, "cinder-volume") ||
		   strings.Contains(serviceLower, "swift") ||
		   strings.Contains(serviceLower, "ceph") ||
		   strings.Contains(serviceLower, "gluster") {
			scores[types.RoleStorage] += 2
		}

		// Database 서비스 (Database)
		if strings.Contains(serviceLower, "mysql") ||
		   strings.Contains(serviceLower, "mariadb") ||
		   strings.Contains(serviceLower, "postgresql") ||
		   strings.Contains(serviceLower, "mongodb") ||
		   strings.Contains(serviceLower, "redis") ||
		   strings.Contains(serviceLower, "galera") {
			scores[types.RoleDatabase] += 2
		}

		// Web 서비스 (Web)
		if strings.Contains(serviceLower, "httpd") ||
		   strings.Contains(serviceLower, "apache") ||
		   strings.Contains(serviceLower, "nginx") ||
		   strings.Contains(serviceLower, "tomcat") {
			scores[types.RoleWeb] += 2
		}
	}
}

// analyzePorts는 리스닝 포트를 분석하여 역할 점수를 업데이트합니다.
func analyzePorts(ports []int, scores map[types.Role]int) {
	for _, port := range ports {
		switch port {
		// OpenStack API 포트 (Controller)
		case 5000, 9292, 8774, 9696, 8776, 8004:
			scores[types.RoleController] += 1
		
		// Database 포트 (Database)
		case 3306, 5432, 27017, 6379, 4567:
			scores[types.RoleDatabase] += 2
		
		// Web 서버 포트 (Web)
		case 80, 443, 8080, 8443:
			scores[types.RoleWeb] += 1
		
		// Ceph 포트 (Storage)
		case 6800, 6801, 6802, 6803, 6804, 6805:
			scores[types.RoleStorage] += 1
		}
	}
}

// analyzePackages는 설치된 패키지를 분석하여 역할 점수를 업데이트합니다.
func analyzePackages(packages []string, scores map[types.Role]int) {
	for _, pkg := range packages {
		pkgLower := strings.ToLower(pkg)
		
		// OpenStack 패키지 확인
		if strings.Contains(pkgLower, "openstack") {
			if strings.Contains(pkgLower, "nova-compute") {
				scores[types.RoleCompute] += 3
			} else if strings.Contains(pkgLower, "nova-api") ||
					  strings.Contains(pkgLower, "keystone") ||
					  strings.Contains(pkgLower, "glance") {
				scores[types.RoleController] += 2
			} else if strings.Contains(pkgLower, "neutron") {
				scores[types.RoleNetwork] += 2
			} else if strings.Contains(pkgLower, "cinder") ||
					  strings.Contains(pkgLower, "swift") {
				scores[types.RoleStorage] += 2
			}
		}

		// Kubernetes 패키지
		if strings.Contains(pkgLower, "kubernetes") ||
		   strings.Contains(pkgLower, "kubelet") ||
		   strings.Contains(pkgLower, "docker") ||
		   strings.Contains(pkgLower, "containerd") {
			scores[types.RoleCompute] += 2
		}

		// Database 패키지
		if strings.Contains(pkgLower, "mysql") ||
		   strings.Contains(pkgLower, "mariadb") ||
		   strings.Contains(pkgLower, "postgresql") {
			scores[types.RoleDatabase] += 2
		}

		// Storage 관련 패키지
		if strings.Contains(pkgLower, "ceph") ||
		   strings.Contains(pkgLower, "glusterfs") ||
		   strings.Contains(pkgLower, "lvm") {
			scores[types.RoleStorage] += 1
		}

		// Network 관련 패키지
		if strings.Contains(pkgLower, "openvswitch") ||
		   strings.Contains(pkgLower, "bridge-utils") {
			scores[types.RoleNetwork] += 1
		}
	}
}

// analyzeProcesses는 실행 중인 프로세스를 분석하여 역할 점수를 업데이트합니다.
func analyzeProcesses(processes []string, scores map[types.Role]int) {
	for _, process := range processes {
		processLower := strings.ToLower(process)
		
		// 가상화 관련 프로세스 (Compute)
		if strings.Contains(processLower, "qemu") ||
		   strings.Contains(processLower, "kvm") ||
		   strings.Contains(processLower, "libvirtd") ||
		   strings.Contains(processLower, "dockerd") ||
		   strings.Contains(processLower, "containerd") {
			scores[types.RoleCompute] += 1
		}

		// Database 프로세스 (Database)
		if strings.Contains(processLower, "mysqld") ||
		   strings.Contains(processLower, "postgres") ||
		   strings.Contains(processLower, "mongod") ||
		   strings.Contains(processLower, "redis-server") {
			scores[types.RoleDatabase] += 2
		}

		// Web 서버 프로세스 (Web)
		if strings.Contains(processLower, "httpd") ||
		   strings.Contains(processLower, "nginx") ||
		   strings.Contains(processLower, "apache") {
			scores[types.RoleWeb] += 1
		}

		// Storage 프로세스 (Storage)
		if strings.Contains(processLower, "ceph") ||
		   strings.Contains(processLower, "gluster") {
			scores[types.RoleStorage] += 1
		}
	}
}