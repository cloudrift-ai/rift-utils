#!/usr/bin/env python3

import os
import sys
import argparse
from typing import Dict, Any

from pyparsing import ABC
from commands.cmd import BaseCmd
from commands.utils import numbered_prompt, reboot_prompt, yes_no_prompt
from commands.nvidia import InstallNvidiaCudaToolkitCmd, InstallNvidiaDriverCmd, RemoveNvidiaDriverCmd
from commands.apt_install import AptInstallCmd
from commands.configure_libvirt import ConfigureLibvirtCmd, CheckVirtualizationCmd
from commands.configure_grub import ReadGrubCmd, GetIommuTypeCmd, GetGpuPciIdsCmd, AddGrubVirtualizationOptionsCmd, CreateGrubOverrideCmd, RemoveGrubOverrideCmd
from commands.configure_initramfs import UpdateInitramfsModulesCmd
from commands.configure_modprobe import CreateVfioConfCmd
from commands.configure_memory import ConfigureMemoryCmd
from commands.configure_disks import ConfigureDisksCmd
from commands.configure_gpu_power import VerifyGpuPowerStateCmd, ConfigureGpuPowerCmd
from commands.configure_docker import ConfigureDockerCmd

GRUB_MAIN_FILE = '/etc/default/grub'
GRUB_D_DIR = '/etc/default/grub.d'
VFIO_GRUB_FILE = os.path.join(GRUB_D_DIR, '99-cloudrift.cfg')


REQUIRED_PACKAGES = [
    "qemu-kvm",
    "libvirt-daemon-system",
    "genisoimage",
    "whois",
    "mdadm"  # RAID devices
]

def reboot_server():
    """
    Prompts the user to reboot and provides verification instructions.
    """
    print("\n--- Reboot and Verify ---")
    print("The configuration is complete. You need to reboot for the changes to take effect.")
    print("After rebooting, you can verify the configuration by running the following commands:")
    print("  grep -i huge /proc/meminfo")
    print("  grep hugetlbfs /proc/mounts")
    reboot_prompt()

class Workflow(ABC):

    commands: list[BaseCmd] = []

    """
    Abstract base class for configuration commands.
    """
    def name(self) -> str:
        raise NotImplementedError("Subclasses must implement name()")

    def description(self) -> str:
        raise NotImplementedError("Subclasses must implement description()")

    def execute(self, env: Dict[str, Any]) -> bool | None:
        total_commands = len(self.commands)
        print(f"📋 Found {total_commands} configuration command(s) to execute:")
        print("-" * 60)
        
        # Print overview of all commands first
        for i, command in enumerate(self.commands, start=1):
            print(f"  {i}. {command.name()}")
            print(f"     └─ {command.description()}")
        print("-" * 60)
        print()

        # Prompt for confirmation
        if yes_no_prompt("Do you want to proceed with these changes?", default=True) is False:
            print("Operation cancelled by user.")
            return None  # Not an error, just cancelled

        env = {}  # Shared environment dictionary for commands

        # Execute commands with enhanced output
        for i, command in enumerate(self.commands, start=1):
            print(f"🚀 Step {i}/{total_commands}: {command.name()}")
            print(f"📝 Description: {command.description()}")
            print(f"⏳ Executing...")
            
            try:
                success = command.execute(env)
                if success:
                    print(f"✅ Step {i}/{total_commands} completed successfully!")
                else:
                    print(f"❌ Step {i}/{total_commands} failed!")
                    print(f"💥 Command '{command.name()}' encountered an error. Exiting.")
                    return False
            except Exception as e:
                print(f"❌ Step {i}/{total_commands} failed with exception!")
                print(f"💥 Error: {str(e)}")
                print(f"🛑 Command '{command.name()}' failed. Exiting.")
                return False

            print("-" * 40)
            print()

        print("🎉 All configuration commands completed successfully!")
        print("=" * 60)        
        return True

# All available commands to execute selectively
NODE_COMMANDS = [
    CheckVirtualizationCmd(),
    InstallNvidiaDriverCmd(),
    RemoveNvidiaDriverCmd(),
    AptInstallCmd(REQUIRED_PACKAGES),
    ConfigureDockerCmd(),
    InstallNvidiaCudaToolkitCmd(),
    ConfigureLibvirtCmd(),
    ReadGrubCmd(),
    GetIommuTypeCmd(),
    GetGpuPciIdsCmd(),
    AddGrubVirtualizationOptionsCmd(),
    UpdateInitramfsModulesCmd(),
    CreateVfioConfCmd(),
    ConfigureGpuPowerCmd(),  # Configure GPU power management (udev + modprobe)
    ConfigureMemoryCmd(),
    ConfigureDisksCmd(),
    CreateGrubOverrideCmd(),
    RemoveGrubOverrideCmd(),
    VerifyGpuPowerStateCmd()  # Verify GPU power settings at the end
]

class VmOnlyWorkflow(Workflow):

    def __init__(self) -> None:
        super().__init__()
        self.commands = [
            CheckVirtualizationCmd(),
            RemoveNvidiaDriverCmd(),
            AptInstallCmd(REQUIRED_PACKAGES),
            ConfigureDockerCmd(),
            ConfigureLibvirtCmd(),
            ReadGrubCmd(),
            GetIommuTypeCmd(),
            GetGpuPciIdsCmd(),
            AddGrubVirtualizationOptionsCmd(),
            UpdateInitramfsModulesCmd(),
            CreateVfioConfCmd(),
            ConfigureGpuPowerCmd(),  # Configure GPU power management (udev + modprobe)
            ConfigureMemoryCmd(),
            ConfigureDisksCmd(),
            CreateGrubOverrideCmd(),
            VerifyGpuPowerStateCmd()  # Verify GPU power settings at the end
        ]

    def name(self) -> str:
        return "VM-Only Configuration Workflow"

    def description(self) -> str:
        return "A workflow for configuring a virtual machine environment."

class VmAndDockerWorkflow(Workflow):

    def __init__(self) -> None:
        super().__init__()
        self.commands = [
            CheckVirtualizationCmd(),
            AptInstallCmd(REQUIRED_PACKAGES),
            RemoveGrubOverrideCmd(),
            InstallNvidiaDriverCmd(),
            ConfigureDockerCmd(),
            InstallNvidiaCudaToolkitCmd(),
            ConfigureLibvirtCmd(),
            ReadGrubCmd(),
            GetIommuTypeCmd(),
            GetGpuPciIdsCmd(),
            AddGrubVirtualizationOptionsCmd(),
            UpdateInitramfsModulesCmd(),
            CreateVfioConfCmd(),
            ConfigureGpuPowerCmd(),  # Configure GPU power management (udev + modprobe)
            ConfigureMemoryCmd(),
            ConfigureDisksCmd(),
            CreateGrubOverrideCmd(),
            VerifyGpuPowerStateCmd()  # Verify GPU power settings at the end
        ]

    def name(self) -> str:
        return "VM and Docker Configuration Workflow"

    def description(self) -> str:
        return "A workflow for configuring both virtual machine and Docker environments."

class TestWorkflow(Workflow):
    
    def __init__(self) -> None:
        super().__init__()
        self.commands = [
            CheckVirtualizationCmd(),
            AptInstallCmd(REQUIRED_PACKAGES),
            InstallNvidiaDriverCmd(),
            RemoveGrubOverrideCmd(),
            InstallNvidiaCudaToolkitCmd(),
        ]

    def name(self) -> str:
        return "Test Configuration Workflow"

    def description(self) -> str:
        return "A test workflow for verifying configuration steps."

WORKFLOWS = [
    VmAndDockerWorkflow(),
    VmOnlyWorkflow(),
    TestWorkflow()
]

def list_workflows():
    """
    List all available configuration workflows.
    """
    print("=" * 60)
    print("📋 AVAILABLE CONFIGURATION WORKFLOWS")
    print("=" * 60)
    
    for i, workflow in enumerate(WORKFLOWS, start=1):
        print(f"  {i}. {workflow.name()}")
        print(f"     └─ {workflow.description()}")
    print("=" * 60)
    print(f"Total: {len(WORKFLOWS)} workflows available")

def execute_workflow(workflow_identifier):
    """
    Execute a specific workflow by index or name.
    """
    if os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)

    env = {}  # Shared environment dictionary
    workflow_to_execute = None
    workflow_index = None

    # Try to parse as index first
    try:
        index = int(workflow_identifier) - 1  # Convert to 0-based index
        if 0 <= index < len(WORKFLOWS):
            workflow_to_execute = WORKFLOWS[index]
            workflow_index = index + 1
    except ValueError:
        # Not a number, try to find by name
        for i, workflow in enumerate(WORKFLOWS):
            if workflow.name().lower() == workflow_identifier.lower():
                workflow_to_execute = workflow
                workflow_index = i + 1
                break

    if workflow_to_execute is None:
        print(f"❌ Workflow '{workflow_identifier}' not found.")
        print("Use --list-workflows to see available workflows.")
        sys.exit(1)

    print("=" * 60)
    print(f"🚀 Executing workflow {workflow_index}: {workflow_to_execute.name()}")
    print(f"📝 Description: {workflow_to_execute.description()}")
    print(f"⏳ Executing...")
    
    try:
        success = workflow_to_execute.execute(env)
        if success is None:
            print("⚠️ Workflow execution cancelled by user.")
            sys.exit(0)
        elif success:
            print(f"✅ Workflow completed successfully!")
        else:
            print(f"❌ Workflow failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Workflow failed with exception!")
        print(f"💥 Error: {str(e)}")
        sys.exit(1)
    
    print("🎉 Workflow execution completed!")
    print("=" * 60)

    reboot_server()

def list_commands():
    """
    List all available configuration commands.
    """
    print("=" * 60)
    print("📋 AVAILABLE CONFIGURATION COMMANDS")
    print("=" * 60)
    
    for i, command in enumerate(NODE_COMMANDS, start=1):
        print(f"  {i}. {command.name()}")
        print(f"     └─ {command.description()}")
    print("=" * 60)
    print(f"Total: {len(NODE_COMMANDS)} commands available")

def execute_specific_command(command_identifier):
    """
    Execute a specific command by index or name.
    """
    if os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)

    env = {}  # Shared environment dictionary
    command_to_execute = None
    command_index = None

    # Try to parse as index first
    try:
        index = int(command_identifier) - 1  # Convert to 0-based index
        if 0 <= index < len(NODE_COMMANDS):
            command_to_execute = NODE_COMMANDS[index]
            command_index = index + 1
    except ValueError:
        # Not a number, try to find by name
        for i, command in enumerate(NODE_COMMANDS):
            if command.name().lower() == command_identifier.lower():
                command_to_execute = command
                command_index = i + 1
                break

    if command_to_execute is None:
        print(f"❌ Command '{command_identifier}' not found.")
        print("Use --list to see available commands.")
        sys.exit(1)

    print("=" * 60)
    print("🔧 EXECUTING SPECIFIC COMMAND")
    print("=" * 60)
    print(f"🚀 Executing command {command_index}: {command_to_execute.name()}")
    print(f"📝 Description: {command_to_execute.description()}")
    print(f"⏳ Executing...")
    
    try:
        success = command_to_execute.execute(env)
        if success:
            print(f"✅ Command completed successfully!")
        else:
            print(f"❌ Command failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Command failed with exception!")
        print(f"💥 Error: {str(e)}")
        sys.exit(1)
    
    print("🎉 Command execution completed!")
    print("=" * 60)

def configure_node():
    """
    Main function to orchestrate the script's execution.
    """
    if os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)

    print("=" * 60)
    print("🔧 NODE CONFIGURATION SCRIPT")
    print("=" * 60)
    print("This script will configure your system for server use.")
    print("It adds the necessary kernel parameters to /etc/default/grub.d/99-cloudrift.cfg,")
    print("/etc/initramfs-tools/modules, and /etc/modprobe.d/vfio.conf.")
    print()

    total_commands = len(NODE_COMMANDS)
    print(f"📋 Found {total_commands} configuration command(s) to execute:")
    print("-" * 60)
    
    # Print overview of all commands first
    for i, command in enumerate(NODE_COMMANDS, start=1):
        print(f"  {i}. {command.name()}")
        print(f"     └─ {command.description()}")
    print("-" * 60)
    print()

    env = {}  # Shared environment dictionary for commands

    # Execute commands with enhanced output
    for i, command in enumerate(NODE_COMMANDS, start=1):
        print(f"🚀 Step {i}/{total_commands}: {command.name()}")
        print(f"📝 Description: {command.description()}")
        print(f"⏳ Executing...")
        
        try:
            success = command.execute(env)
            if success:
                print(f"✅ Step {i}/{total_commands} completed successfully!")
            else:
                print(f"❌ Step {i}/{total_commands} failed!")
                print(f"💥 Command '{command.name()}' encountered an error. Exiting.")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Step {i}/{total_commands} failed with exception!")
            print(f"💥 Error: {str(e)}")
            print(f"🛑 Command '{command.name()}' failed. Exiting.")
            sys.exit(1)
        
        print("-" * 40)
        print()

    print("🎉 All configuration commands completed successfully!")
    print("=" * 60)

    reboot_server()

def main():
    """
    Parse command line arguments and execute appropriate action.
    """
    parser = argparse.ArgumentParser(
        description="Configure your system for server use with QEMU/KVM virtualization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  configure.py                     # Run all configuration commands
  configure.py --list-workflows    # List all available workflows
  configure.py --list-commands     # List all available commands
  configure.py --workflow <index or name>  # Execute a specific workflow
  configure.py --command 3         # Execute command #3 only
  configure.py --command "Remove Nvidia Driver"  # Execute by name
        """
    )

    parser.add_argument(
        "--list-workflows", 
        action="store_true",
        help="List all available configuration workflows"
    )

    parser.add_argument(
        "--list-commands", 
        action="store_true",
        help="List all available configuration commands"
    )
    
    parser.add_argument(
        "--workflow", 
        metavar="ID_OR_NAME",
        help="Execute only the specified workflow (by number or name)"
    )

    parser.add_argument(
        "--command", 
        metavar="ID_OR_NAME",
        help="Execute only the specified command (by number or name)"
    )
    
    args = parser.parse_args()
    
    if args.list_workflows:
        list_workflows()
    elif args.list_commands:
        list_commands()
    elif args.command:
        execute_specific_command(args.command)
    elif args.workflow:
        execute_workflow(args.workflow)
    else:
        list_workflows()
        workflow_choice = numbered_prompt("Select workflow for this node", 1, len(WORKFLOWS))
        if workflow_choice is not None:
            execute_workflow(workflow_choice)

if __name__ == "__main__":
    main()
