"""CLI interface using Click framework."""

import json
import sys

import click

import infra_auditor
from infra_auditor.drift import DriftDetector
from infra_auditor.remediation import RemediationGenerator
from infra_auditor.report import Report
from infra_auditor.utils.role_detector import VALID_ROLES


@click.group()
@click.version_option(version=infra_auditor.__version__, prog_name="infra-auditor")
def main():
    """infra-auditor: OS 튜닝 점검 에이전트

    서버 역할별 OS 설정을 자동으로 점검하고 최적화 권장사항을 제공합니다.

    지원 역할: control, compute, network, storage-ceph, storage-s3
    """
    pass


@main.command()
@click.option(
    "--role",
    type=click.Choice(["auto"] + VALID_ROLES),
    default="auto",
    help="서버 역할 (auto=자동감지)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="리포트 출력 파일 경로 (미지정 시 stdout)",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "summary"]),
    default="json",
    help="출력 형식",
)
@click.option(
    "--indent",
    type=int,
    default=2,
    help="JSON 들여쓰기 (기본: 2)",
)
@click.option(
    "--save/--no-save",
    default=True,
    help="스캔 결과를 히스토리에 저장 (기본: 저장)",
)
@click.option(
    "--show-drift/--no-drift",
    default=True,
    help="이전 스캔 대비 변경 사항 표시 (summary 형식에서)",
)
def scan(role, output, fmt, indent, save, show_drift):
    """시스템 스캔 및 규칙 평가를 실행합니다.

    Examples:

        infra-auditor scan --role auto

        infra-auditor scan --role compute -o report.json

        infra-auditor scan --role control --format summary
    """
    report = Report(role=role if role != "auto" else None)

    if fmt == "json":
        data = report.generate()
        drift_data = None
        if save:
            detector = DriftDetector()
            hostname = data.get("server_info", {}).get("hostname", "unknown")
            prev = detector.get_previous(hostname)
            if prev and show_drift:
                drift_data = detector.compare(data, prev)
                data["drift"] = drift_data
            detector.save_scan(data)

        json_str = json.dumps(data, indent=indent, ensure_ascii=False)
        if output:
            with open(output, "w") as f:
                f.write(json_str)
            click.echo(f"리포트 저장: {output}")
        else:
            click.echo(json_str)
    elif fmt == "summary":
        data = report.generate()
        drift_data = None
        if save:
            detector = DriftDetector()
            hostname = data.get("server_info", {}).get("hostname", "unknown")
            prev = detector.get_previous(hostname)
            if prev and show_drift:
                drift_data = detector.compare(data, prev)
            detector.save_scan(data)

        _print_summary(data, drift_data)
        if output:
            with open(output, "w") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            click.echo(f"\n상세 리포트 저장: {output}")


@main.command()
@click.option(
    "--hostname",
    default=None,
    help="비교할 호스트명 (미지정 시 현재 호스트)",
)
@click.option(
    "--limit",
    default=10,
    help="히스토리 개수 제한",
)
def drift(hostname, limit):
    """이전 스캔과의 drift(변경 사항)를 확인합니다.

    현재 스캔을 실행하고 마지막 저장된 결과와 비교합니다.

    Examples:

        infra-auditor drift

        infra-auditor drift --hostname myserver
    """
    report = Report()
    data = report.generate()

    if hostname is None:
        hostname = data.get("server_info", {}).get("hostname", "unknown")

    detector = DriftDetector()
    prev = detector.get_previous(hostname)

    if prev is None:
        click.echo("이전 스캔 결과가 없습니다. 먼저 scan을 실행하세요.")
        click.echo("현재 스캔 결과를 저장합니다...")
        detector.save_scan(data)
        click.echo("다음 실행 시 drift를 확인할 수 있습니다.")
        return

    drift_result = detector.compare(data, prev)
    _print_drift(drift_result)

    # Save current scan
    detector.save_scan(data)


@main.command()
@click.option(
    "--role",
    type=click.Choice(["auto"] + VALID_ROLES),
    default="auto",
    help="서버 역할 (auto=자동감지)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="스크립트 출력 파일 (미지정 시 stdout)",
)
@click.option(
    "--severity",
    type=click.Choice(["critical", "warning", "info"]),
    multiple=True,
    help="특정 심각도만 포함 (복수 지정 가능)",
)
@click.option(
    "--category",
    multiple=True,
    help="특정 카테고리만 포함 (복수 지정 가능)",
)
def remediate(role, output, severity, category):
    """비준수 항목에 대한 수정 스크립트를 생성합니다.

    Examples:

        infra-auditor remediate --role compute

        infra-auditor remediate --severity critical --severity warning

        infra-auditor remediate -o fix.sh
    """
    report = Report(role=role if role != "auto" else None)
    data = report.generate()

    gen = RemediationGenerator()
    result = gen.generate(
        data,
        categories=list(category) if category else None,
        severities=list(severity) if severity else None,
    )

    if result["total_fixes"] == 0:
        click.echo("✅ 모든 항목이 준수 상태입니다. 수정할 항목이 없습니다.")
        return

    click.echo(f"📝 {result['total_fixes']}개 비준수 항목에 대한 수정 스크립트 생성")

    if result["reboot_required"]:
        click.echo(
            click.style("⚠ 일부 변경사항은 리부트가 필요합니다.", fg="yellow")
        )

    click.echo("-" * 60)
    for item in result["items"]:
        sev_color = {
            "critical": "red",
            "warning": "yellow",
            "info": "blue",
        }.get(item["severity"], "white")
        click.echo(
            f"  [{click.style(item['severity'].upper(), fg=sev_color)}] "
            f"{item['item']}: {item['current_value']} → {item['recommended_value']} "
            f"({item['fix_type']})"
        )
    click.echo("-" * 60)

    if output:
        with open(output, "w") as f:
            f.write(result["script"])
        click.echo(f"\n스크립트 저장: {output}")
        click.echo(f"실행 전 검토: cat {output}")
        click.echo(f"Dry-run: bash {output} --dry-run")
        click.echo(f"적용: sudo bash {output}")
    else:
        click.echo("\n" + result["script"])


def _print_summary(data, drift_data=None):
    """Print a human-readable summary of the report."""
    server = data.get("server_info", {})
    compliance = data.get("compliance", {})
    meta = data.get("metadata", {})
    errors = data.get("errors", [])

    click.echo("=" * 60)
    click.echo("  infra-auditor 스캔 결과 요약")
    click.echo("=" * 60)
    click.echo(f"  호스트: {server.get('hostname', 'unknown')}")
    click.echo(f"  역할:   {server.get('role', 'unknown')}")
    click.echo(f"  OS:     {server.get('os', {}).get('distribution', {}).get('name', 'unknown')}")
    click.echo(f"  스캔 ID: {meta.get('scan_id', '')[:8]}...")
    click.echo(f"  소요시간: {meta.get('scan_duration_seconds', 0):.1f}초")
    click.echo("-" * 60)

    score = compliance.get("overall_score", 0)
    if score >= 80:
        color = "green"
    elif score >= 50:
        color = "yellow"
    else:
        color = "red"

    score_str = click.style(str(score), fg=color, bold=True)
    # Show score delta if drift available
    if drift_data:
        delta = drift_data.get("score_change", {}).get("delta", 0)
        if delta > 0:
            score_str += click.style(f" (+{delta})", fg="green")
        elif delta < 0:
            score_str += click.style(f" ({delta})", fg="red")

    click.echo(f"  전체 점수: {score_str}/100")

    severity = compliance.get("severity_summary", {})
    click.echo(
        f"  위반: "
        f"{click.style(str(severity.get('critical', 0)), fg='red')} critical, "
        f"{click.style(str(severity.get('warning', 0)), fg='yellow')} warning, "
        f"{severity.get('info', 0)} info"
    )

    click.echo("-" * 60)
    click.echo("  카테고리별 점수:")
    for cat, stats in compliance.get("category_scores", {}).items():
        cat_score = stats.get("score", 0)
        bar = "█" * (cat_score // 5) + "░" * (20 - cat_score // 5)
        click.echo(
            f"    {cat:20s} {bar} {cat_score}% "
            f"({stats.get('compliant_items', 0)}/{stats.get('total_items', 0)})"
        )

    # High priority recommendations
    recs = compliance.get("recommendations", {}).get("high_priority", [])
    if recs:
        click.echo("-" * 60)
        click.echo(
            click.style("  ⚠ 우선 조치 필요:", fg="red", bold=True)
        )
        for rec in recs:
            click.echo(f"    • {rec['item']} (영향도: {rec['impact']})")

    # Drift section
    if drift_data and drift_data.get("summary", {}).get("has_drift"):
        click.echo("-" * 60)
        _print_drift_compact(drift_data)

    if errors:
        click.echo("-" * 60)
        click.echo(f"  수집 오류: {len(errors)}건")

    click.echo("=" * 60)


def _print_drift_compact(drift_data):
    """Print compact drift info within summary."""
    summary = drift_data.get("summary", {})
    click.echo(
        click.style("  🔄 Drift 감지:", fg="cyan", bold=True)
    )
    parts = []
    if summary.get("improved", 0):
        parts.append(click.style(f"{summary['improved']} 개선", fg="green"))
    if summary.get("degraded", 0):
        parts.append(click.style(f"{summary['degraded']} 악화", fg="red"))
    if summary.get("changed", 0) - summary.get("improved", 0) - summary.get("degraded", 0) > 0:
        neutral = summary["changed"] - summary.get("improved", 0) - summary.get("degraded", 0)
        parts.append(click.style(f"{neutral} 변경", fg="yellow"))
    click.echo(f"    {', '.join(parts)}")

    for item in drift_data.get("items", [])[:5]:
        dtype = item["drift_type"]
        if dtype == "improved":
            icon = click.style("↑", fg="green")
        elif dtype == "degraded":
            icon = click.style("↓", fg="red")
        elif dtype == "added":
            icon = click.style("+", fg="cyan")
        elif dtype == "removed":
            icon = click.style("-", fg="magenta")
        else:
            icon = click.style("~", fg="yellow")

        click.echo(
            f"    {icon} {item['item']}: "
            f"{item.get('previous_value', '?')} → {item.get('current_value', '?')}"
        )

    remaining = len(drift_data.get("items", [])) - 5
    if remaining > 0:
        click.echo(f"    ... {remaining}개 더 (infra-auditor drift 로 전체 확인)")


def _print_drift(drift_data):
    """Print full drift report."""
    summary = drift_data.get("summary", {})
    score = drift_data.get("score_change", {})

    click.echo("=" * 60)
    click.echo("  infra-auditor Drift Report")
    click.echo("=" * 60)

    click.echo(
        f"  이전 스캔: {drift_data.get('previous_timestamp', '?')}"
    )
    click.echo(
        f"  현재 스캔: {drift_data.get('current_timestamp', '?')}"
    )
    click.echo("-" * 60)

    # Score change
    delta = score.get("delta", 0)
    if delta > 0:
        delta_str = click.style(f"+{delta}", fg="green", bold=True)
    elif delta < 0:
        delta_str = click.style(str(delta), fg="red", bold=True)
    else:
        delta_str = click.style("0", fg="white")

    click.echo(
        f"  점수 변화: {score.get('previous', '?')} → {score.get('current', '?')} "
        f"({delta_str})"
    )
    click.echo("-" * 60)

    if not summary.get("has_drift"):
        click.echo(
            click.style("  ✅ 변경 사항 없음", fg="green", bold=True)
        )
        click.echo("=" * 60)
        return

    click.echo(
        f"  검사 항목: {summary.get('total_items_checked', 0)}개"
    )
    click.echo(
        f"  변경 없음: {summary.get('unchanged', 0)}개"
    )

    if summary.get("improved", 0):
        click.echo(
            f"  개선:     {click.style(str(summary['improved']), fg='green')}개"
        )
    if summary.get("degraded", 0):
        click.echo(
            f"  악화:     {click.style(str(summary['degraded']), fg='red')}개"
        )
    changed_other = summary.get("changed", 0) - summary.get("improved", 0) - summary.get("degraded", 0)
    if changed_other > 0:
        click.echo(
            f"  변경:     {click.style(str(changed_other), fg='yellow')}개"
        )
    if summary.get("added", 0):
        click.echo(f"  추가:     {summary['added']}개")
    if summary.get("removed", 0):
        click.echo(f"  제거:     {summary['removed']}개")

    click.echo("-" * 60)
    click.echo("  상세:")

    for item in drift_data.get("items", []):
        dtype = item["drift_type"]
        if dtype == "improved":
            icon = click.style("  ✅", fg="green")
            direction = click.style("개선", fg="green")
        elif dtype == "degraded":
            icon = click.style("  ❌", fg="red")
            direction = click.style("악화", fg="red")
        elif dtype == "added":
            icon = click.style("  ➕", fg="cyan")
            direction = "추가"
        elif dtype == "removed":
            icon = click.style("  ➖", fg="magenta")
            direction = "제거"
        else:
            icon = click.style("  🔄", fg="yellow")
            direction = click.style("변경", fg="yellow")

        sev = item.get("severity", "info")
        sev_color = {"critical": "red", "warning": "yellow"}.get(sev, "white")

        click.echo(
            f"{icon} [{click.style(sev.upper(), fg=sev_color)}] "
            f"{item['item']} ({direction})"
        )
        if item.get("previous_value") is not None:
            click.echo(f"     이전: {item['previous_value']}")
        if item.get("current_value") is not None:
            click.echo(f"     현재: {item['current_value']}")

    click.echo("=" * 60)


if __name__ == "__main__":
    main()
