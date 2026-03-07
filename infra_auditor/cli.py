"""CLI interface using Click framework."""

import json
import sys

import click

import infra_auditor
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
def scan(role, output, fmt, indent):
    """시스템 스캔 및 규칙 평가를 실행합니다.

    Examples:

        infra-auditor scan --role auto

        infra-auditor scan --role compute -o report.json

        infra-auditor scan --role control --format summary
    """
    report = Report(role=role if role != "auto" else None)

    if fmt == "json":
        json_str = report.to_json(indent=indent)
        if output:
            with open(output, "w") as f:
                f.write(json_str)
            click.echo(f"리포트 저장: {output}")
        else:
            click.echo(json_str)
    elif fmt == "summary":
        data = report.generate()
        _print_summary(data)
        if output:
            with open(output, "w") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            click.echo(f"\n상세 리포트 저장: {output}")


def _print_summary(data):
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
    click.echo(
        f"  전체 점수: {click.style(str(score), fg=color, bold=True)}/100"
    )

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

    if errors:
        click.echo("-" * 60)
        click.echo(f"  수집 오류: {len(errors)}건")

    click.echo("=" * 60)


if __name__ == "__main__":
    main()
