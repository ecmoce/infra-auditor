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

# ── Deployment ──────────────────────────────────
deploy-single:
	@echo "🚀 Deploying to single server via SCP..."
	@if [ -z "$(HOST)" ]; then \
		echo "❌ HOST variable required. Usage: make deploy-single HOST=server.example.com"; \
		exit 1; \
	fi
	@if [ ! -f $(BINARY_NAME)-linux-amd64 ]; then \
		echo "Building Linux binary..."; \
		make build-linux; \
	fi
	@echo "Uploading binary to $(HOST)..."
	scp $(BINARY_NAME)-linux-amd64 $(HOST):/tmp/$(BINARY_NAME)
	ssh $(HOST) "sudo mv /tmp/$(BINARY_NAME) /usr/local/bin/$(BINARY_NAME) && sudo chmod +x /usr/local/bin/$(BINARY_NAME)"
	ssh $(HOST) "/usr/local/bin/$(BINARY_NAME) --version"
	@echo "✅ Deployment to $(HOST) complete!"

deploy-ansible:
	@echo "🤖 Deploying via Ansible..."
	@if [ ! -d "deploy/ansible" ]; then \
		echo "❌ Ansible deployment files not found"; \
		exit 1; \
	fi
	cd deploy/ansible && ansible-playbook -i inventory/production/ deploy.yml

deploy-ansible-staging:
	@echo "🧪 Deploying to staging via Ansible..."
	cd deploy/ansible && ansible-playbook -i inventory/staging/ deploy.yml

deploy-check:
	@echo "🔍 Checking deployment readiness..."
	@echo "Ansible configuration:"
	cd deploy/ansible && ansible --version
	@echo "Inventory check:"
	cd deploy/ansible && ansible-inventory --list

scan-all:
	@echo "🔍 Running scan across all servers..."
	cd deploy/ansible && ansible-playbook -i inventory/production/ scan.yml

scan-staging:
	@echo "🔍 Running scan on staging servers..."
	cd deploy/ansible && ansible-playbook -i inventory/staging/ scan.yml

upgrade-all:
	@echo "🔄 Running rolling upgrade..."
	cd deploy/ansible && ansible-playbook -i inventory/production/ upgrade.yml

upgrade-staging:
	@echo "🔄 Upgrading staging environment..."
	cd deploy/ansible && ansible-playbook -i inventory/staging/ upgrade.yml

# ── Release ──────────────────────────────────────
release-check:
	@echo "🏷️  Checking release readiness..."
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ VERSION required. Usage: make release-tag VERSION=v1.0.0"; \
		exit 1; \
	fi
	@echo "Current version: $(shell git describe --tags --always)"
	@echo "New version: $(VERSION)"
	@echo "Uncommitted changes:"
	@git status --porcelain || echo "Working directory clean"

release-tag:
	@echo "🏷️  Creating release tag..."
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ VERSION required. Usage: make release-tag VERSION=v1.0.0"; \
		exit 1; \
	fi
	make verify
	git tag -a $(VERSION) -m "Release $(VERSION)"
	git push origin $(VERSION)
	@echo "✅ Tag $(VERSION) created and pushed!"
	@echo "GitHub Actions will now build and create the release."

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
	@echo ""
	@echo "Deployment:"
	@echo "  deploy-single HOST=server  Deploy to single server via SCP"
	@echo "  deploy-ansible             Deploy via Ansible (production)"
	@echo "  deploy-ansible-staging     Deploy to staging environment"
	@echo "  deploy-check               Check deployment readiness"
	@echo ""
	@echo "Operations:"
	@echo "  scan-all      Run scans across all servers"
	@echo "  scan-staging  Run scans on staging"
	@echo "  upgrade-all   Rolling upgrade (production)"
	@echo "  upgrade-staging  Upgrade staging environment"
	@echo ""
	@echo "Release:"
	@echo "  release-check VERSION=v1.0.0   Check release readiness"
	@echo "  release-tag VERSION=v1.0.0     Create and push release tag"