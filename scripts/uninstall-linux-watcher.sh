#!/usr/bin/env sh
set -eu

systemctl --user disable --now backup-imagen-watcher.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/backup-imagen-watcher.service"
rm -f "$HOME/.local/bin/backup-imagen-watch"
if [ -n "${HOME:-}" ]; then
    rm -rf -- "$HOME/.local/share/backup-imagen"
fi
systemctl --user daemon-reload
printf '%s\n' 'Monitor eliminado del inicio de sesión.'
