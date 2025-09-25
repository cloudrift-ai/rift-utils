#!/bin/bash

# FRP Bootstrap Installation Script
# Usage: ./bootstrap.sh [server|client]
# Installs FRP (Fast Reverse Proxy) v0.64.0 with systemd integration

set -euo pipefail

# Configuration
FRP_VERSION="0.64.0"
FRP_URL="https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz"
FRP_INSTALL_DIR="/opt/frp"
FRP_CONFIG_DIR="/etc/frp"
FRP_CONFD_DIR="/etc/frp/confd"
TEMP_DIR="/tmp/frp_install"
MODE=""  # Initialize MODE variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Validate arguments
validate_args() {
    if [[ $# -ne 1 ]]; then
        log_error "Usage: $0 [server|client]"
        exit 1
    fi

    case "$1" in
        server|client)
            MODE="$1"
            ;;
        *)
            log_error "Invalid argument. Use 'server' or 'client'"
            exit 1
            ;;
    esac
}

# Create directories
create_directories() {
    log_info "Creating directories..."
    mkdir -p "$FRP_INSTALL_DIR"
    mkdir -p "$FRP_CONFIG_DIR"
    mkdir -p "$FRP_CONFD_DIR"
    mkdir -p "$TEMP_DIR"
}

# Download and extract FRP
download_frp() {
    log_info "Downloading FRP v${FRP_VERSION}..."
    cd "$TEMP_DIR"

    if ! curl -L -o "frp_${FRP_VERSION}_linux_amd64.tar.gz" "$FRP_URL"; then
        log_error "Failed to download FRP"
        exit 1
    fi

    log_info "Extracting FRP..."
    tar -xzf "frp_${FRP_VERSION}_linux_amd64.tar.gz"

    # Copy binaries to install directory
    cp "frp_${FRP_VERSION}_linux_amd64/frps" "$FRP_INSTALL_DIR/"
    cp "frp_${FRP_VERSION}_linux_amd64/frpc" "$FRP_INSTALL_DIR/"
    cp "frp_${FRP_VERSION}_linux_amd64/LICENSE" "$FRP_INSTALL_DIR/"

    # Make binaries executable
    chmod +x "$FRP_INSTALL_DIR/frps"
    chmod +x "$FRP_INSTALL_DIR/frpc"

    log_info "FRP binaries installed to $FRP_INSTALL_DIR"
}

# Generate random token
generate_token() {
    openssl rand -hex 32
}

# Create server configuration
create_server_config() {
    log_info "Creating server configuration..."
    local token
    token=$(generate_token)

    cat > "$FRP_CONFIG_DIR/frps.toml" << EOF
bindAddr = "0.0.0.0"
bindPort = 7000
auth.token = "$token"
EOF

    log_info "Server configuration created at $FRP_CONFIG_DIR/frps.toml"
    log_warn "Generated auth token: $token"
    log_warn "Please save this token for client configuration!"
}

# Create client configuration
create_client_config() {
    log_info "Creating client configuration..."
    local token
    token=$(generate_token)

    cat > "$FRP_CONFIG_DIR/frpc.toml" << EOF
serverAddr = "10.21.106.201"
serverPort = 7000
includes = ["/etc/frp/confd/*.toml"]

[webServer]
addr = "127.0.0.1"
port = 7500

[auth]
token = "$token"
EOF

    log_info "Client configuration created at $FRP_CONFIG_DIR/frpc.toml"
    log_warn "Generated auth token: $token"
    log_warn "Please update the auth token to match your server!"
}

# Create systemd service for server
create_server_service() {
    log_info "Creating systemd service for FRP server..."

    cat > /etc/systemd/system/frps.service << EOF
[Unit]
Description=FRP Server
After=network.target
Wants=network.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=$FRP_INSTALL_DIR/frps -c $FRP_CONFIG_DIR/frps.toml
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
Restart=on-failure
RestartSec=5s

# Logging configuration for journald
StandardOutput=journal
StandardError=journal
SyslogIdentifier=frps

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$FRP_CONFIG_DIR

[Install]
WantedBy=multi-user.target
EOF

    log_info "FRP server service created"
}

# Create systemd service for client
create_client_service() {
    log_info "Creating systemd service for FRP client..."

    cat > /etc/systemd/system/frpc.service << EOF
[Unit]
Description=FRP Client
After=network.target
Wants=network.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=$FRP_INSTALL_DIR/frpc -c $FRP_CONFIG_DIR/frpc.toml
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
Restart=on-failure
RestartSec=5s

# Logging configuration for journald
StandardOutput=journal
StandardError=journal
SyslogIdentifier=frpc

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$FRP_CONFIG_DIR

[Install]
WantedBy=multi-user.target
EOF

    log_info "FRP client service created"
}

# Set proper permissions
set_permissions() {
    log_info "Setting proper permissions..."
    chown -R root:root "$FRP_INSTALL_DIR"
    chown -R root:root "$FRP_CONFIG_DIR"
    chmod 755 "$FRP_INSTALL_DIR"
    chmod 755 "$FRP_CONFIG_DIR"
    chmod 755 "$FRP_CONFD_DIR"
    chmod 644 "$FRP_CONFIG_DIR"/*.toml 2>/dev/null || true
}

# Enable and start service
enable_service() {
    local service_name="frp${MODE:0:1}" # frps or frpc

    log_info "Reloading systemd daemon..."
    systemctl daemon-reload

    log_info "Enabling $service_name service..."
    systemctl enable "$service_name"

    log_info "Starting $service_name service..."
    if systemctl start "$service_name"; then
        log_info "$service_name service started successfully"
        log_info "Service status:"
        systemctl status "$service_name" --no-pager -l
    else
        log_error "Failed to start $service_name service"
        log_error "Check logs with: journalctl -u $service_name -f"
        exit 1
    fi
}

# Cleanup temporary files
cleanup() {
    log_info "Cleaning up temporary files..."
    rm -rf "$TEMP_DIR"
}

# Show final instructions
show_instructions() {
    log_info "Installation completed successfully!"
    echo
    log_info "Service management commands:"
    echo "  Start:   systemctl start frp${MODE:0:1}"
    echo "  Stop:    systemctl stop frp${MODE:0:1}"
    echo "  Restart: systemctl restart frp${MODE:0:1}"
    echo "  Status:  systemctl status frp${MODE:0:1}"
    echo "  Logs:    journalctl -u frp${MODE:0:1} -f"
    echo
    log_info "Configuration files:"
    echo "  Config:  $FRP_CONFIG_DIR/frp${MODE:0:1}.toml"
    if [[ "$MODE" == "client" ]]; then
        echo "  Additional configs: $FRP_CONFD_DIR/*.toml"
    fi
    echo "  Binaries: $FRP_INSTALL_DIR/"
    echo
    if [[ "$MODE" == "client" ]]; then
        log_warn "Remember to update the auth token in $FRP_CONFIG_DIR/frpc.toml to match your server!"
        log_warn "Web interface available at: http://127.0.0.1:7500"
    fi
}

# Main installation function
main() {
    log_info "Starting FRP installation in $MODE mode..."

    check_root
    validate_args "$@"
    create_directories
    download_frp

    case "$MODE" in
        server)
            create_server_config
            create_server_service
            ;;
        client)
            create_client_config
            create_client_service
            ;;
    esac

    set_permissions
    enable_service
    cleanup
    show_instructions

    log_info "FRP $MODE installation completed successfully!"
}

# Run main function with all arguments
main "$@"