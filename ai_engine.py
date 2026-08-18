#!/usr/bin/env python3
"""
AI Conversational Engine — Multi-Model Cascading Fallbacks (Groq, Nvidia, Local Pattern Extractor)
Crafts high-CTR, concise, anti-spam SMS copy with variables: {name}, {role}, {company}, {location}
"""

import requests
import json
import re

class AIEngine:
    def __init__(self, groq_key=None, gemini_key=None, nvidia_key=None):
        self.groq_key = groq_key
        self.gemini_key = gemini_key
        self.nvidia_key = nvidia_key

    def generate_sms_template(self, prompt, job_role=None, location=None, company="Job Recruitment"):
        """
        Drafts a high-impact SMS message based on user's plain Hindi/English prompt.
        """
        # Primary: Groq Active Models
        if self.groq_key:
            res = self._call_groq(prompt, job_role, location, company)
            if res:
                return res

        # Secondary: Nvidia NIM API
        if self.nvidia_key:
            res = self._call_nvidia(prompt, job_role, location, company)
            if res:
                return res

        # Smart Heuristic Generator (Extracts links, intent, WhatsApp URLs dynamically)
        return self._smart_rule_fallback(prompt, job_role, location, company)

    def _call_groq(self, prompt, job_role, location, company):
        try:
            # Detect URLs in prompt
            extracted_urls = re.findall(r'https?://[^\s]+', prompt)
            url_text = extracted_urls[0] if extracted_urls else "https://jobrecruitment.in/jobs"
            
            system_instruction = (
                "You are an expert HR SMS copywriter for Indian job seekers. "
                "CRITICAL INSTRUCTIONS: "
                f"1. You MUST include this exact URL in the message: {url_text} "
                "2. Always use {name} for candidate personalization. "
                "3. Keep the entire message under 160 characters. "
                "4. Output ONLY the raw SMS text. No thinking tags, no markdown, no quotes."
            )
            
            headers = {
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json"
            }
            
            # Use active fast models on Groq
            for model_name in ["qwen/qwen3.6-27b", "openai/gpt-oss-20b", "groq/compound-mini"]:
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": f"User Goal: {prompt}\nRole: {job_role}, City: {location}"}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 120
                }
                
                r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=6)
                if r.status_code == 200:
                    raw_content = r.json()["choices"][0]["message"]["content"].strip()
                    # Strip any <think> blocks if returned by deep reasoning models
                    clean_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
                    if '</think>' in raw_content:
                        clean_content = raw_content.split('</think>')[-1].strip()
                    clean_content = clean_content.strip('"\' \n')
                    
                    if clean_content and len(clean_content) > 10 and len(clean_content) < 180:
                        return clean_content
        except Exception as e:
            print(f"[AI Fallback] Groq error: {e}")
        return None

    def _call_nvidia(self, prompt, job_role, location, company):
        try:
            extracted_urls = re.findall(r'https?://[^\s]+', prompt)
            url_text = extracted_urls[0] if extracted_urls else "https://jobrecruitment.in/jobs"

            system_instruction = (
                "You are an expert HR copywriter. Output ONLY the final raw SMS text under 160 characters. "
                f"Always include {{name}} tag and the exact URL: {url_text}. No markdown, no quotes."
            )
            headers = {
                "Authorization": f"Bearer {self.nvidia_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "meta/llama-3.1-70b-instruct",
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 100,
                "temperature": 0.2
            }
            r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload, timeout=6)
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"].strip().strip('"')
                if content:
                    return content
        except Exception as e:
            print(f"[AI Fallback] Nvidia error: {e}")
        return None

    def _smart_rule_fallback(self, prompt, job_role, location, company):
        """
        Zero-latency smart fallback that extracts links & intent if external AI APIs timeout.
        """
        extracted_urls = re.findall(r'https?://[^\s]+', prompt)
        
        if "whatsapp" in prompt.lower() and extracted_urls:
            wa_link = extracted_urls[0]
            return f"Dear {{name}}, join Job Recruitment's official WhatsApp jobs group for instant job alerts & interview calls in {location or 'Ahmedabad'}: {wa_link}"
        
        if extracted_urls:
            link = extracted_urls[0]
            return f"Dear {{name}}, update regarding {job_role or 'Job Opening'} in {location or 'Ahmedabad'}. Check details & join here: {link}"

        return f"Dear {{name}}, Job Recruitment has an urgent opening for {job_role or 'Candidate'} in {location or 'Ahmedabad'}. Apply here: https://jobrecruitment.in/jobs"
