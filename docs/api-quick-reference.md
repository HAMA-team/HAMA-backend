# API Quick Reference

**HAMA 백엔드 API 빠른 참조 가이드**

---

## 🚀 **Base URL**

```
http://localhost:8000/api/v1
```

---

## 📡 **엔드포인트**

### **1. POST `/chat/`** - 대화 처리

```bash
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "삼성전자 10주 매수해줘",
    "automation_level": 2
  }'
```

**Response:**
```json
{
  "message": "🔔 사용자 승인이 필요합니다.",
  "conversation_id": "abc123",
  "requires_approval": true,
  "approval_request": {
    "thread_id": "abc123",  // ⭐ 승인 시 사용
    "interrupt_data": { ... }
  }
}
```

---

### **2. POST `/chat/approve`** - 승인/거부

```bash
curl -X POST http://localhost:8000/api/v1/chat/approve \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "abc123",
    "decision": "approved",
    "automation_level": 2
  }'
```

**Response:**
```json
{
  "status": "approved",
  "message": "승인 완료 - 매매가 실행되었습니다.",
  "result": {
    "order_id": "ORDER_a1b2c3d4",
    "status": "executed",
    "total": 890000
  }
}
```

---

## 🎯 **핵심 플로우**

```
1. 사용자 메시지 전송
   POST /chat/ { message: "삼성전자 매수" }

2. ⚠️ HITL 발생 (requires_approval: true)
   → thread_id 저장

3. 사용자 승인/거부
   POST /chat/approve { thread_id, decision: "approved" }

4. ✅ 거래 실행 완료
```

---

## 📚 **자세한 문서**

- **프론트엔드 통합 가이드**: `docs/frontend-integration-guide.md`
- **OpenAPI 스펙**: `http://localhost:8000/docs`
- **테스트 코드**: `tests/test_api_chat.py`

---

**버전**: 1.0
**최종 업데이트**: 2025-10-06
