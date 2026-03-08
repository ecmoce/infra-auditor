.PHONY: build test clean lint docker-build docker-up docker-down install benchmark all

# Go 빌드 설정
BINARY_NAME=infra-auditor
MAIN_PATH=./cmd/infra-auditor
BUILD_FLAGS=-ldflags="-s -w" -trimpath
VERSION?=$(shell git describe --tags --always --dirty)
SCHEMA=1.0.0

# CGO 비활성화 (정적 바이너리)
export CGO_ENABLED=0

# ── Development ─────────────────────────────────
all: build test

build:
	@echo "🔨 Building $(BINARY_NAME)..."
	go build $(BUILD_FLAGS) -o $(BINARY_NAME) $(MAIN_PATH)

build-linux:
	@echo "🐧 Building for Linux..."
	GOOS=linux GOARCH=amd64 go build $(BUILD_FLAGS) -o $(BINARY_NAME)-linux-amd64 $(MAIN_PATH)

build-all:
	@echo "🌍 Building for all platforms..."
	GOOS=linux GOARCH=amd64 go build $(BUILD_FLAGS) -o $(BINARY_NAME)-linux-amd64 $(MAIN_PATH)
	GOOS=linux GOARCH=arm64 go build $(BUILD_FLAGS) -o $(BINARY_NAME)-linux-arm64 $(MAIN_PATH)
	GOOS=darwin GOARCH=amd64 go build $(BUILD_FLAGS) -o $(BINARY_NAME)-darwin-amd64 $(MAIN_PATH)
	GOOS=darwin GOARCH=arm64 go build $(BUILD_FLAGS) -o $(BINARY_NAME)-darwin-arm64 $(MAIN_PATH)
	GOOS=windows GOARCH=amd64 go build $(BUILD_FLAGS) -o $(BINARY_NAME)-windows-amd64.exe $(MAIN_PATH)

test:
	@echo "🧪 Running tests..."
	go test -v ./...

test-coverage:
	@echo "📊 Running tests with coverage..."
	go test -v -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html

lint:
	@echo "🔍 Running linters..."
	go fmt ./...
	go vet ./...
	@if command -v golangci-lint >/dev/null 2>&1; then \
		golangci-lint run; \
	else \
		echo "golangci-lint not found, install with: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"; \
	fi

deps:
	@echo "📦 Installing dependencies..."
	go mod download
	go mod tidy

clean:
	@echo "🧹 Cleaning..."
	go clean
	rm -f $(BINARY_NAME) $(BINARY_NAME)-*
	rm -f coverage.out coverage.html

install: build
	@echo "📥 Installing $(BINARY_NAME)..."
	sudo cp $(BINARY_NAME) /usr/local/bin/

uninstall:
	@echo "🗑️  Uninstalling $(BINARY_NAME)..."
	sudo rm -f /usr/local/bin/$(BINARY_NAME)

# ── Testing & Validation ────────────────────────
benchmark: build
	@echo "⚡ Running benchmark..."
	@time ./$(BINARY_NAME) version
	@echo "Scan benchmark (requires Linux):"
	@if [ "$(shell uname)" = "Linux" ]; then \
		time ./$(BINARY_NAME) scan --collect-only > /dev/null; \
	else \
		echo "Skipping scan benchmark on non-Linux platform"; \
	fi

verify: build test
	@echo "✅ Running verification..."
	./$(BINARY_NAME) version
	@echo "Build verification complete!"

# ── Docker ──────────────────────────────────────
docker-build:
	@echo "🐳 Building Docker images..."
	docker build -f Dockerfile.agent -t infra-auditor:latest .
	docker build -f Dockerfile.aggregator -t infra-auditor-aggregator:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

# ── Git Operations ──────────────────────────────
commit-build: test
	@echo "🚀 Committing Go rebuild..."
	git add .
	git commit -m "feat: complete Go rebuild and aggregator implementation

- ✅ Fix all build errors (missing imports, field names)
- ✅ Create internal/aggregator package (server, API, store)
- ✅ Add basic test coverage for all packages
- ✅ Static binary build with CGO_ENABLED=0
- ✅ File-based storage (no external dependencies)
- ✅ REST API for report management and drift analysis
- ✅ Update Makefile for Go workflow

Co-authored-by: Go Migration Agent <agent@openclaw>"

push: commit-build
	@echo "📤 Pushing to remote..."
	git push origin HEAD

# ── Help ────────────────────────────────────────
help:
	@echo "🛠️  Infra Auditor Makefile Commands:"
	@echo ""
	@echo "Build:"
	@echo "  build         Build binary for current platform"
	@echo "  build-linux   Build binary for Linux amd64"
	@echo "  build-all     Build for all supported platforms"
	@echo ""
	@echo "Development:"
	@echo "  test          Run all tests"
	@echo "  test-coverage Run tests with coverage report"
	@echo "  lint          Format code and run linters"
	@echo "  deps          Download and tidy dependencies"
	@echo "  clean         Clean build artifacts"
	@echo ""
	@echo "Installation:"
	@echo "  install       Install binary to /usr/local/bin"
	@echo "  uninstall     Remove binary from /usr/local/bin"
	@echo ""
	@echo "Validation:"
	@echo "  benchmark     Run performance benchmarks"
	@echo "  verify        Build + test + basic verification"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build  Build Docker images"
	@echo "  docker-up     Start services with docker-compose"
	@echo "  docker-down   Stop services"
	@echo ""
	@echo "Git:"
	@echo "  commit-build  Test + commit build results"
	@echo "  push          Commit + push to remote"