cat >/etc/default/grub.d/98-extra-cmdline.cfg <<'EOF'
EXTRA_CMDLINE="module_blacklist=nvidia_drm,nvidia_modeset nouveau.modeset=0 pci=realloc pci=pcie_bus_perf"
GRUB_CMDLINE_LINUX_DEFAULT="${GRUB_CMDLINE_LINUX_DEFAULT:+$GRUB_CMDLINE_LINUX_DEFAULT }$EXTRA_CMDLINE"
GRUB_CMDLINE_LINUX="${GRUB_CMDLINE_LINUX:+$GRUB_CMDLINE_LINUX }$EXTRA_CMDLINE"
EOF

sudo tee /etc/default/grub.d/00-disable-os-prober.cfg >/dev/null <<'EOF'
GRUB_DISABLE_OS_PROBER=true
EOF

cat >/etc/modprobe.d/99-nvidia-compute-only.conf <<'EOF'
# Block display-related pieces
blacklist nvidia_drm
blacklist nvidia_modeset
# (belt-and-suspenders) ensure KMS stays off if nvidia-drm ever loads
options nvidia-drm modeset=0

# Just in case: never load nouveau either
blacklist nouveau
options nouveau modeset=0
EOF

grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=ubuntu --removable

update-initramfs -u -k all

update-grub
