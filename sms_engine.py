#!/usr/bin/env python3
"""
================================================================================
     🚀 JobRecruitment — Unified AI SMS Automation Engine (CLI)
================================================================================
Controls:
  - Select from Manage Jobs or Global Search
  - AI Conversational Prompting (Groq / Gemini)
  - Quota Safety (180 limit + Midnight reset)
  - Android SIM Radio Dispatch (5s delay)
"""

import os
import sys
import time
from dotenv import load_dotenv

# Try importing colorama for clean terminal colors
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    GREEN = Fore.GREEN
    CYAN = Fore.CYAN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    MAGENTA = Fore.MAGENTA
    BOLD = Style.BRIGHT
    RESET = Style.RESET_ALL
except ImportError:
    GREEN = CYAN = YELLOW = RED = MAGENTA = BOLD = RESET = ""

from candidate_client import CandidateClient
from ai_engine import AIEngine
from sms_gateway import SMSGateway
from quota_tracker import QuotaTracker

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(quota_tracker):
    clear_screen()
    sent = quota_tracker.state.get("sent_today", 0)
    limit = quota_tracker.limit
    rem = max(0, limit - sent)
    
    print(f"{CYAN}{BOLD}{'='*72}")
    print(f"{CYAN}{BOLD}  🤖 JobRecruitment — AI SMS Outreach Engine [Live SIM Dispatch]")
    print(f"{CYAN}{BOLD}{'='*72}{RESET}")
    print(f"📊 {BOLD}Today's Quota:{RESET} {GREEN}{sent}/{limit} sent{RESET} ({YELLOW}{rem} remaining{RESET}) | {BOLD}Reset:{RESET} Midnight 00:00:00")
    print(f"{CYAN}{'-'*72}{RESET}\n")

def main():
    # Load Environment
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(env_path)

    worker_url = os.getenv("WORKER_API_URL", "https://jobrecruitment.in/backend/api/worker-api.php")
    worker_key = os.getenv("WORKER_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    sms_mode = os.getenv("SMS_MODE", "adb")
    gateway_url = os.getenv("ANDROID_GATEWAY_URL", "http://192.168.1.100:8080/send")
    daily_limit = int(os.getenv("DAILY_SMS_LIMIT", "180"))
    dispatch_delay = int(os.getenv("DISPATCH_DELAY_SECONDS", "5"))

    client = CandidateClient(worker_url, worker_key)
    ai = AIEngine(groq_key, gemini_key)
    gateway = SMSGateway(sms_mode, gateway_url)
    quota = QuotaTracker(daily_limit)

    while True:
        print_header(quota)
        print(f"{BOLD}🎯 Select Audience Source:{RESET}")
        print(f"  [{GREEN}1{RESET}] 📋 {BOLD}Select from Manage Jobs Tab{RESET} (View live jobs & pick applicants)")
        print(f"  [{GREEN}2{RESET}] 🔍 {BOLD}Global Candidate Search{RESET} (Filter by Role, City, Status)")
        print(f"  [{GREEN}3{RESET}] ⚡ {BOLD}Send Single Test SMS{RESET} (Direct test to your mobile number)")
        print(f"  [{GREEN}4{RESET}] 🔄 {BOLD}Check Phone Connection & Quota Status{RESET}")
        print(f"  [{RED}0{RESET}] ❌ Exit")
        
        choice = input(f"\n{BOLD}Your Choice [0-4]: {RESET}").strip()

        if choice == '0':
            print(f"\n{GREEN}Goodbye!{RESET}")
            sys.exit(0)

        elif choice == '4':
            print_header(quota)
            print(f"{BOLD}🔍 Checking Hardware Radio Connection...{RESET}")
            ok, msg = gateway.check_phone_connection()
            status_color = GREEN if ok else RED
            print(f"Hardware Status: {status_color}{msg}{RESET}")
            print(f"\n{BOLD}Quota Details:{RESET}")
            print(f"  Sent Today: {quota.state.get('sent_today', 0)} / {quota.limit}")
            print(f"  Last Reset: {quota.state.get('last_reset_at', 'N/A')}")
            input(f"\n{YELLOW}Press Enter to return to menu...{RESET}")
            continue

        elif choice == '3':
            # Single Test SMS
            print_header(quota)
            phone = input(f"{BOLD}Enter 10-digit Indian Mobile Number: {RESET}").strip()
            msg = input(f"{BOLD}Enter Test Message Body: {RESET}").strip()
            
            can_send, rem, q_msg = quota.check_quota(1)
            if not can_send:
                print(f"\n{RED}❌ {q_msg}{RESET}")
                input(f"\n{YELLOW}Press Enter to return...{RESET}")
                continue

            print(f"\n{CYAN}Dispatching test SMS via Android SIM ({sms_mode.upper()})...{RESET}")
            ok, resp = gateway.send_sms(phone, msg)
            if ok:
                quota.record_sent(1)
                print(f"{GREEN}✅ SUCCESS! SMS Sent to +91-{phone}. ({resp}){RESET}")
            else:
                print(f"{RED}❌ FAILED: {resp}{RESET}")
            input(f"\n{YELLOW}Press Enter to continue...{RESET}")
            continue

        selected_candidates = []
        job_context = {"role": "Candidate", "location": "Ahmedabad", "company": "Job Recruitment"}

        if choice == '1':
            # Manage Jobs Tab
            print(f"\n{CYAN}Fetching live jobs from 'Manage Jobs' tab...{RESET}")
            jobs = client.fetch_admin_jobs(status="")
            if not jobs:
                print(f"{RED}No jobs found or failed to connect to live API.{RESET}")
                input(f"{YELLOW}Press Enter to return...{RESET}")
                continue

            print(f"\n{BOLD}Available Job Postings:{RESET}")
            for idx, j in enumerate(jobs[:25], 1):
                app_count = j.get('total_applicants', 0)
                print(f"  [{GREEN}{idx:2d}{RESET}] {BOLD}{j.get('jobRole')}{RESET} @ {j.get('companyName')} ({j.get('location')}) — {YELLOW}{app_count} applicants{RESET} [{j.get('status')}]")

            job_idx = input(f"\n{BOLD}Select Job Number [1-{len(jobs[:25])}]: {RESET}").strip()
            try:
                sel_job = jobs[int(job_idx) - 1]
                job_id = sel_job.get("id")
                job_context = {
                    "role": sel_job.get("jobRole"),
                    "location": sel_job.get("location"),
                    "company": sel_job.get("companyName")
                }
                print(f"\n{CYAN}Fetching applicants for '{sel_job.get('jobRole')}'...{RESET}")
                cands, _ = client.fetch_job_applicants(job_id)
                selected_candidates = cands
            except (ValueError, IndexError):
                print(f"{RED}Invalid selection.{RESET}")
                input(f"{YELLOW}Press Enter to return...{RESET}")
                continue

        elif choice == '2':
            # Global Search
            print_header(quota)
            role_query = input(f"{BOLD}Filter by Role (e.g. Accountant, HR, Developer - blank for all): {RESET}").strip()
            city_query = input(f"{BOLD}Filter by City (e.g. Ahmedabad, Gandhinagar - blank for all): {RESET}").strip()
            limit_str = input(f"{BOLD}Max recipients to fetch (e.g. 25): {RESET}").strip() or "25"
            
            print(f"\n{CYAN}Searching live candidate database...{RESET}")
            cands, total = client.fetch_global_candidates(role=role_query, city=city_query, limit=int(limit_str))
            selected_candidates = cands
            job_context["role"] = role_query or "Candidate"
            job_context["location"] = city_query or "Ahmedabad"

        if not selected_candidates:
            print(f"\n{RED}❌ No candidates found matching your criteria.{RESET}")
            input(f"\n{YELLOW}Press Enter to return...{RESET}")
            continue

        print(f"\n{GREEN}✅ Found {len(selected_candidates)} candidates with active phone numbers.{RESET}")

        # AI Message Crafting
        print(f"\n{MAGENTA}{BOLD}{'='*72}")
        print(f"🤖 AI SMS Template Crafting")
        print(f"{MAGENTA}{BOLD}{'='*72}{RESET}")
        print(f"Describe what you want to send in Hindi/English (or press Enter for auto-template):")
        ai_prompt = input(f"{BOLD}You: {RESET}").strip()
        if not ai_prompt:
            ai_prompt = f"Urgent hiring for {job_context['role']} in {job_context['location']}. Salary competitive. Direct interview."

        print(f"\n{CYAN}AI is drafting high-CTR SMS with personalization variables...{RESET}")
        sms_template = ai.generate_sms_template(
            ai_prompt, 
            job_role=job_context.get("role"), 
            location=job_context.get("location"), 
            company=job_context.get("company")
        )

        while True:
            print(f"\n{YELLOW}----------------------------------------------------------------------")
            print(f"{BOLD}Drafted SMS Template:{RESET}")
            print(f"{GREEN}{sms_template}{RESET}")
            print(f"{YELLOW}----------------------------------------------------------------------{RESET}")
            print(f"Length: {len(sms_template)} chars (1 SMS credit)")
            
            cand_sample = selected_candidates[0]
            cand_name = cand_sample.get("name") or "Candidate"
            sample_preview = sms_template.replace("{name}", cand_name).replace("{role}", job_context.get("role", "")).replace("{location}", job_context.get("location", ""))
            print(f"\n{BOLD}Live Sample for {cand_name} ({cand_sample.get('phone')}):{RESET}")
            print(f"\"{sample_preview}\"")

            print(f"\nOptions: [{GREEN}1{RESET}] Use Template & Proceed | [{YELLOW}2{RESET}] Re-prompt AI | [{CYAN}3{RESET}] Edit Text Manually")
            t_choice = input("Your Choice [1-3]: ").strip()
            
            if t_choice == '1':
                break
            elif t_choice == '2':
                new_prompt = input("Enter new AI instruction: ").strip()
                sms_template = ai.generate_sms_template(new_prompt, job_context.get("role"), job_context.get("location"))
            elif t_choice == '3':
                sms_template = input("Enter exact text: ").strip()
                break

        # Quota Validation
        count_to_send = len(selected_candidates)
        can_send, remaining, q_msg = quota.check_quota(count_to_send)
        if not can_send:
            print(f"\n{RED}⚠️ Warning: {q_msg}{RESET}")
            if remaining <= 0:
                input(f"\n{YELLOW}Cannot send today. Press Enter to return...{RESET}")
                continue
            
            trim_choice = input(f"Would you like to trim list to {remaining} candidates and proceed? (y/n): ").strip().lower()
            if trim_choice == 'y':
                selected_candidates = selected_candidates[:remaining]
                count_to_send = len(selected_candidates)
            else:
                continue

        # Confirmation & Dispatch Modes
        print(f"\n{CYAN}{BOLD}{'='*72}")
        print(f"🚀 Choose Dispatch Mode:")
        print(f"{CYAN}{BOLD}{'='*72}{RESET}")
        print(f"  [{GREEN}1{RESET}] 🧪 {BOLD}TEST RUN (Send to First 5 Candidates Only){RESET}")
        print(f"  [{GREEN}2{RESET}] 🚀 {BOLD}FULL BATCH (Send to All {len(selected_candidates)} Candidates){RESET}")
        print(f"  [{YELLOW}3{RESET}] 🖥️ {BOLD}Dry-Run Simulation (Print without sending SMS){RESET}")
        print(f"  [{RED}0{RESET}] ❌ Cancel & Return")
        
        mode_choice = input(f"\n{BOLD}Your Choice [0-3]: {RESET}").strip()
        
        if mode_choice == '0':
            continue
        elif mode_choice == '1':
            to_dispatch = selected_candidates[:5]
            is_dry_run = False
        elif mode_choice == '2':
            to_dispatch = selected_candidates
            is_dry_run = False
        elif mode_choice == '3':
            to_dispatch = selected_candidates
            is_dry_run = True
        else:
            print(f"{RED}Invalid option.{RESET}")
            continue

        count_to_send = len(to_dispatch)
        
        if not is_dry_run:
            can_send, remaining, q_msg = quota.check_quota(count_to_send)
            if not can_send:
                print(f"\n{RED}⚠️ Warning: {q_msg}{RESET}")
                input(f"\n{YELLOW}Press Enter to return...{RESET}")
                continue

        print(f"\n{GREEN}{BOLD}🚀 Starting SIM Dispatch Queue ({count_to_send} recipients)... (Press Ctrl+C to pause anytime){RESET}\n")
        
        sent_count = 0
        failed_count = 0

        for i, c in enumerate(to_dispatch, 1):
            c_name = c.get("name") or "Candidate"
            c_phone = c.get("phone")
            final_msg = sms_template.replace("{name}", c_name).replace("{role}", job_context.get("role", "")).replace("{location}", job_context.get("location", "")).replace("{company}", job_context.get("company", ""))

            print(f"[{i}/{count_to_send}] Dispatching to {c_name} (+91-{c_phone})... ", end="", flush=True)
            
            if is_dry_run:
                print(f"{YELLOW}[DRY-RUN SIMULATED]{RESET}")
                sent_count += 1
            else:
                ok, resp = gateway.send_sms(c_phone, final_msg)
                if ok:
                    sent_count += 1
                    quota.record_sent(1)
                    print(f"{GREEN}[SUCCESS]{RESET} ({resp})")
                else:
                    failed_count += 1
                    print(f"{RED}[FAILED]{RESET} ({resp})")

            if i < count_to_send:
                time.sleep(dispatch_delay if not is_dry_run else 0.5)

        print(f"\n{CYAN}{BOLD}{'='*72}")
        print(f"🎉 Dispatch Finished! {GREEN}{sent_count} Sent{RESET}, {RED}{failed_count} Failed{RESET}.")
        print(f"📊 Daily Quota Updated: {quota.state.get('sent_today')}/{quota.limit} sent today.")
        print(f"{CYAN}{BOLD}{'='*72}{RESET}")

        if mode_choice == '1' and len(selected_candidates) > 5:
            cont = input(f"\n{YELLOW}5 Test SMS sent. Would you like to send to the remaining {len(selected_candidates)-5} candidates now? (y/n): {RESET}").strip().lower()
            if cont == 'y':
                remaining_cands = selected_candidates[5:]
                print(f"\n{GREEN}Starting remaining batch ({len(remaining_cands)} candidates)...{RESET}")
                for i, c in enumerate(remaining_cands, 1):
                    c_name = c.get("name") or "Candidate"
                    c_phone = c.get("phone")
                    final_msg = sms_template.replace("{name}", c_name).replace("{role}", job_context.get("role", "")).replace("{location}", job_context.get("location", ""))
                    print(f"[{i}/{len(remaining_cands)}] Dispatching to {c_name} (+91-{c_phone})... ", end="", flush=True)
                    ok, resp = gateway.send_sms(c_phone, final_msg)
                    if ok:
                        quota.record_sent(1)
                        print(f"{GREEN}[SUCCESS]{RESET} ({resp})")
                    else:
                        print(f"{RED}[FAILED]{RESET} ({resp})")
                    if i < len(remaining_cands):
                        time.sleep(dispatch_delay)

        input(f"\n{YELLOW}Press Enter to return to main menu...{RESET}")
        continue

if __name__ == "__main__":
    main()
