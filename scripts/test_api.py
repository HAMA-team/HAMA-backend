#!/usr/bin/env python3
"""
API 테스트 스크립트

서버가 실행 중이어야 합니다:
python -m src.main
"""
import requests
import json

BASE_URL = "http://localhost:8000/v1"


def test_health():
    """Health check 테스트"""
    print("=" * 60)
    print("1. Health Check 테스트")
    print("=" * 60)

    response = requests.get("http://localhost:8000/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def test_chat_stock_analysis():
    """종목 분석 테스트"""
    print("=" * 60)
    print("2. 종목 분석 테스트 (삼성전자)")
    print("=" * 60)

    payload = {
        "message": "삼성전자 분석해줘",
        "automation_level": 2
    }

    response = requests.post(f"{BASE_URL}/chat/", json=payload)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"\nMessage:\n{data['message']}\n")
        print(f"Conversation ID: {data['conversation_id']}")
        print(f"Requires Approval: {data['requires_approval']}")
        print(f"\nMetadata:")
        print(json.dumps(data['metadata'], indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")
    print()


def test_chat_trade_execution():
    """매매 실행 테스트 (HITL 트리거)"""
    print("=" * 60)
    print("3. 매매 실행 테스트 (HITL 트리거)")
    print("=" * 60)

    payload = {
        "message": "삼성전자 1000만원 매수해줘",
        "automation_level": 2
    }

    response = requests.post(f"{BASE_URL}/chat/", json=payload)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"\nMessage:\n{data['message']}\n")
        print(f"Requires Approval: {data['requires_approval']}")

        if data['approval_request']:
            print(f"\nApproval Request:")
            print(json.dumps(data['approval_request'], indent=2, ensure_ascii=False))

        print(f"\nMetadata:")
        print(json.dumps(data['metadata'], indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")
    print()


def test_chat_general_question():
    """일반 질문 테스트"""
    print("=" * 60)
    print("4. 일반 질문 테스트")
    print("=" * 60)

    payload = {
        "message": "PER이 뭐야?",
        "automation_level": 2
    }

    response = requests.post(f"{BASE_URL}/chat/", json=payload)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"\nMessage:\n{data['message']}\n")
        print(f"Metadata:")
        print(json.dumps(data['metadata'], indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")
    print()


def test_stocks_search():
    """종목 검색 테스트"""
    print("=" * 60)
    print("5. 종목 검색 테스트")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/stocks/search?q=삼성")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")
    print()


def main():
    """모든 테스트 실행"""
    print("\n" + "=" * 60)
    print("HAMA Backend API 테스트")
    print("=" * 60 + "\n")

    try:
        test_health()
        test_chat_stock_analysis()
        test_chat_trade_execution()
        test_chat_general_question()
        test_stocks_search()

        print("=" * 60)
        print("✅ 모든 테스트 완료!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("❌ 서버가 실행 중이지 않습니다.")
        print("다음 명령어로 서버를 시작하세요:")
        print("  python -m src.main")
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")


if __name__ == "__main__":
    main()
