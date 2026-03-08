package rules

import (
	"testing"
)

func TestRulesPackage(t *testing.T) {
	// 기본 테스트: 패키지가 정상적으로 로드되는지 확인
	t.Log("rules 패키지 테스트 통과")

	// 규칙 엔진 생성 테스트
	engine := NewEngine()
	if engine == nil {
		t.Error("규칙 엔진 생성 실패")
	}
}