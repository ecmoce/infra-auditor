// package aggregator의 API 핸들러를 제공합니다.
package aggregator

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// APIHandler는 REST API 요청을 처리합니다.
type APIHandler struct {
	store *Store
}

// NewAPIHandler는 새로운 API 핸들러를 생성합니다.
func NewAPIHandler(store *Store) *APIHandler {
	return &APIHandler{
		store: store,
	}
}

// RegisterRoutes는 API 라우트를 등록합니다.
func (h *APIHandler) RegisterRoutes(mux *http.ServeMux) {
	// API v1 라우트
	mux.HandleFunc("/api/v1/reports", h.corsMiddleware(h.handleReports))
	mux.HandleFunc("/api/v1/reports/", h.corsMiddleware(h.handleReportByID))
	mux.HandleFunc("/api/v1/stats", h.corsMiddleware(h.handleStats))
	
	// 드리프트 분석 라우트
	mux.HandleFunc("/api/v1/drift", h.corsMiddleware(h.handleDriftAnalysis))
}

// corsMiddleware는 CORS 헤더를 추가합니다.
func (h *APIHandler) corsMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}
		
		next(w, r)
	}
}

// handleReports는 보고서 목록 조회 및 업로드를 처리합니다.
func (h *APIHandler) handleReports(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case "GET":
		h.getReports(w, r)
	case "POST":
		h.uploadReport(w, r)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

// getReports는 보고서 목록을 반환합니다.
func (h *APIHandler) getReports(w http.ResponseWriter, r *http.Request) {
	// 쿼리 파라미터 파싱
	query := r.URL.Query()
	hostname := query.Get("hostname")
	role := query.Get("role")
	limitStr := query.Get("limit")
	
	limit := 100 // 기본값
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil {
			limit = parsed
		}
	}

	reports, err := h.store.GetReports(hostname, role, limit)
	if err != nil {
		slog.Error("보고서 조회 실패", "error", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(map[string]interface{}{
		"reports": reports,
		"count":   len(reports),
	}); err != nil {
		slog.Error("응답 인코딩 실패", "error", err)
	}
}

// uploadReport는 새 보고서를 업로드합니다.
func (h *APIHandler) uploadReport(w http.ResponseWriter, r *http.Request) {
	var report types.Report
	if err := json.NewDecoder(r.Body).Decode(&report); err != nil {
		slog.Error("보고서 디코딩 실패", "error", err)
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// 보고서 유효성 검증
	if report.SystemInfo.Hostname == "" {
		http.Error(w, "Hostname is required", http.StatusBadRequest)
		return
	}

	// 타임스탬프 설정
	report.GeneratedAt = time.Now()

	id, err := h.store.SaveReport(&report)
	if err != nil {
		slog.Error("보고서 저장 실패", "error", err)
		http.Error(w, "Failed to save report", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"id":      id,
		"message": "Report uploaded successfully",
	})

	slog.Info("보고서 업로드 완료", 
		"id", id, 
		"hostname", report.SystemInfo.Hostname,
		"rules_count", len(report.RuleResults))
}

// handleReportByID는 특정 보고서 ID에 대한 요청을 처리합니다.
func (h *APIHandler) handleReportByID(w http.ResponseWriter, r *http.Request) {
	// URL에서 ID 추출
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/reports/")
	parts := strings.Split(path, "/")
	if len(parts) == 0 || parts[0] == "" {
		http.Error(w, "Report ID required", http.StatusBadRequest)
		return
	}

	id := parts[0]

	// 드리프트 분석 요청인지 확인
	if len(parts) > 1 && parts[1] == "drift" {
		h.getReportDrift(w, r, id)
		return
	}

	// 일반 보고서 조회
	h.getReportByID(w, r, id)
}

// getReportByID는 특정 보고서를 반환합니다.
func (h *APIHandler) getReportByID(w http.ResponseWriter, r *http.Request, id string) {
	report, err := h.store.GetReport(id)
	if err != nil {
		if err.Error() == "report not found" {
			http.Error(w, "Report not found", http.StatusNotFound)
		} else {
			slog.Error("보고서 조회 실패", "id", id, "error", err)
			http.Error(w, "Internal server error", http.StatusInternalServerError)
		}
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(report); err != nil {
		slog.Error("응답 인코딩 실패", "error", err)
	}
}

// getReportDrift는 특정 보고서의 드리프트 분석을 반환합니다.
func (h *APIHandler) getReportDrift(w http.ResponseWriter, r *http.Request, id string) {
	// 현재 보고서 조회
	currentReport, err := h.store.GetReport(id)
	if err != nil {
		if err.Error() == "report not found" {
			http.Error(w, "Report not found", http.StatusNotFound)
		} else {
			slog.Error("보고서 조회 실패", "id", id, "error", err)
			http.Error(w, "Internal server error", http.StatusInternalServerError)
		}
		return
	}

	// 같은 호스트의 이전 보고서 조회
	hostname := currentReport.SystemInfo.Hostname
	reportSummaries, err := h.store.GetReports(hostname, "", 2)
	if err != nil {
		slog.Error("이전 보고서 조회 실패", "hostname", hostname, "error", err)
		http.Error(w, "Failed to get previous reports", http.StatusInternalServerError)
		return
	}

	if len(reportSummaries) < 2 {
		http.Error(w, "Not enough reports for drift analysis", http.StatusBadRequest)
		return
	}

	// 이전 보고서의 전체 데이터 조회
	previousReport, err := h.store.GetReport(reportSummaries[1].ID)
	if err != nil {
		slog.Error("이전 보고서 상세 조회 실패", "id", reportSummaries[1].ID, "error", err)
		http.Error(w, "Failed to get previous report details", http.StatusInternalServerError)
		return
	}

	// 드리프트 분석 수행 (간단한 버전)
	driftResult := h.performSimpleDrift(previousReport, currentReport)

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(driftResult); err != nil {
		slog.Error("응답 인코딩 실패", "error", err)
	}
}

// handleStats는 통계 정보를 반환합니다.
func (h *APIHandler) handleStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	stats, err := h.store.GetStats()
	if err != nil {
		slog.Error("통계 조회 실패", "error", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(stats); err != nil {
		slog.Error("응답 인코딩 실패", "error", err)
	}
}

// handleDriftAnalysis는 두 보고서 간의 드리프트 분석을 처리합니다.
func (h *APIHandler) handleDriftAnalysis(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	query := r.URL.Query()
	previousID := query.Get("previous")
	currentID := query.Get("current")

	if previousID == "" || currentID == "" {
		http.Error(w, "Both previous and current report IDs required", http.StatusBadRequest)
		return
	}

	// 보고서들 조회
	previousReport, err := h.store.GetReport(previousID)
	if err != nil {
		http.Error(w, "Previous report not found", http.StatusNotFound)
		return
	}

	currentReport, err := h.store.GetReport(currentID)
	if err != nil {
		http.Error(w, "Current report not found", http.StatusNotFound)
		return
	}

	// 드리프트 분석 수행
	driftResult := h.performSimpleDrift(previousReport, currentReport)

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(driftResult); err != nil {
		slog.Error("응답 인코딩 실패", "error", err)
	}
}

// performSimpleDrift는 간단한 드리프트 분석을 수행합니다.
func (h *APIHandler) performSimpleDrift(previous, current *types.Report) map[string]interface{} {
	// 간단한 드리프트 분석 로직
	newIssues := 0
	resolvedIssues := 0
	
	// 현재 보고서의 실패한 규칙들
	currentFailed := make(map[string]bool)
	for _, result := range current.RuleResults {
		if result.Status == types.StatusFail {
			currentFailed[result.RuleID] = true
		}
	}

	// 이전 보고서의 실패한 규칙들
	previousFailed := make(map[string]bool)
	for _, result := range previous.RuleResults {
		if result.Status == types.StatusFail {
			previousFailed[result.RuleID] = true
		}
	}

	// 새로운 이슈와 해결된 이슈 카운트
	for ruleID := range currentFailed {
		if !previousFailed[ruleID] {
			newIssues++
		}
	}

	for ruleID := range previousFailed {
		if !currentFailed[ruleID] {
			resolvedIssues++
		}
	}

	return map[string]interface{}{
		"summary": map[string]interface{}{
			"new_issues":      newIssues,
			"resolved_issues": resolvedIssues,
			"total_changes":   newIssues + resolvedIssues,
			"drift_score":     float64(newIssues+resolvedIssues) / float64(len(current.RuleResults)) * 100,
		},
		"previous_report": map[string]interface{}{
			"id":        previous.ReportID,
			"timestamp": previous.GeneratedAt,
			"hostname":  previous.SystemInfo.Hostname,
		},
		"current_report": map[string]interface{}{
			"id":        current.ReportID,
			"timestamp": current.GeneratedAt,
			"hostname":  current.SystemInfo.Hostname,
		},
		"analysis_time": time.Now(),
	}
}