# ---------- keep-alive (Flask) ----------
from flask import Flask
import threading

webapp = Flask(__name__)

@webapp.get("/")
def home():
    return "Bot is alive!"

def _run_flask():
    webapp.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = threading.Thread(target=_run_flask, daemon=True)
    t.start()

# ---------- Telegram Bot ----------
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ⚠️ BotFather 토큰 입력
TOKEN = "8261305333:AAHqU9t2ZNGw7ryZtb82M7my_PERgszXoRU"

# ⚠️ 관리자 여러 명 등록
ADMIN_IDS = [7503638843, 7852387923]  # 원하는 관리자 ID 추가

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# 연결/임시저장/유저명 매핑
pairs = {}          # {user_id: partner_id}
uploads = {}        # {user_id: [msg_id, ...]}
usernames = {}      # {username: user_id}
ready_for_exchange = {}  # {user_id: True/False}

# 유저 등록
def _remember_user(update: Update):
    u = update.effective_user
    if u and u.username:
        usernames[u.username] = u.id
    if u and (u.id not in uploads):
        uploads[u.id] = []
    if u and (u.id not in ready_for_exchange):
        ready_for_exchange[u.id] = False

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_user(update)
    await update.message.reply_text(
        "안녕하세요! 1:1 교환 봇입니다.\n"
        "1) 두 사람 모두 /start\n"
        "2) /link <상대 user_id 또는 @username>\n"
        "3) 파일/사진/영상 업로드 (원하면 /cancel로 취소)\n"
        "4) /status → 상대 업로드 수 확인\n"
        "5) 마지막에 두 사람 모두 '교환' 입력해야 교환 실행\n"
        "관리자는 업로드 자료를 실시간으로 확인 가능합니다."
    )

# /link
async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_user(update)
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("사용법: /link <상대 user_id 또는 @username>")
        return

    arg = context.args[0]

    if arg.startswith('@'):
        uname = arg[1:]
        partner_id = usernames.get(uname)
        if partner_id is None:
            await update.message.reply_text("상대가 아직 /start 하지 않았습니다.")
            return
    else:
        try:
            partner_id = int(arg)
        except ValueError:
            await update.message.reply_text("user_id 또는 @username 형식으로 입력해주세요.")
            return

    pairs[user_id] = partner_id
    pairs[partner_id] = user_id
    uploads.setdefault(user_id, [])
    uploads.setdefault(partner_id, [])
    ready_for_exchange[user_id] = False
    ready_for_exchange[partner_id] = False

    await update.message.reply_text(f"연결 완료! 상대: {arg}")

# 업로드 저장 + 관리자 실시간 전달
async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_user(update)
    user_id = update.effective_user.id
    if user_id not in pairs:
        await update.message.reply_text("아직 연결되지 않았습니다. /link로 먼저 연결하세요.")
        return

    uploads[user_id].append(update.message.message_id)
    await update.message.reply_text(f"업로드 완료! 현재 {len(uploads[user_id])}개 업로드됨.")

    # 관리자에게 실시간 전달
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.forward_message(chat_id=admin_id, from_chat_id=user_id, message_id=update.message.message_id)
        except Exception as e:
            print(f"관리자 전송 실패: {e}")

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_user(update)
    user_id = update.effective_user.id
    uploads[user_id] = []
    ready_for_exchange[user_id] = False
    await update.message.reply_text("업로드 및 교환 준비 상태가 모두 취소되었습니다.")

# /status
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_user(update)
    user_id = update.effective_user.id
    if user_id not in pairs:
        await update.message.reply_text("아직 연결되지 않았습니다.")
        return
    partner_id = pairs[user_id]
    count = len(uploads.get(partner_id, []))
    await update.message.reply_text(f"상대방 업로드 수: {count}개")

# "교환" 입력 처리
async def exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_user(update)
    user_id = update.effective_user.id
    if user_id not in pairs:
        await update.message.reply_text("아직 연결되지 않았습니다.")
        return

    partner_id = pairs[user_id]
    ready_for_exchange[user_id] = True
    await update.message.reply_text("교환 준비 완료! 상대방도 '교환'을 입력해야 실행됩니다.")

    if ready_for_exchange.get(user_id) and ready_for_exchange.get(partner_id):
        # 교환 실행
        partner_list = uploads.get(partner_id, [])
        user_list = uploads.get(user_id, [])

        for mid in partner_list:
            await context.bot.forward_message(chat_id=user_id, from_chat_id=partner_id, message_id=mid)

        for mid in user_list:
            await context.bot.forward_message(chat_id=partner_id, from_chat_id=user_id, message_id=mid)

        # 초기화
        uploads[user_id] = []
        uploads[partner_id] = []
        ready_for_exchange[user_id] = False
        ready_for_exchange[partner_id] = False

        await update.message.reply_text("✅ 교환 완료! 서로의 자료가 전달되었습니다.")
        await context.bot.send_message(chat_id=partner_id, text="✅ 교환 완료! 서로의 자료가 전달되었습니다.")

# 관리자 전용: 전체 업로드 현황
async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ 권한이 없습니다.")
        return

    if not uploads:
        await update.message.reply_text("현재 업로드된 자료가 없습니다.")
        return

    msg = "📊 업로드 현황:\n"
    for uid, lst in uploads.items():
        uname = None
        for k, v in usernames.items():
            if v == uid:
                uname = k
        msg += f"- {uid} (@{uname}) → {len(lst)}개\n"
    await update.message.reply_text(msg)

# 앱 구성
def main():
    keep_alive()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("link", link))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("admin_list", admin_list))

    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("교환") & ~filters.COMMAND, exchange))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, upload))

    application.run_polling()

if __name__ == "__main__":
    main()
    
