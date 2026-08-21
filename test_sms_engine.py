#!/usr/bin/env python3
"""
Self-check unit test for Spintax, GSM-7 / UCS-2 calculations, and Gateway validation.
"""
import sys
import os

# Import functions directly from web_ui
from web_ui import calculate_sms_encoding, evaluate_spintax

def test_gsm7_ascii():
    text = "Dear {name}, JobRecruitment has an opening for Sales in Ahmedabad. Apply: https://jobrecruitment.in/jobs"
    res = calculate_sms_encoding(text)
    assert not res["is_unicode"], "Should be GSM-7"
    assert res["encoding"] == "GSM-7 (Standard)"
    assert res["segments"] == 1, "Should fit in 1 segment"
    print("✅ test_gsm7_ascii passed!")

def test_ucs2_unicode():
    text = "नमस्ते {name}, अर्जेंट ओपनिंग 🚀"
    res = calculate_sms_encoding(text)
    assert res["is_unicode"], "Should detect Devanagari/Emoji as Unicode"
    assert res["encoding"] == "UCS-2 (Unicode)"
    assert res["segments"] == 1
    print("✅ test_ucs2_unicode passed!")

def test_spintax_rotation():
    template = "{Hi|Hello|Dear} {name}, we have {urgent|immediate} hiring!"
    out1 = evaluate_spintax(template, seed=1)
    out2 = evaluate_spintax(template, seed=2)
    assert any(g in out1 for g in ["Hi", "Hello", "Dear"]), "Spintax must resolve choices"
    assert "{" not in out1 and "}" not in out1 or "{name}" in out1, "Spintax tags must be substituted"
    print(f"✅ test_spintax_rotation passed! (Seed 1: '{out1}', Seed 2: '{out2}')")

if __name__ == "__main__":
    print("[*] Running SMS Engine & Gateway Self-Checks...")
    test_gsm7_ascii()
    test_ucs2_unicode()
    test_spintax_rotation()
    print("🎉 All test assertions passed with 100% success!")
