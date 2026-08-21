import pytest
from web_ui import calculate_sms_encoding, evaluate_spintax

class TestSpintaxEngine:
    def test_single_spintax_resolution(self):
        template = "{Hi|Hello|Dear} candidate!"
        result = evaluate_spintax(template, seed=0)
        assert result in ["Hi candidate!", "Hello candidate!", "Dear candidate!"]

    def test_nested_spintax_resolution(self):
        template = "{Urgent|Immediate {hiring|opening}} in Ahmedabad!"
        result = evaluate_spintax(template, seed=1)
        assert any(phrase in result for phrase in ["Urgent", "Immediate hiring", "Immediate opening"])

    def test_empty_template_safe(self):
        assert evaluate_spintax("") == ""
        assert evaluate_spintax(None) == ""

    def test_no_spintax_passthrough(self):
        plain = "Standard SMS without variation."
        assert evaluate_spintax(plain) == plain


class TestGsm7AndUcs2Encoding:
    def test_pure_gsm7_ascii_single_segment(self):
        text = "Hello Omear, your interview is scheduled at JobRecruitment office. Call: 9898011223"
        res = calculate_sms_encoding(text)
        assert res["encoding"] == "GSM-7 (Standard)"
        assert not res["is_unicode"]
        assert res["segments"] == 1
        assert res["chars_left"] == 160 - len(text)

    def test_gsm7_multisegment_concatenation(self):
        # 170 characters of GSM-7 should consume 2 segments (153 chars/segment)
        text = "A" * 170
        res = calculate_sms_encoding(text)
        assert res["encoding"] == "GSM-7 (Standard)"
        assert res["segments"] == 2

    def test_devanagari_hindi_triggers_ucs2(self):
        text = "नमस्ते राहुल, इंटरव्यू के लिए संपर्क करें।"
        res = calculate_sms_encoding(text)
        assert res["encoding"] == "UCS-2 (Unicode)"
        assert res["is_unicode"]
        assert res["segments"] == 1  # Under 70 chars

    def test_emoji_triggers_ucs2_segment_drop(self):
        # Even 1 single emoji drops the segment capacity from 160 to 70 chars
        text = "Urgent hiring for Developer 🚀 Apply now: https://jobrecruitment.in/jobs"
        res = calculate_sms_encoding(text)
        assert res["is_unicode"]
        assert res["encoding"] == "UCS-2 (Unicode)"
        if len(text) > 70:
            assert res["segments"] >= 2
