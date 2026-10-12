"""Tests for the Groq LLM wrapper and the classify-LLM-then-fallback wiring.

Avoids the network: the HTTP call is mocked. Covers the required behavior:
pydantic category validation, one automatic retry, then regex fallback.

Run with:  python3 test_llm.py   (or)   python3 -m unittest test_llm
"""

import os
import unittest
from unittest import mock

import agent
import agent_llm


class TestGroqClientWhitelisted(unittest.TestCase):
    def make_email(self):
        return agent.Email("1", "a@b.co", "Subject", "Body text")

    def test_parse_valid_json(self):
        c = agent_llm.GroqClient(api_key="x")
        p = c._parse('{"category": "bug_report", "rationale": "crashing"}')
        self.assertEqual(p.category, "bug_report")

    def test_parse_invalid_category_raises_groq_error(self):
        c = agent_llm.GroqClient(api_key="x")
        with self.assertRaises(agent_llm.GroqError):
            c._parse('{"category": "dog", "rationale": "nope"}')

    def test_parse_no_json_raises_groq_error(self):
        c = agent_llm.GroqClient(api_key="x")
        with self.assertRaises(agent_llm.GroqError):
            c._parse("I am sorry, I cannot do that.")

    def test_retry_once_then_succeed(self):
        calls = {"n": 0}

        def fake_chat(self, email):
            calls["n"] += 1
            if calls["n"] == 1:
                raise agent_llm.GroqError("timeout")
            return '{"category": "feature_request", "rationale": "want it"}'

        c = agent_llm.GroqClient(api_key="x")
        c._chat = fake_chat.__get__(c)
        cat, _, _ = c.propose_category(self.make_email())
        self.assertEqual(cat, "feature_request")
        self.assertEqual(calls["n"], 2)

    def test_repeated_failure_raises(self):
        c = agent_llm.GroqClient(api_key="x")
        c._chat = lambda email: (_ for _ in ()).throw(agent_llm.GroqError("boom"))
        with self.assertRaises(agent_llm.GroqError):
            c.propose_category(self.make_email())

    def test_prompt_uses_delimiters_and_data_only_notice(self):
        c = agent_llm.GroqClient(api_key="x")
        prompt = c.build_prompt(self.make_email())
        self.assertIn("<email>", prompt)
        self.assertIn("</email>", prompt)
        self.assertIn("UNTRUSTED DATA", prompt)

    def test_request_temperature_zero_and_no_key_is_fallback(self):
        c = agent_llm.GroqClient(api_key="x")
        with mock.patch.object(agent_llm.requests, "post") as post:
            resp = mock.Mock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {"choices": [{"message": {"content": '{"category": "spam"}'}}]}
            post.return_value = resp
            cat, _, _ = c.propose_category(self.make_email())
            self.assertEqual(cat, "spam")
            payload = post.call_args.kwargs["json"]
            self.assertEqual(payload["temperature"], 0)
            self.assertEqual(payload["response_format"], {"type": "json_object"})


class TestAgentOrchestrator(unittest.TestCase):
    def make_email(self, body="I was charged twice this month. Please fix my invoice."):
        return agent.Email("1", "a@b.co", "Duplicate charge", body)

    def test_llm_valid_used(self):
        stub = mock.Mock()
        stub.propose_category.return_value = ("billing", "double charge", '{"category": "billing"}')
        cat, source, _, _, note = agent.classify_email(self.make_email(), use_llm=True, client=stub)
        self.assertEqual((cat, source), ("billing", "llm"))
        self.assertEqual(note, "")

    def test_llm_invalid_category_falls_back(self):
        stub = mock.Mock()
        stub.propose_category.return_value = ("dog", "?", "{}")
        cat, source, _, _, _ = agent.classify_email(self.make_email(), use_llm=True, client=stub)
        self.assertEqual(source, "fallback")
        self.assertEqual(cat, "billing")  # regex verdict

    def test_llm_spam_rejected_when_regex_disagrees(self):
        # A real customer email must not be silently dropped because the model
        # guessed "spam"; the regex spam detector has to agree.
        stub = mock.Mock()
        stub.propose_category.return_value = ("spam", "looks spammy", '{"category": "spam"}')
        cat, source, _, _, note = agent.classify_email(self.make_email(), use_llm=True, client=stub)
        self.assertNotEqual(cat, "spam")
        self.assertEqual((source, note), ("fallback", "llm_spam_rejected"))

    def test_llm_spam_accepted_when_regex_agrees(self):
        spammy = agent.Email(
            "2", "a@b.co", "Win",
            "Congratulations you won a free iPhone. Click here to claim your prize. Limited time offer.",
        )
        stub = mock.Mock()
        stub.propose_category.return_value = ("spam", "spam", '{"category": "spam"}')
        cat, source, _, _, note = agent.classify_email(spammy, use_llm=True, client=stub)
        self.assertEqual((cat, source), ("spam", "llm"))
        self.assertEqual(note, "")

    def test_llm_error_falls_back_batch_never_crashes(self):
        stub = mock.Mock()
        stub.propose_category.side_effect = agent_llm.GroqError("down")
        t, meta = agent.triage_email(self.make_email(), use_llm=True, client=stub)
        self.assertEqual(meta["source"], "fallback")
        self.assertEqual(t.category, "billing")
        agent.validate_triage(t)

    def test_no_llm_uses_regex(self):
        cat, source, _, _, _ = agent.classify_email(self.make_email(), use_llm=False, client=None)
        self.assertEqual(source, "fallback")
        self.assertEqual(cat, "billing")

    def test_is_configured_reflects_api_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(agent_llm.GroqClient(api_key="").is_configured())
            self.assertTrue(agent_llm.GroqClient(api_key="secret").is_configured())


if __name__ == "__main__":
    unittest.main()