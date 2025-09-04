#!/usr/bin/env python3

import subprocess
import re
import json
import argparse
from typing import List, Dict, Optional


class InstanceInfo:
    """Represents information about a single VM instance."""
    
    def __init__(self, id: str, node_id: str, status: str, address: str, mode: str, 
                 instance_type: str, user: str, cpus: str, gpus: str, dram: str, 
                 disk: str, gpu_list: str, vm_name: str, vm_id: str):
        self.id = id.strip()
        self.node_id = node_id.strip()
        self.status = status.strip()
        self.address = address.strip()
        self.mode = mode.strip()
        self.instance_type = instance_type.strip()
        self.user = user.strip()
        self.cpus = int(cpus.strip()) if cpus.strip().isdigit() else 0
        self.gpus = int(gpus.strip()) if gpus.strip().isdigit() else 0
        self.dram = int(dram.strip()) if dram.strip().isdigit() else 0
        self.disk = int(disk.strip()) if disk.strip().isdigit() else 0
        self.gpu_list = gpu_list.strip()
        self.vm_name = vm_name.strip()
        self.vm_id = vm_id.strip()
    
    def to_dict(self) -> Dict:
        """Convert instance info to dictionary."""
        return {
            "id": self.id,
            "node_id": self.node_id,
            "status": self.status,
            "address": self.address,
            "mode": self.mode,
            "instance_type": self.instance_type,
            "user": self.user,
            "cpus": self.cpus,
            "gpus": self.gpus,
            "dram": self.dram,
            "disk": self.disk,
            "gpu_list": self.gpu_list,
            "vm_name": self.vm_name,
            "vm_id": self.vm_id
        }
    
    def __str__(self) -> str:
        return f"Instance(id={self.id[:8]}..., node={self.node_id[:8]}..., status={self.status}, user={self.user})"


class NodeInfo:
    """Represents information about a single node."""
    
    def __init__(self, id: str, machine_id: str, address: str, status: str, instance: str):
        self.id = id.strip()
        self.machine_id = machine_id.strip()
        self.address = address.strip()
        self.status = status.strip()
        self.instance = instance.strip() if instance.strip() != "None" else None
        self.instances: List[InstanceInfo] = []
    
    def add_instance(self, instance: InstanceInfo):
        """Add an instance to this node."""
        self.instances.append(instance)
    
    def to_dict(self) -> Dict:
        """Convert node info to dictionary."""
        return {
            "id": self.id,
            "machine_id": self.machine_id,
            "address": self.address,
            "status": self.status,
            "instance": self.instance,
            "instances": [inst.to_dict() for inst in self.instances]
        }
    
    def __str__(self) -> str:
        return f"Node(id={self.id[:8]}..., status={self.status}, address={self.address}, instances={len(self.instances)})"


class NodeListParser:
    """Parser for 'rift node list' and 'rift instance list' commands."""
    
    def run_node_command(self) -> str:
        """Run the 'rift node list' command and return its output."""
        try:
            result = subprocess.run(
                ["rift", "node", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Node command failed with exit code {e.returncode}: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError("'rift' command not found. Make sure it's installed and in your PATH.")
    
    def run_instance_command(self) -> str:
        """Run the 'rift instance list -l -c -g' command and return its output."""
        try:
            result = subprocess.run(
                ["rift", "instance", "list", "-l", "-c", "-g"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Instance command failed with exit code {e.returncode}: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError("'rift' command not found. Make sure it's installed and in your PATH.")
    
    def parse_node_table(self, output: str) -> List[NodeInfo]:
        """Parse the node table output and extract node information."""
        lines = output.strip().split('\n')
        nodes = []
        
        # Find the header line (contains column names)
        header_line = None
        for i, line in enumerate(lines):
            if "ID" in line and "Machine ID" in line and "Address" in line:
                header_line = i
                break
        
        if header_line is None:
            raise ValueError("Could not find table header in node output")
        
        # Skip header and separator lines
        data_start = header_line + 2
        
        for line in lines[data_start:]:
            # Skip separator lines (lines with only +, -, and | characters)
            if re.match(r'^[\+\-\|\s]+$', line):
                continue
            
            # Parse data line
            if '|' in line:
                parts = [part.strip() for part in line.split('|')[1:-1]]  # Remove empty parts at start/end
                
                if len(parts) >= 5:
                    node = NodeInfo(
                        id=parts[0],
                        machine_id=parts[1],
                        address=parts[2],
                        status=parts[3],
                        instance=parts[4]
                    )
                    nodes.append(node)
        
        return nodes
    
    def parse_instance_table(self, output: str) -> List[InstanceInfo]:
        """Parse the instance table output and extract instance information."""
        lines = output.strip().split('\n')
        instances = []
        
        # Find the header line (contains column names)
        header_line = None
        for i, line in enumerate(lines):
            if "Id" in line and "Node Id" in line and "Status" in line:
                header_line = i
                break
        
        if header_line is None:
            raise ValueError("Could not find table header in instance output")
        
        # Skip header and separator lines
        data_start = header_line + 1
        
        for line in lines[data_start:]:
            # Skip empty lines
            if not line.strip():
                continue
            
            # Parse data line with pipe separators
            if '|' in line:
                parts = [part.strip() for part in line.split('|')]
                
                if len(parts) >= 13:
                    instance = InstanceInfo(
                        id=parts[0],
                        node_id=parts[1],
                        status=parts[2],
                        address=parts[3],
                        mode=parts[4],
                        instance_type=parts[5],
                        user=parts[6],
                        cpus=parts[7],
                        gpus=parts[8],
                        dram=parts[9],
                        disk=parts[10],
                        gpu_list=parts[11],
                        vm_name=parts[12],
                        vm_id=parts[13] if len(parts) > 13 else ""
                    )
                    instances.append(instance)
        
        return instances
    
    def get_nodes_with_instances(self) -> List[NodeInfo]:
        """Get all nodes and their instances by running both commands."""
        # Get nodes
        node_output = self.run_node_command()
        nodes = self.parse_node_table(node_output)
        
        # Get instances
        instance_output = self.run_instance_command()
        instances = self.parse_instance_table(instance_output)
        print(f"Parsed {len(nodes)} nodes and {len(instances)} instances.")
        
        # Create a lookup dictionary for nodes
        node_dict = {node.id: node for node in nodes}
        
        # Associate instances with their nodes
        for instance in instances:
            if instance.node_id in node_dict:
                node_dict[instance.node_id].add_instance(instance)
        
        return nodes


def main():
    """Main function to demonstrate the script."""
    parser = argparse.ArgumentParser(description='Parse rift node and instance information')
    parser.add_argument('--save-json', '--save', action='store_true', 
                       help='Save output to nodes.json file')
    parser.add_argument('--output', '-o', default='nodes.json',
                       help='Output JSON filename (default: nodes.json)')
    parser.add_argument('--long-ids', action='store_true',
                       help='Display full IDs instead of truncated ones')
    
    args = parser.parse_args()
    
    node_parser = NodeListParser()
    
    try:
        nodes = node_parser.get_nodes_with_instances()
        
        print(f"Found {len(nodes)} nodes:")
        print("-" * 80)
        
        # Group by status
        status_groups = {}
        for node in nodes:
            if node.status not in status_groups:
                status_groups[node.status] = []
            status_groups[node.status].append(node)
        
        for status, nodes_with_status in status_groups.items():
            print(f"\n{status} nodes ({len(nodes_with_status)}):")
            for node in nodes_with_status:
                instance_info = f" - {node.instance}" if node.instance else "(type not set)"
                node_id_display = node.id if args.long_ids else f"{node.id[:8]}..."
                machine_id_display = node.machine_id if args.long_ids else f"{node.machine_id[:8]}..."
                print(f"  {node_id_display} | {node.address:<15} | {machine_id_display}{instance_info} | Instances: {len(node.instances)}")
                for instance in node.instances:
                    instance_id_display = instance.id if args.long_ids else f"{instance.id[:8]}..."
                    print(f"    {instance_id_display} | {instance.address:<15} | {instance.status} | {instance.user} | CPUs: {instance.cpus}, GPUs: {instance.gpus}, DRAM: {instance.dram}MB, Disk: {instance.disk}GB")
        
        # Optionally save to JSON
        if args.save_json:
            print(f"\nSaving node data to {args.output}...")
            with open(args.output, "w") as f:
                json.dump([node.to_dict() for node in nodes], f, indent=2)
            print(f"Data saved to {args.output}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

