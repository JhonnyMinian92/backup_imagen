#!/usr/bin/env sh
set -eu

systemctl --user disable --now backup-imagen-watcher.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/backup-imagen-watcher.service"
rm -f "$HOME/.local/bin/backup-imagen-watch"
if [ -n "${HOME:-}" ]; then
    install_root="$HOME/.local/share/backup-imagen"
    version_file="$install_root/python-version"
    if [ -f "$version_file" ] && [ ! -L "$install_root" ]; then
        python_version=$(cat -- "$version_file")
        case "$python_version" in
            *.*)
                major=${python_version%%.*}
                minor=${python_version#*.}
                case "$major" in ''|*[!0-9]*) python_version="" ;; esac
                case "$minor" in ''|*[!0-9]*) python_version="" ;; esac
                ;;
            *) python_version="" ;;
        esac
        if [ -n "$python_version" ]; then
            install_dir="$install_root/py$python_version"
            if [ -d "$install_dir" ] && [ ! -L "$install_dir" ]; then
                rm -rf -- "$install_dir"
            fi
        fi
        rm -f -- "$version_file"
        rmdir -- "$install_root" 2>/dev/null || true
    fi
fi
systemctl --user daemon-reload
printf '%s\n' 'Monitor eliminado del inicio de sesión.'
