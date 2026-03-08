#!/bin/bash
# infra-auditor 설치 스크립트
# 사용법: curl -fsSL https://raw.githubusercontent.com/ecmoce/infra-auditor/main/install.sh | sh

set -euo pipefail

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 설정
GITHUB_REPO="ecmoce/infra-auditor"
GITHUB_API="https://api.github.com/repos/${GITHUB_REPO}"
INSTALL_DIR="/usr/local/bin"
TEMP_DIR=$(mktemp -d)
BINARY_NAME="infra-auditor"

# 로깅 함수
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

debug() {
    if [[ "${DEBUG:-}" == "1" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# 정리 함수
cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
        debug "임시 디렉토리 정리: $TEMP_DIR"
    fi
}

# 종료 시 정리
trap cleanup EXIT

# 시스템 정보 감지
detect_system() {
    # OS 감지
    case "$(uname -s)" in
        Linux*)  OS="linux" ;;
        Darwin*) OS="darwin" ;;
        *)       error "지원하지 않는 OS: $(uname -s)" ;;
    esac
    
    # 아키텍처 감지
    case "$(uname -m)" in
        x86_64|amd64) ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
        armv7l|armv6l) ARCH="arm" ;;
        *) error "지원하지 않는 아키텍처: $(uname -m)" ;;
    esac
    
    debug "감지된 시스템: ${OS}-${ARCH}"
}

# 권한 확인
check_permissions() {
    if [[ ! -w "$INSTALL_DIR" ]]; then
        if [[ $EUID -ne 0 ]]; then
            error "설치에 root 권한이 필요합니다. sudo를 사용해주세요."
        fi
    fi
}

# 의존성 확인
check_dependencies() {
    local deps=("curl" "tar" "gzip")
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            error "필수 프로그램이 없습니다: $dep"
        fi
    done
    
    debug "의존성 확인 완료"
}

# 최신 릴리즈 버전 가져오기
get_latest_version() {
    log "최신 릴리즈 버전 확인 중..."
    
    local release_data
    if ! release_data=$(curl -fsSL "${GITHUB_API}/releases/latest" 2>/dev/null); then
        error "GitHub API에서 릴리즈 정보를 가져올 수 없습니다"
    fi
    
    # jq가 있으면 사용, 없으면 grep/sed로 파싱
    if command -v jq >/dev/null 2>&1; then
        VERSION=$(echo "$release_data" | jq -r '.tag_name')
        DOWNLOAD_URL=$(echo "$release_data" | jq -r ".assets[] | select(.name == \"${BINARY_NAME}-${OS}-${ARCH}\") | .browser_download_url")
        CHECKSUM_URL=$(echo "$release_data" | jq -r ".assets[] | select(.name == \"checksums.txt\") | .browser_download_url")
    else
        VERSION=$(echo "$release_data" | grep -o '"tag_name": *"[^"]*"' | grep -o '"[^"]*"$' | sed 's/"//g')
        DOWNLOAD_URL=$(echo "$release_data" | grep -o "\"browser_download_url\": *\"[^\"]*${BINARY_NAME}-${OS}-${ARCH}\"" | grep -o 'https://[^"]*')
        CHECKSUM_URL=$(echo "$release_data" | grep -o "\"browser_download_url\": *\"[^\"]*checksums.txt\"" | grep -o 'https://[^"]*')
    fi
    
    if [[ -z "$VERSION" || -z "$DOWNLOAD_URL" ]]; then
        error "릴리즈 정보를 파싱할 수 없습니다. (OS: $OS, ARCH: $ARCH)"
    fi
    
    log "최신 버전: $VERSION"
    debug "다운로드 URL: $DOWNLOAD_URL"
}

# 기존 설치 확인
check_existing() {
    if [[ -f "${INSTALL_DIR}/${BINARY_NAME}" ]]; then
        local existing_version
        if existing_version=$("${INSTALL_DIR}/${BINARY_NAME}" --version 2>/dev/null); then
            log "기존 설치 발견: $existing_version"
            
            if [[ "$existing_version" == *"$VERSION"* ]]; then
                log "이미 최신 버전이 설치되어 있습니다."
                if [[ "${FORCE:-}" != "1" ]]; then
                    log "강제 재설치하려면 FORCE=1을 설정하세요."
                    exit 0
                fi
            fi
            
            # 백업 생성
            log "기존 바이너리 백업 중..."
            cp "${INSTALL_DIR}/${BINARY_NAME}" "${INSTALL_DIR}/${BINARY_NAME}.backup.$(date +%Y%m%d_%H%M%S)"
        fi
    fi
}

# 바이너리 다운로드
download_binary() {
    log "바이너리 다운로드 중: ${BINARY_NAME}-${OS}-${ARCH}"
    
    cd "$TEMP_DIR"
    
    if ! curl -fsSL -o "${BINARY_NAME}" "$DOWNLOAD_URL"; then
        error "바이너리 다운로드 실패: $DOWNLOAD_URL"
    fi
    
    # 체크섬 파일 다운로드
    if [[ -n "$CHECKSUM_URL" ]]; then
        log "체크섬 파일 다운로드 중..."
        if curl -fsSL -o "checksums.txt" "$CHECKSUM_URL"; then
            # 체크섬 검증
            local expected_checksum
            expected_checksum=$(grep "${BINARY_NAME}-${OS}-${ARCH}" checksums.txt | awk '{print $1}')
            
            if [[ -n "$expected_checksum" ]]; then
                log "체크섬 검증 중..."
                local actual_checksum
                actual_checksum=$(sha256sum "${BINARY_NAME}" | awk '{print $1}')
                
                if [[ "$actual_checksum" == "$expected_checksum" ]]; then
                    log "체크섬 검증 성공"
                else
                    error "체크섬 불일치. 파일이 손상되었을 수 있습니다."
                fi
            else
                warn "체크섬을 찾을 수 없습니다."
            fi
        else
            warn "체크섬 파일 다운로드 실패"
        fi
    fi
    
    # 실행 권한 설정
    chmod +x "${BINARY_NAME}"
    
    # 바이너리 테스트
    log "바이너리 테스트 중..."
    if ! ./"${BINARY_NAME}" --version >/dev/null 2>&1; then
        error "다운로드한 바이너리가 실행되지 않습니다"
    fi
}

# 바이너리 설치
install_binary() {
    log "바이너리 설치 중: ${INSTALL_DIR}/${BINARY_NAME}"
    
    # 디렉토리 생성 (필요한 경우)
    mkdir -p "$INSTALL_DIR"
    
    # 바이너리 복사
    cp "${TEMP_DIR}/${BINARY_NAME}" "${INSTALL_DIR}/${BINARY_NAME}"
    
    # 소유권 및 권한 설정
    chown root:root "${INSTALL_DIR}/${BINARY_NAME}" 2>/dev/null || true
    chmod 755 "${INSTALL_DIR}/${BINARY_NAME}"
}

# 설치 확인
verify_installation() {
    log "설치 확인 중..."
    
    if [[ ! -x "${INSTALL_DIR}/${BINARY_NAME}" ]]; then
        error "설치된 바이너리가 실행 가능하지 않습니다"
    fi
    
    local installed_version
    if ! installed_version=$("${INSTALL_DIR}/${BINARY_NAME}" --version 2>/dev/null); then
        error "설치된 바이너리가 실행되지 않습니다"
    fi
    
    log "설치 완료: $installed_version"
}

# PATH 확인 및 안내
check_path() {
    if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
        warn "주의: $INSTALL_DIR이 PATH에 없습니다."
        warn "다음 명령을 실행하여 PATH에 추가하세요:"
        warn "echo 'export PATH=\"$INSTALL_DIR:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
        warn ""
    fi
}

# 사용법 안내
show_usage() {
    log ""
    log "🎉 infra-auditor 설치 완료!"
    log ""
    log "사용법:"
    log "  ${BINARY_NAME} --help                 # 도움말 보기"
    log "  ${BINARY_NAME} --version              # 버전 확인"
    log "  ${BINARY_NAME} --role control         # OpenStack 컨트롤러 감사"
    log "  ${BINARY_NAME} --role compute         # OpenStack 컴퓨트 감사"
    log ""
    log "문서: https://github.com/${GITHUB_REPO}/blob/main/README.md"
    log ""
}

# 메인 함수
main() {
    log "🚀 infra-auditor 설치 시작"
    log "GitHub: https://github.com/${GITHUB_REPO}"
    log ""
    
    detect_system
    check_permissions
    check_dependencies
    get_latest_version
    check_existing
    download_binary
    install_binary
    verify_installation
    check_path
    show_usage
}

# 스크립트 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi