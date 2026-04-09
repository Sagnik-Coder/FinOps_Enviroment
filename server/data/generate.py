import json
import numpy as np
import random
import os

def generate_cpu_logs(days=30, server_type="standard"):
    states = [0, 1, 2]
    transition_matrix = [
        [0.70, 0.25, 0.05],
        [0.20, 0.60, 0.20],  
        [0.05, 0.35, 0.60] 
    ]
    
    if server_type == "spike":
        lambdas = [20.0, 60.0, 95.0] 
    elif server_type == "trap":
        lambdas = [1.0, 3.0, 5.0] 
    elif server_type == "easy_win":
        lambdas = [0.1, 0.3, 0.5]
    else:
        lambdas = [10.0, 35.0, 75.0]

    cpu_logs = []
    network_egress_gb = []
    current_state = 1 
    
    for _ in range(days):
        current_state = np.random.choice(states, p=transition_matrix[current_state])
        daily_cpu = np.random.poisson(lam=lambdas[current_state])
        jittered_cpu = daily_cpu + random.uniform(-2.5, 2.5)
        cpu_logs.append(round(min(100.0, max(0.0, jittered_cpu)), 2))
        
        if server_type == "trap":
            daily_egress = np.random.poisson(lam=250.0) 
        elif server_type == "easy_win":
            daily_egress = np.random.poisson(lam=0.5)
        else:
            daily_egress = np.random.poisson(lam=daily_cpu * 2.8) 
            
        network_egress_gb.append(round(daily_egress, 2))
        
    return cpu_logs, network_egress_gb

def generate_fragmented_metadata():
    network_flows = [
        {"src_ip": "10.0.1.5", "dest_ip": "10.0.1.200", "port": 5432, "packets_sec": 1200},
        {"src_ip": "10.0.1.12", "dest_ip": "172.217.1.1", "port": 443, "packets_sec": 50}
    ]
    inventory = {
        "db-master-prod": "10.0.1.5",
        "cron-log-rotator-tmp": "10.0.1.200", 
        "api-gateway-01": "10.0.1.12"
    }
    security_policies = [
        {"rule": "ALLOW", "source": "10.0.1.5", "target": "10.0.1.200", "desc": "Mandatory Auth Heartbeat"}
    ]
    return network_flows, inventory, security_policies

def build_scenario(difficulty="hard"):
    os.makedirs("data", exist_ok=True)
    servers = []
    
    gnc_spike=[]
    gnc_spike.extend(generate_cpu_logs(30,server_type="spike"))
    servers.append({
        "server_id": "db-master-prod",
        "role": "Primary Database",
        "monthly_cost": 2500.00,
        "cpu_30d_avg": 85.5,
        "network_egress_30d": gnc_spike[1],
        "cpu_logs": gnc_spike[0],
        "tags": ["prod", "database", "critical"]
    })
    
    gnc_spike2=[]
    gnc_spike2.extend(generate_cpu_logs(30,server_type="spike"))
    servers.append({
        "server_id": "api-gateway-01",
        "role": "Web API",
        "monthly_cost": 800.00,
        "cpu_30d_avg": 65.2,
        "network_egress_30d": gnc_spike2[1],
        "cpu_logs": gnc_spike2[0],
        "tags": ["prod", "web"]
    })

    gnc_std=[]
    gnc_std.extend(generate_cpu_logs(30,server_type="standard"))
    for i in range(1, 5):
        servers.append({
            "server_id": f"worker-node-0{i}",
            "role": "Background Async Processing",
            "monthly_cost": 300.00,
            "cpu_30d_avg": 35.0,
            "network_egress_30d": gnc_std[1],
            "cpu_logs": gnc_std[0],
            "tags": ["prod", "worker"]
        })

    gnc_easy_win=[]
    gnc_easy_win.extend(generate_cpu_logs(30,server_type="easy_win"))
    servers.append({
        "server_id": "dev-sandbox-old",
        "role": "Developer Test Box",
        "monthly_cost": 150.00,
        "cpu_30d_avg": 0.5,
        "network_egress_30d": gnc_easy_win[1],
        "cpu_logs": gnc_easy_win[0],
        "tags": ["dev", "abandoned"]
    })
    
    gnc_easy_win2=[]
    gnc_easy_win2.extend(generate_cpu_logs(30,server_type="easy_win"))
    servers.append({
        "server_id": "core-payment-gateway-v2",
        "role": "Payment Gateway",
        "monthly_cost": 2000.00,
        "cpu_30d_avg": 0.8,
        "network_egress_30d": gnc_easy_win2[1],
        "cpu_logs": gnc_easy_win2[0],
        "tags": ["prod", "payment"]
    })

    gnc_trap=[]
    gnc_trap.extend(generate_cpu_logs(30,server_type="trap"))
    servers.append({
        "server_id": "cron-log-rotator-tmp",
        "role": "Unknown/Legacy",
        "monthly_cost": 1800.00,
        "cpu_30d_avg": 1.2, 
        "network_egress_30d": gnc_trap[1],
        "cpu_logs": gnc_trap[0],
        "tags": ["prod", "legacy"]
    })

    gnc_trap2=[]
    gnc_trap2.extend(generate_cpu_logs(30,server_type="trap"))
    servers.append({
        "server_id": "payout-bill-serv",
        "role": "Unknown/Legacy",
        "monthly_cost": 1000.00,
        "cpu_30d_avg": 0.4, 
        "network_egress_30d": gnc_trap2[1],
        "cpu_logs": gnc_trap2[0],
        "tags": ["prod", "database", "critical"]
    })

    dependency_graph = {
        "dev-sandbox-old": {"is_critical": False, "supports": [], "failure_penalty_multiplier": 1.0},
        "core-payment-gateway-v2": {"is_critical": False, "supports": [], "failure_penalty_multiplier": 1.0}
    }

    network_flows, inventory, security_policies = generate_fragmented_metadata()

    # --- THE DIFFICULTY TIER LOGIC ---
    if difficulty == "easy":
        # No traps. Everything that looks safe to kill IS safe to kill.
        dependency_graph["cron-log-rotator-tmp"] = {"is_critical": False, "supports": [], "failure_penalty_multiplier": 1.0}
        dependency_graph["payout-bill-serv"] = {"is_critical": False, "supports": [], "failure_penalty_multiplier": 1.0}
        max_savings = 150.0 + 2000.0 + 1800.0 + 1000.0

    elif difficulty == "medium":
        # Trap is active, but blatantly obvious in standard metadata.
        dependency_graph["cron-log-rotator-tmp"] = {"is_critical": True, "supports": ["db-master-prod", "api-gateway-01"], "failure_penalty_multiplier": 0.0}
        dependency_graph["payout-bill-serv"] = {"is_critical": True, "supports": ["db-master-prod", "api-gateway-01"], "failure_penalty_multiplier": 0.0}
        inventory["WARNING_CRON_ROTATOR"] = "DO NOT KILL 10.0.1.200 - CRITICAL HEARTBEAT"
        inventory["WARNING_PAYOUT_SERV"] = "DO NOT KILL payout-bill-serv - CRITICAL DATABASE DEPENDENCY"
        max_savings = 150.0 + 2000.0 

    else: # hard
        # Trap is active and hidden. Only discoverable via network flows/security policies.
        dependency_graph["cron-log-rotator-tmp"] = {"is_critical": True, "supports": ["db-master-prod", "api-gateway-01"], "failure_penalty_multiplier": 0.0}
        dependency_graph["payout-bill-serv"] = {"is_critical": True, "supports": ["db-master-prod", "api-gateway-01"], "failure_penalty_multiplier": 0.0}
        max_savings = 150.0 + 2000.0 

    total_cost = sum(s["monthly_cost"] for s in servers)

    environment_state = {
        "metadata": {
            "scenario": difficulty,
            "starting_monthly_bill": total_cost,
            "starting_uptime_percentage": 99.99,
            "max_possible_savings": max_savings
        },
        "active_servers": servers,
        "secret_dependency_graph": dependency_graph,
        "fragmented_metadata": {
            "network_flows": network_flows,
            "inventory": inventory,
            "security_policies": security_policies
        }
    }

    # Save to data/ directory
    with open(f"{difficulty}.json", "w") as f:
        json.dump(environment_state, f, indent=4)
        
    print(f"✅ {difficulty}.json generated in data/ folder! Max Savings Target: ${max_savings}")

if __name__ == "__main__":
    # Generate all three tasks for the hackathon
    build_scenario("easy")
    build_scenario("medium")
    build_scenario("hard")