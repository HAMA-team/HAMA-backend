"""
터미널 대화형 HITL (Human-in-the-Loop) 전체 프로세스 테스트

실제 API 라우터를 호출하고 터미널에서 대화형으로 승인/거부 처리를 테스트합니다.

테스트 플로우:
1. 사용자 요구사항 입력 (터미널)
2. Master Agent가 의도 분석 및 에이전트 라우팅
3. HITL 승인 필요 시 터미널에서 승인/거부 입력
4. 최종 결과 출력

사용법:
    PYTHONPATH=. python tests/test_terminal_hitl.py
"""
import asyncio
import uuid
import sys
from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

# FastAPI 앱 및 라우터 임포트
from src.api.routes.chat import ChatRequest, ChatResponse, ApprovalRequest, ApprovalResponse, chat, approve_action
from src.config.settings import settings

console = Console()


class TerminalHITLTester:
    """터미널 대화형 HITL 테스터"""

    def __init__(self, automation_level: int = 2):
        """
        Args:
            automation_level: 자동화 레벨 (1=Pilot, 2=Copilot, 3=Advisor)
        """
        self.automation_level = automation_level
        self.conversation_id: Optional[str] = None

    def print_header(self):
        """헤더 출력"""
        console.print()
        console.print(Panel.fit(
            "[bold cyan]HAMA HITL 전체 프로세스 테스트[/bold cyan]\n"
            f"자동화 레벨: [yellow]{self.automation_level}[/yellow] "
            f"({'Pilot' if self.automation_level == 1 else 'Copilot' if self.automation_level == 2 else 'Advisor'})\n"
            f"환경: [green]{settings.ENV or 'development'}[/green]",
            border_style="cyan"
        ))
        console.print()

    def print_step(self, step_num: int, title: str):
        """단계 출력"""
        console.print()
        console.print(f"[bold magenta]━━━ Step {step_num}: {title} ━━━[/bold magenta]")
        console.print()

    async def get_user_input(self) -> str:
        """사용자 요구사항 입력"""
        self.print_step(1, "사용자 요구사항 입력")

        console.print("[dim]예시:[/dim]")
        console.print("  - 삼성전자 분석해줘")
        console.print("  - 삼성전자 100주 매수해줘")
        console.print("  - 내 포트폴리오 리밸런싱해줘")
        console.print("  - 반도체 관련 종목 추천해줘")
        console.print()

        message = Prompt.ask("[bold green]>>> 요청사항을 입력하세요[/bold green]")
        return message

    async def call_chat_api(self, message: str) -> ChatResponse:
        """Chat API 호출"""
        self.print_step(2, "Master Agent 실행")

        # conversation_id가 없으면 새로 생성
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())

        request = ChatRequest(
            message=message,
            conversation_id=self.conversation_id,
            automation_level=self.automation_level
        )

        console.print(f"[dim]Conversation ID: {self.conversation_id}[/dim]")
        console.print(f"[dim]메시지: {message}[/dim]")
        console.print()

        with console.status("[bold yellow]AI가 분석 중입니다...[/bold yellow]", spinner="dots"):
            response = await chat(request)

        return response

    def display_response(self, response: ChatResponse):
        """응답 결과 출력"""
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

    async def handle_approval(self, approval_request: Dict[str, Any]) -> Optional[ApprovalResponse]:
        """승인 처리"""
        self.print_step(3, "사용자 승인 요청")

        # 승인 요청 정보 출력
        console.print(Panel(
            f"[yellow]⚠️  승인이 필요합니다[/yellow]\n\n"
            f"유형: {approval_request.get('type', 'N/A')}\n"
            f"메시지: {approval_request.get('message', 'N/A')}",
            title="[bold red]Approval Required[/bold red]",
            border_style="red"
        ))
        console.print()

        # interrupt_data 출력
        if "interrupt_data" in approval_request:
            interrupt_data = approval_request["interrupt_data"]
            if isinstance(interrupt_data, dict):
                console.print("[bold]승인 대상 상세 정보:[/bold]")
                for key, value in interrupt_data.items():
                    console.print(f"  • {key}: {value}")
                console.print()

        # 사용자 결정 입력
        console.print("[bold cyan]결정을 선택하세요:[/bold cyan]")
        console.print("  1. [green]승인 (approved)[/green] - 제안대로 실행")
        console.print("  2. [red]거부 (rejected)[/red] - 실행 취소")
        console.print("  3. [yellow]수정 (modified)[/yellow] - 수정 후 실행")
        console.print()

        choice = Prompt.ask(
            "선택",
            choices=["1", "2", "3"],
            default="1"
        )

        decision_map = {
            "1": "approved",
            "2": "rejected",
            "3": "modified"
        }
        decision = decision_map[choice]

        # 메모 입력
        user_notes = None
        if Confirm.ask("메모를 추가하시겠습니까?", default=False):
            user_notes = Prompt.ask("[dim]메모[/dim]")

        # 수정사항 입력 (modified인 경우)
        modifications = None
        if decision == "modified":
            console.print()
            console.print("[yellow]수정 내용을 입력하세요 (JSON 형식)[/yellow]")
            console.print("[dim]예시: {\"quantity\": 50, \"price\": 60000}[/dim]")
            modifications_str = Prompt.ask("수정사항")
            try:
                import json
                modifications = json.loads(modifications_str)
            except json.JSONDecodeError:
                console.print("[red]JSON 형식 오류. 빈 수정사항으로 진행합니다.[/red]")
                modifications = {}

        # Approval API 호출
        approval = ApprovalRequest(
            thread_id=self.conversation_id,
            decision=decision,
            automation_level=self.automation_level,
            modifications=modifications,
            user_notes=user_notes
        )

        console.print()
        with console.status(f"[bold yellow]{decision} 처리 중...[/bold yellow]", spinner="dots"):
            approval_response = await approve_action(approval)

        return approval_response

    def display_approval_result(self, response: ApprovalResponse):
        """승인 결과 출력"""
        self.print_step(4, "최종 결과")

        status_color = {
            "approved": "green",
            "rejected": "red",
            "modified": "yellow"
        }.get(response.status, "white")

        console.print(Panel(
            f"[{status_color}]상태: {response.status.upper()}[/{status_color}]\n\n"
            f"{response.message}",
            title="[bold]처리 완료[/bold]",
            border_style=status_color
        ))
        console.print()

        # 결과 상세 정보
        if response.result:
            console.print("[bold]결과 상세:[/bold]")
            for key, value in response.result.items():
                console.print(f"  • {key}: {value}")
            console.print()

    async def run_test(self):
        """전체 테스트 실행"""
        self.print_header()

        try:
            # Step 1: 사용자 입력
            message = await self.get_user_input()

            # Step 2: Chat API 호출
            chat_response = await self.call_chat_api(message)

            # 응답 출력
            self.display_response(chat_response)

            # Step 3: 승인 처리 (필요한 경우)
            if chat_response.requires_approval and chat_response.approval_request:
                approval_response = await self.handle_approval(chat_response.approval_request)

                if approval_response:
                    self.display_approval_result(approval_response)
            else:
                console.print("[green]✅ 승인 없이 완료되었습니다.[/green]")
                console.print()

            # 계속 진행 여부
            if Confirm.ask("\n다른 요청을 테스트하시겠습니까?", default=True):
                await self.run_test()
            else:
                console.print()
                console.print(Panel.fit(
                    "[bold green]테스트 종료[/bold green]\n"
                    f"Conversation ID: {self.conversation_id}",
                    border_style="green"
                ))
                console.print()

        except KeyboardInterrupt:
            console.print()
            console.print("[yellow]사용자가 테스트를 중단했습니다.[/yellow]")
            sys.exit(0)
        except Exception as e:
            console.print()
            console.print(f"[bold red]❌ 오류 발생:[/bold red] {str(e)}")
            import traceback
            console.print()
            console.print("[dim]" + traceback.format_exc() + "[/dim]")


async def main():
    """메인 실행 함수"""
    console.print()
    console.print("[bold cyan]HAMA HITL 터미널 테스트 시작[/bold cyan]")
    console.print()

    # 자동화 레벨 선택
    console.print("[bold]자동화 레벨을 선택하세요:[/bold]")
    console.print("  1. [yellow]Pilot[/yellow] - AI가 거의 모든 것을 처리 (월 1회 확인)")
    console.print("  2. [green]Copilot[/green] - AI가 제안, 큰 결정만 승인 (기본값)")
    console.print("  3. [blue]Advisor[/blue] - AI는 정보만 제공, 사용자가 결정")
    console.print()

    level_choice = Prompt.ask(
        "선택",
        choices=["1", "2", "3"],
        default="2"
    )
    automation_level = int(level_choice)

    # 테스터 실행
    tester = TerminalHITLTester(automation_level=automation_level)
    await tester.run_test()


if __name__ == "__main__":
    """독립 실행"""
    asyncio.run(main())
