.PHONY: help system-deps venv install configure clean

# Python configuration
PYTHON := python3
VENV_DIR := venv
VENV_BIN := $(VENV_DIR)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
REQUIREMENTS := python/requirements.txt
CONFIGURE_SCRIPT := python/configure/configure.py

# System packages required
SYSTEM_PACKAGES := python3 python3-venv python3-pip

help:
	@echo "CloudRift Utilities - Makefile Commands"
	@echo "========================================"
	@echo "make system-deps - Install system dependencies (requires sudo)"
	@echo "make venv        - Create Python virtual environment"
	@echo "make install     - Install Python dependencies in venv"
	@echo "make configure   - Complete setup and run configure.py (requires sudo)"
	@echo "make clean       - Remove virtual environment"
	@echo ""
	@echo "Quick start: sudo make configure"

system-deps:
	@echo "Installing system dependencies..."
	@echo "This requires sudo privileges and will install: $(SYSTEM_PACKAGES)"
	@sudo apt-get update
	@sudo apt-get install -y $(SYSTEM_PACKAGES)
	@echo "System dependencies installed successfully"

venv: system-deps
	@echo "Creating virtual environment..."
	@$(PYTHON) -m venv $(VENV_DIR)
	@echo "Virtual environment created at ./$(VENV_DIR)"

install: venv
	@echo "Installing dependencies..."
	@$(VENV_PIP) install --upgrade pip
	@$(VENV_PIP) install -r $(REQUIREMENTS)
	@echo "Dependencies installed successfully"

configure: install
	@echo "Running configure script with sudo..."
	@sudo $(VENV_PYTHON) $(CONFIGURE_SCRIPT)

clean:
	@echo "Removing virtual environment..."
	@rm -rf $(VENV_DIR)
	@echo "Virtual environment removed"
