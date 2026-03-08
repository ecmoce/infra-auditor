#!/bin/bash

# Docker 통합 테스트 스크립트
# 4개 OS에서 infra-auditor Go 버전 테스트

set -e

echo "=== Docker 통합 테스트 시작 ==="

# 결과 파일 초기화
RESULTS_FILE="docker-test-results.md"
cat > $RESULTS_FILE << 'EOF'
# Docker 통합 테스트 결과

| OS | 바이너리 실행 | Scan | Report | 파일 크기 | 수행 시간 |
|----|-------------|------|--------|----------|----------|
EOF

# 테스트 함수
test_os() {
    local image=$1
    local os_name=$2
    local install_cmd=$3
    
    echo "=== $os_name 테스트 시작 ==="
    
    # 임시 컨테이너 실행
    local container_id
    container_id=$(docker run -d \
        -v $(pwd)/infra-auditor-linux-amd64:/usr/local/bin/infra-auditor:ro \
        -v /proc:/host/proc:ro \
        -v /sys:/host/sys:ro \
        $image sleep 300)
    
    echo "컨테이너 ID: $container_id"
    
    # 필요한 패키지 설치
    if [ -n "$install_cmd" ]; then
        echo "패키지 설치 중..."
        docker exec $container_id sh -c "$install_cmd" || echo "패키지 설치 실패 (계속 진행)"
    fi
    
    # 바이너리 복사 및 실행 권한 설정
    docker exec $container_id cp /usr/local/bin/infra-auditor /tmp/infra-auditor
    docker exec $container_id chmod +x /tmp/infra-auditor
    
    # 버전 확인
    echo "버전 확인:"
    if docker exec $container_id /tmp/infra-auditor version; then
        binary_test="✅"
    else
        binary_test="❌"
    fi
    
    # 스캔 테스트
    echo "스캔 테스트:"
    local scan_start=$(date +%s)
    if docker exec $container_id /tmp/infra-auditor scan --role auto --output /tmp/report.json; then
        scan_test="✅"
    else
        scan_test="❌"
    fi
    local scan_end=$(date +%s)
    local duration=$((scan_end - scan_start))
    
    # 리포트 파일 확인
    echo "리포트 확인:"
    if docker exec $container_id test -f /tmp/report.json; then
        report_test="✅"
        # 파일 크기 확인
        file_size=$(docker exec $container_id stat -c%s /tmp/report.json 2>/dev/null || echo "N/A")
        echo "리포트 샘플:"
        docker exec $container_id head -3 /tmp/report.json 2>/dev/null || echo "리포트 내용 확인 실패"
    else
        report_test="❌"
        file_size="N/A"
    fi
    
    # 결과 기록
    echo "| $os_name | $binary_test | $scan_test | $report_test | $file_size bytes | ${duration}s |" >> $RESULTS_FILE
    
    # 컨테이너 정리
    docker rm -f $container_id > /dev/null
    
    echo "$os_name 테스트 완료"
    echo
}

# CentOS 7 테스트 (EOL이므로 vault 사용)
test_os "centos:7" "CentOS 7" "
    sed -i 's|^mirrorlist=|#mirrorlist=|g' /etc/yum.repos.d/CentOS-*.repo 2>/dev/null || true;
    sed -i 's|^#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-*.repo 2>/dev/null || true;
    yum install -y procps-ng net-tools 2>/dev/null || echo 'CentOS 7 package install failed'
"

# Ubuntu 22.04 테스트
test_os "ubuntu:22.04" "Ubuntu 22.04" "
    apt-get update > /dev/null 2>&1 || true;
    apt-get install -y --no-install-recommends procps net-tools > /dev/null 2>&1 || true
"

# Ubuntu 24.04 테스트
test_os "ubuntu:24.04" "Ubuntu 24.04" "
    apt-get update > /dev/null 2>&1 || true;
    apt-get install -y --no-install-recommends procps net-tools > /dev/null 2>&1 || true
"

# Rocky 9 테스트
test_os "rockylinux:9" "Rocky 9" "
    dnf install -y procps-ng net-tools > /dev/null 2>&1 || true
"

# Alpine 테스트 (추가)
test_os "alpine:3.19" "Alpine 3.19" "
    apk add --no-cache procps > /dev/null 2>&1 || true
"

echo "=== 모든 테스트 완료 ==="
echo
echo "결과 요약:"
cat $RESULTS_FILE

# Git에 결과 기록
if [ -f $RESULTS_FILE ]; then
    echo
    echo "결과를 git에 기록합니다..."
    git add $RESULTS_FILE
fi

echo
echo "Docker 테스트 완료!"