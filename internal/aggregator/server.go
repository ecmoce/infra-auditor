// package aggregator는 중앙 집중식 서버를 제공하여 
// 여러 에이전트로부터 보고서를 수집하고 관리합니다.
package aggregator

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"
)

// Config는 Aggregator 서버 설정을 정의합니다.
type Config struct {
	Host     string // 바인드 주소
	Port     int    // 포트 번호
	DBPath   string // 데이터베이스 파일 경로
	Config   string // 설정 파일 경로
	EnableUI bool   // 웹 UI 활성화 여부
}

// Server는 Aggregator HTTP 서버입니다.
type Server struct {
	config   Config
	store    *Store
	api      *APIHandler
	server   *http.Server
}

// NewServer는 새로운 Aggregator 서버를 생성합니다.
func NewServer(config Config) (*Server, error) {
	// 스토어 초기화
	store, err := NewStore(config.DBPath)
	if err != nil {
		return nil, fmt.Errorf("스토어 초기화 실패: %w", err)
	}

	// API 핸들러 초기화
	api := NewAPIHandler(store)

	// HTTP 서버 설정
	mux := http.NewServeMux()
	api.RegisterRoutes(mux)

	// 웹 UI 활성화 시 정적 파일 서비스
	if config.EnableUI {
		registerUIRoutes(mux)
	}

	server := &http.Server{
		Addr:         config.Host + ":" + strconv.Itoa(config.Port),
		Handler:      mux,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	return &Server{
		config: config,
		store:  store,
		api:    api,
		server: server,
	}, nil
}

// Start는 서버를 시작합니다.
func (s *Server) Start() error {
	slog.Info("Aggregator 서버 시작", 
		"address", s.server.Addr,
		"ui_enabled", s.config.EnableUI)

	// Graceful shutdown을 위한 채널
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	// 서버를 고루틴에서 실행
	go func() {
		if err := s.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("서버 시작 실패", "error", err)
			quit <- syscall.SIGTERM
		}
	}()

	slog.Info("서버가 시작되었습니다", "address", s.server.Addr)
	if s.config.EnableUI {
		slog.Info("웹 UI 접속 가능", "url", fmt.Sprintf("http://%s", s.server.Addr))
	}

	// 종료 신호 대기
	<-quit
	slog.Info("서버 종료 신호를 받았습니다...")

	// 30초 타임아웃으로 graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := s.server.Shutdown(ctx); err != nil {
		slog.Error("서버 종료 실패", "error", err)
		return err
	}

	// 스토어 정리
	if err := s.store.Close(); err != nil {
		slog.Error("스토어 종료 실패", "error", err)
		return err
	}

	slog.Info("서버가 정상적으로 종료되었습니다")
	return nil
}

// Stop은 서버를 강제 종료합니다.
func (s *Server) Stop() error {
	return s.server.Close()
}

// registerUIRoutes는 웹 UI 라우트를 등록합니다.
func registerUIRoutes(mux *http.ServeMux) {
	// 기본 페이지
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" {
			http.Redirect(w, r, "/dashboard", http.StatusFound)
			return
		}
		http.NotFound(w, r)
	})

	// 대시보드 페이지
	mux.HandleFunc("/dashboard", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, getBasicDashboard())
	})

	// Health check
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","service":"infra-auditor-aggregator"}`)
	})
}

// getBasicDashboard는 기본 대시보드 HTML을 반환합니다.
func getBasicDashboard() string {
	return `<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Infra Auditor - Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; }
        .header { border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }
        .api-docs { background: #f5f5f5; padding: 15px; border-radius: 5px; }
        .endpoint { margin: 10px 0; padding: 10px; background: white; border-radius: 3px; }
        .method { font-weight: bold; color: #0066cc; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛠 Infra Auditor Aggregator</h1>
        <p>중앙 집중식 인프라 감사 보고서 수집 및 관리 서버</p>
    </div>
    
    <h2>📊 대시보드</h2>
    <p>웹 대시보드는 향후 릴리스에서 제공될 예정입니다.</p>
    
    <h2>🔌 API 엔드포인트</h2>
    <div class="api-docs">
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/v1/reports</code> - 보고서 목록 조회
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/v1/reports</code> - 새 보고서 업로드
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/v1/reports/{id}</code> - 특정 보고서 조회
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/v1/reports/{id}/drift</code> - 드리프트 분석
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/health</code> - 서비스 상태 확인
        </div>
    </div>
</body>
</html>`
}