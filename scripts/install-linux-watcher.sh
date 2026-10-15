#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin=$(command -v python3)
python_version=$("$python_bin" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
install_dir="$HOME/.local/share/backup-imagen/py$python_version"
install_root="$HOME/.local/share/backup-imagen"
venv_python="$install_dir/bin/python"
mkdir -p "$(dirname -- "$install_dir")"
if [ ! -x "$venv_python" ]; then
    "$python_bin" -m venv "$install_dir" || {
        printf '%s\n' 'No se pudo crear el entorno Python. Instala python3-venv y vuelve a ejecutar.' >&2
        exit 1
    }
fi
"$venv_python" -m pip install "$repo_root"
printf '%s\n' "$python_version" > "$install_root/python-version"

bin_dir="$HOME/.local/bin"
service_dir="$HOME/.config/systemd/user"
mkdir -p "$bin_dir" "$service_dir"
cat > "$bin_dir/backup-imagen-watch" <<EOF
#!/usr/bin/env sh
exec "$venv_python" -m backup_imagen --watch
EOF
chmod +x "$bin_dir/backup-imagen-watch"

escaped_command=$(printf '%s' "$bin_dir/backup-imagen-watch" | sed 's/ /\\s/g')
cat > "$service_dir/backup-imagen-watcher.service" <<EOF
[Unit]
Description=Detecta el USB NTFS de 32 GB para Backup Imagen

[Service]
ExecStart=$escaped_command
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
if command -v dbus-update-activation-environment >/dev/null 2>&1; then
    dbus-update-activation-environment --systemd DISPLAY WAYLAND_DISPLAY XAUTHORITY 2>/dev/null || true
fi
systemctl --user enable --now backup-imagen-watcher.service
printf '%s\n' 'Monitor instalado. Al conectar el USB se abrirá la terminal disponible.'
