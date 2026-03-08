package report

import (
	"testing"
)

func TestReportPackage(t *testing.T) {
	// 기본 테스트: 패키지가 정상적으로 로드되는지 확인
	t.Log("report 패키지 테스트 통과")

	// 보고서 생성기 생성 테스트
	generator := NewGenerator("test-version", "test-schema")
	if generator == nil {
		t.Error("보고서 생성기 생성 실패")
	}
}