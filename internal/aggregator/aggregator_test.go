package aggregator

import (
	"os"
	"testing"
	"time"
)

func TestAggregatorPackage(t *testing.T) {
	// 기본 테스트: 패키지가 정상적으로 로드되는지 확인
	t.Log("aggregator 패키지 테스트 통과")
}

func TestStore(t *testing.T) {
	// 임시 디렉토리에서 스토어 테스트
	tmpDir := os.TempDir() + "/infra-auditor-test-" + 
		time.Now().Format("20060102150405")
	
	store, err := NewStore(tmpDir)
	if err != nil {
		t.Errorf("스토어 생성 실패: %v", err)
		return
	}
	defer os.RemoveAll(tmpDir)
	defer store.Close()

	// 통계 조회 테스트
	stats, err := store.GetStats()
	if err != nil {
		t.Errorf("통계 조회 실패: %v", err)
		return
	}

	if stats.TotalReports != 0 {
		t.Errorf("빈 스토어의 보고서 수가 0이 아님: %d", stats.TotalReports)
	}
}