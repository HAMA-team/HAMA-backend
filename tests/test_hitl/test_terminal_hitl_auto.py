"""
자동 실행 HITL 테스트 (데모용)

터미널 입력 없이 자동으로 시나리오를 실행하여 HITL 플로우를 검증합니다.

사용법:
    PYTHONPATH=. python tests/test_terminal_hitl_auto.py
"""
import asyncio
import uuid
from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich import box

from src.api.routes.chat import ChatRequest, ChatResponse, ApprovalRequest, ApprovalResponse, chat, approve_action

console = Console()


class AutomatedHITLTester:
    """자동 HITL 테스터 (데모용)"""

    def __init__(self, automation_level: int = 2):
        self.automation_level = automation_level
        self.conversation_id: Optional[str] = None

    def print_header(self):
        """헤더 출력"""
        console.print()
        console.print(Panel.fit(
            "[bold cyan]HAMA HITL 자동 테스트 (데모)[/bold cyan]\n"
            f"자동화 레벨: [yellow]{self.automation_level}[/yellow] "
            f"({'Pilot' if self.automation_level == 1 else 'Copilot' if self.automation_level == 2 else 'Advisor'})",
            border_style="cyan"
        ))
        console.print()

    def print_step(self, step_num: int, title: str):
        """단계 출력"""
        console.print()
        console.print(f"[bold magenta]━━━ Step {step_num}: {title} ━━━[/bold magenta]")
        console.print()

    async def test_scenario(self, scenario_name: str, message: str, auto_approve: bool = True):
        """시나리오 테스트"""
        console.print()
        console.print(f"[bold yellow]📋 시나리오: {scenario_name}[/bold yellow]")
        console.print()

        # Step 1: 사용자 요청
        self.print_step(1, "사용자 요청")
        console.print(f"[green]>>> {message}[/green]")
        console.print()

        # Step 2: Chat API 호출
        self.print_step(2, "Master Agent 실행")

        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())

        request = ChatRequest(
            message=message,
            conversation_id=self.conversation_id,
            automation_level=self.automation_level
        )

        console.print(f"[dim]Conversation ID: {self.conversation_id}[/dim]")
        console.print()

        with console.status("[bold yellow]AI가 분석 중입니다...[/bold yellow]", spinner="dots"):
            response = await chat(request)

        # 응답 출력
        console.print()
        console.print(Panel(
            Markdown(response.message),
            title="[bold blue]AI 응답[/bold blue]",
            border_style="blue"
        ))
        console.print()

        # 메타데이터 출력
        if response.metadata:
            table = Table(title="실행 정보", box=box.ROUNDED)
            table.add_column("항목", style="cyan")
            table.add_column("값", style="green")

            if "intent" in response.metadata:
                table.add_row("의도", response.metadata["intent"])
            if "agents_called" in response.metadata:
                agents = ", ".join(response.metadata["agents_called"])
                table.add_row("실행된 에이전트", agents)
            if "automation_level" in response.metadata:
                table.add_row("자동화 레벨", str(response.metadata["automation_level"]))

            console.print(table)
            console.print()

        # Step 3: 승인 처리 (필요한 경우)
        if response.requires_approval and response.approval_request:
            self.print_step(3, "사용자 승인 요청")

            # 승인 요청 정보 출력
            console.print(Panel(
                f"[yellow]⚠️  승인이 필요합니다[/yellow]\n\n"
                f"유형: {response.approval_request.get('type', 'N/A')}\n"
                f"메시지: {response.approval_request.get('message', 'N/A')}",
                title="[bold red]Approval Required[/bold red]",
                border_style="red"
            ))
            console.print()

            # 자동 승인/거부
            decision = "approved" if auto_approve else "rejected"
            console.print(f"[bold cyan]자동 결정: {decision.upper()}[/bold cyan]")
            console.print()

            approval = ApprovalRequest(
                thread_id=self.conversation_id,
                decision=decision,
                automation_level=self.automation_level,
                user_notes=f"자동 테스트: {decision}"
            )

            with console.status(f"[bold yellow]{decision} 처리 중...[/bold yellow]", spinner="dots"):
                approval_response = await approve_action(approval)

            # Step 4: 최종 결과
            self.print_step(4, "최종 결과")

            status_color = {
                "approved": "green",
                "rejected": "red",
                "modified": "yellow"
            }.get(approval_response.status, "white")

            console.print(Panel(
                f"[{status_color}]상태: {approval_response.status.upper()}[/{status_color}]\n\n"
                f"{approval_response.message}",
                title="[bold]처리 완료[/bold]",
                border_style=status_color
            ))
            console.print()

            if approval_response.result:
                console.print("[bold]결과 상세:[/bold]")
                for key, value in approval_response.result.items():
                    console.print(f"  • {key}: {value}")
                console.print()

        else:
            console.print("[green]✅ 승인 없이 완료되었습니다.[/green]")
            console.print()

        console.print("[dim]" + "─" * 80 + "[/dim]")
        console.print()


async def main():
    """메인 실행 함수"""
    console.print()
    console.print("[bold cyan]HAMA HITL 자동 테스트 시작[/bold cyan]")
    console.print()

    # 자동화 레벨 2 (Copilot)로 테스트
    tester = AutomatedHITLTester(automation_level=2)
    tester.print_header()

    # 시나리오 1: 종목 분석 (승인 불필요)
    await tester.test_scenario(
        scenario_name="종목 분석",
        message="삼성전자 분석해줘",
        auto_approve=True
    )

    await asyncio.sleep(1)

    # 시나리오 2: 매매 요청 (승인 필요) - 승인
    await tester.test_scenario(
        scenario_name="매매 요청 (승인)",
        message="삼성전자 100주 매수해줘",
        auto_approve=True
    )

    await asyncio.sleep(1)

    # 시나리오 3: 새 대화 시작 - 매매 요청 거부
    tester.conversation_id = None  # 새 대화
    await tester.test_scenario(
        scenario_name="매매 요청 (거부)",
        message="SK하이닉스 50주 매도해줘",
        auto_approve=False
    )

    # 완료
    console.print()
    console.print(Panel.fit(
        "[bold green]✅ 모든 시나리오 테스트 완료[/bold green]",
        border_style="green"
    ))
    console.print()


if __name__ == "__main__":
    """독립 실행"""
    asyncio.run(main())
