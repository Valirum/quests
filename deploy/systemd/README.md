# Quests — systemd user units
#
# Install (once):
#   mkdir -p ~/.config/systemd/user
#   ln -sf "$PWD/deploy/systemd/user/"*.service ~/.config/systemd/user/
#   # or: cp deploy/systemd/user/*.service ~/.config/systemd/user/
#   systemctl --user daemon-reload
#
# Import Wayland env into the user manager (niri / login — once per session or in config):
#   systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR DISPLAY NIRI_SOCKET
#
# Enable / start (examples — do not run from CI; you start when ready):
#   systemctl --user enable --now quests-server.service
#   systemctl --user enable --now quests-overlay.service
#   systemctl --user start quests-frontend-dev.service   # optional, HMR
#
# WorkingDirectory assumes the repo at ~/Documents/projects/Quests.
# Edit WorkingDirectory / ExecStart if the clone lives elsewhere.
