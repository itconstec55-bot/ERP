#!/usr/bin/env bash
# سكربت إعداد خادم ERP (لينكس Ubuntu 22.04+)
# شغّله كـ root على الخادم الهدف قبل تفعيل النشر التلقائي من GitHub Actions.
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
APP_PATH="${DEPLOY_PATH:-/home/$DEPLOY_USER/erp}"
SSH_KEY_PATH="/home/$DEPLOY_USER/.ssh/erp_deploy_key"

echo "==> تحديث النظام وتثبيت المتطلبات"
apt-get update
apt-get install -y docker.io docker-compose-plugin git curl ufw

echo "==> تمكين docker عند الإقلاع"
systemctl enable --now docker

echo "==> إنشاء مستخدم النشر $DEPLOY_USER"
if ! id "$DEPLOY_USER" &>/dev/null; then
  useradd -m -s /bin/bash "$DEPLOY_USER"
fi
usermod -aG docker "$DEPLOY_USER"

echo "==> تجهيز مفاتيح SSH للمستخدم"
mkdir -p "/home/$DEPLOY_USER/.ssh"
chmod 700 "/home/$DEPLOY_USER/.ssh"
# أنشئ مفتاح النشر إن لم يوجد (احفظ الخاص منه في GitHub secret DEPLOY_SSH_KEY)
if [ ! -f "$SSH_KEY_PATH" ]; then
  ssh-keygen -t ed25519 -C "github-deploy" -f "$SSH_KEY_PATH" -N ""
  cat "${SSH_KEY_PATH}.pub" >> "/home/$DEPLOY_USER/.ssh/authorized_keys"
  chmod 600 "/home/$DEPLOY_USER/.ssh/authorized_keys"
  echo ">> مفتاح النشر الجديد وُلّد. انسخ محتوى $SSH_KEY_PATH إلى GitHub secret DEPLOY_SSH_KEY"
fi

echo "==> استنساخ المستودع"
if [ ! -d "$APP_PATH" ]; then
  sudo -u "$DEPLOY_USER" git clone https://github.com/itconstec55-bot/ERP.git "$APP_PATH"
fi

echo "==> ملف .env على الخادم (املأ القيم بسرية قوية)"
if [ ! -f "$APP_PATH/.env" ]; then
  sudo -u "$DEPLOY_USER" bash -c "cat > $APP_PATH/.env" <<EOF
DJANGO_SECRET_KEY=CHANGE_ME_TO_A_STRONG_RANDOM_KEY
DJANGO_DEBUG=false
DJANGO_DB_PASSWORD=$(openssl rand -base64 18)
BIND_PORT=8012
EOF
  echo ">> عدّل $APP_PATH/.env وضع قيمة DJANGO_SECRET_KEY قوية (openssl rand -base64 50)"
fi

echo "==> فتح المنفذ 8012"
ufw allow 22
ufw allow 8012
ufw --force enable || true

echo "==> جاهز. الآن أضف أسرار GitHub: DEPLOY_HOST (IP هذا الخادم), DEPLOY_USER=$DEPLOY_USER, DEPLOY_SSH_KEY (محتوى $SSH_KEY_PATH)"
