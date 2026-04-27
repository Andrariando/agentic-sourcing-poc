from types import SimpleNamespace

from backend.services.conversation_context import ConversationContextManager


class _FakeCaseService:
    def __init__(self, state):
        self._state = state

    def get_case_state(self, case_id: str):
        return self._state


def _msg(i: int, role: str, text: str):
    return SimpleNamespace(
        message_id=f"m{i}",
        role=role,
        content=text,
        intent_classified=None,
        created_at=f"2026-04-27T00:00:{i:02d}",
    )


def test_build_structured_case_memory_includes_stage_intake_values():
    state = {
        "dtp_stage": "DTP-03",
        "human_decision": {
            "DTP-02": {
                "_stage_intake": {
                    "values": {
                        "request_title": "IT Service Desk Renewal",
                        "business_unit": "IT Infrastructure",
                    }
                }
            }
        },
        "working_documents": {
            "rfx": {"plain_text": "Section 1\nSection 2"},
            "contract": {"plain_text": ""},
        },
    }
    mgr = ConversationContextManager(_FakeCaseService(state))
    mem = mgr._build_structured_case_memory("CASE-1")
    assert mem is not None
    assert "DTP-02 intake" in mem
    assert "request_title" in mem
    assert "Working rfx draft exists" in mem


def test_get_relevant_context_uses_summary_and_structured_memory(monkeypatch):
    mgr = ConversationContextManager(_FakeCaseService({"dtp_stage": "DTP-01", "human_decision": {}}))
    mgr.recent_messages_count = 2
    mgr.summarize_threshold = 1
    mgr.enable_summarization = True
    mgr.max_context_tokens = 5000

    messages = [
        _msg(1, "user", "Need to include legal signoff in contracting."),
        _msg(2, "assistant", "Captured. I will track legal signoff."),
        _msg(3, "user", "Also prioritize timeline and KPI governance."),
        _msg(4, "assistant", "Noted."),
    ]

    monkeypatch.setattr(mgr, "get_recent_messages", lambda case_id, limit=100: messages)
    monkeypatch.setattr(mgr, "_build_structured_case_memory", lambda case_id: "Structured memory snapshot (human-confirmed inputs):")
    monkeypatch.setattr(mgr, "_get_cached_summary", lambda case_id, covered_last_message_id: None)
    monkeypatch.setattr(mgr, "summarize_conversation", lambda case_id, message_ids=None: "Decisions: legal signoff required.")
    monkeypatch.setattr(mgr, "_save_summary_cache", lambda *args, **kwargs: None)

    ctx = mgr.get_relevant_context("CASE-2", "what did we decide?", max_tokens=5000)
    assert len(ctx) >= 3
    assert ctx[0]["role"] == "system"
    assert "Structured memory snapshot" in ctx[0]["content"]
    assert ctx[1]["role"] == "system"
    assert "Previous conversation summary" in ctx[1]["content"]
