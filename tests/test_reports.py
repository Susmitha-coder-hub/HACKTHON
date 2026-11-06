import json
import math
import os
import re
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANDBOX_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")


def test_01_docker_compose_and_dockerfile():
    compose_path = os.path.join(ROOT_DIR, "docker-compose.yml")
    dockerfile_path = os.path.join(ROOT_DIR, "Dockerfile")
    seeds_path = os.path.join(ROOT_DIR, "seeds", "01_runs.sql")

    assert os.path.exists(compose_path), "docker-compose.yml must exist"
    assert os.path.exists(dockerfile_path), "Dockerfile must exist"
    assert os.path.exists(seeds_path), "seeds/01_runs.sql must exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_text = f.read()

    # Check services api and ledger
    assert "api:" in compose_text, "api service missing in docker-compose.yml"
    assert "ledger:" in compose_text, "ledger service missing in docker-compose.yml"

    # Check healthchecks and parameters
    assert "healthcheck:" in compose_text
    assert "pg_isready" in compose_text
    assert "http://localhost:8080/health" in compose_text or "http://api:8080/health" in compose_text or "/health" in compose_text
    for param in ["interval", "timeout", "retries", "start_period"]:
        assert param in compose_text, f"{param} missing from healthchecks in docker-compose.yml"

    # Check seeds mount
    assert "./seeds" in compose_text or "seeds:" in compose_text, "seeds volume mount missing in ledger service"

    # Check seed SQL
    with open(seeds_path, "r", encoding="utf-8") as f:
        seed_sql = f.read()
    assert "sbx-seeddemo1" in seed_sql
    assert "deleted" in seed_sql
    assert "celesto_sandbox" in seed_sql


def test_02_env_example_and_no_live_env():
    env_example_path = os.path.join(ROOT_DIR, ".env.example")
    env_live_path = os.path.join(ROOT_DIR, ".env")

    assert os.path.exists(env_example_path), ".env.example must exist"
    assert not os.path.exists(env_live_path), ".env must NOT be present in root submission"

    with open(env_example_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_keys = [
        "CELESTO_PROVIDER",
        "CELESTO_API_KEY",
        "LLM_API_KEY",
        "LLM_MODEL",
        "DATABASE_URL",
        "API_PORT",
    ]
    for key in required_keys:
        assert f"{key}=" in content, f"Key {key} missing from .env.example"


def test_03_problem_statement():
    problem_path = os.path.join(ROOT_DIR, "reports", "problem.json")
    assert os.path.exists(problem_path), "reports/problem.json must exist"

    with open(problem_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for k in ["who", "agent_work", "proof_output", "idea_source"]:
        assert k in data, f"Key {k} missing from problem.json"

    assert data["idea_source"] in ("idea_bank", "original")
    assert len(data["who"]) >= 40, f"who must be at least 40 characters (got {len(data['who'])})"
    assert len(data["agent_work"]) >= 40, f"agent_work must be at least 40 characters (got {len(data['agent_work'])})"
    assert len(data["proof_output"]) >= 20, f"proof_output must be at least 20 characters (got {len(data['proof_output'])})"


def test_04_command_audit_log():
    log_path = os.path.join(ROOT_DIR, "logs", "commands.jsonl")
    assert os.path.exists(log_path), "logs/commands.jsonl must exist"

    lines = []
    with open(log_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            entry = json.loads(line_str)
            lines.append(entry)

            assert "ts" in entry, f"Missing ts on line {idx}"
            assert "sandbox_name" in entry, f"Missing sandbox_name on line {idx}"
            assert "command" in entry and entry["command"], f"Empty or missing command on line {idx}"
            assert entry["decision"] in ("allow", "block"), f"Invalid decision on line {idx}"
            assert entry["execution_target"] == "celesto_sandbox", f"execution_target must be exactly celesto_sandbox on line {idx}"
            assert SANDBOX_REGEX.match(entry["sandbox_name"]), f"Invalid sandbox_name regex on line {idx}: {entry['sandbox_name']}"

    assert len(lines) >= 1, "logs/commands.jsonl must have at least one line"


def test_05_capabilities():
    cap_path = os.path.join(ROOT_DIR, "reports", "capabilities.json")
    assert os.path.exists(cap_path), "reports/capabilities.json must exist"

    with open(cap_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    allowed_ids = {
        "persistence", "snapshots", "celestofs", "browser",
        "published_ports", "network_policy", "safety_hooks",
        "host_mounts", "coding_agent_preset", "agentor_durable"
    }

    assert "capabilities" in data
    caps = data["capabilities"]
    assert len(caps) >= 2, "Must contain at least 2 capabilities"

    seen_ids = set()
    for cap in caps:
        cap_id = cap["id"]
        assert cap_id in allowed_ids, f"Disallowed capability id: {cap_id}"
        assert cap_id not in seen_ids, f"Duplicate capability id: {cap_id}"
        seen_ids.add(cap_id)

        assert len(cap["why"]) >= 80, f"why must be at least 80 chars for {cap_id}"
        ev_path = os.path.join(ROOT_DIR, cap["evidence_path"])
        assert os.path.exists(ev_path), f"evidence_path does not exist: {cap['evidence_path']}"


def test_06_lifecycle():
    life_path = os.path.join(ROOT_DIR, "reports", "lifecycle.json")
    assert os.path.exists(life_path), "reports/lifecycle.json must exist"

    with open(life_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("cleanup_on_success") is True
    assert data.get("cleanup_on_failure") is True
    assert data.get("cleanup_on_interrupt") is True

    names = data.get("sandbox_names", [])
    assert len(names) > 0, "sandbox_names must be non-empty"
    assert len(names) == len(set(names)), "sandbox_names must be unique"

    # Read commands and reliability to check name occurrence
    commands_log = os.path.join(ROOT_DIR, "logs", "commands.jsonl")
    rel_path = os.path.join(ROOT_DIR, "reports", "reliability.json")

    known_names = set()
    if os.path.exists(commands_log):
        with open(commands_log, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    known_names.add(json.loads(line)["sandbox_name"])

    if os.path.exists(rel_path):
        with open(rel_path, "r", encoding="utf-8") as f:
            rdata = json.load(f)
            for r in rdata.get("runs", []):
                known_names.add(r["sandbox_name"])

    for name in names:
        assert SANDBOX_REGEX.match(name), f"Sandbox name '{name}' does not match regex"
        assert name in known_names, f"Sandbox name '{name}' does not appear in commands.jsonl or reliability.json"


def test_07_reliability_eval():
    rel_path = os.path.join(ROOT_DIR, "reports", "reliability.json")
    assert os.path.exists(rel_path), "reports/reliability.json must exist"

    with open(rel_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    runs = data.get("runs", [])
    assert data["run_count"] >= 20, "run_count must be at least 20"
    assert len(runs) == data["run_count"], "run_count must match len(runs)"

    names = set()
    for run in runs:
        s_name = run["sandbox_name"]
        assert SANDBOX_REGEX.match(s_name), f"Invalid sandbox_name: {s_name}"
        assert s_name not in names, f"Duplicate sandbox name: {s_name}"
        names.add(s_name)
        assert run["fresh"] is True
        assert isinstance(run["success"], bool)
        assert run["wall_clock_s"] >= 0
        assert run["boot_to_ready_s"] >= 0
        assert run["cost_usd"] >= 0

    # Verification of arithmetic
    expected_success_rate = sum(1 for r in runs if r["success"]) / len(runs)
    assert abs(data["success_rate"] - expected_success_rate) <= 0.001

    # Median wall_clock_s
    sorted_wall = sorted(r["wall_clock_s"] for r in runs)
    n = len(sorted_wall)
    if n % 2 == 1:
        expected_median_wall = sorted_wall[n // 2]
    else:
        expected_median_wall = (sorted_wall[n // 2 - 1] + sorted_wall[n // 2]) / 2.0
    assert abs(data["median_wall_clock_s"] - expected_median_wall) <= 0.001

    # P90 wall_clock_s
    p90_idx = math.ceil(0.90 * n) - 1
    expected_p90 = sorted_wall[p90_idx]
    assert abs(data["p90_wall_clock_s"] - expected_p90) <= 0.001

    # Median boot_to_ready_s
    sorted_boot = sorted(r["boot_to_ready_s"] for r in runs)
    if n % 2 == 1:
        expected_median_boot = sorted_boot[n // 2]
    else:
        expected_median_boot = (sorted_boot[n // 2 - 1] + sorted_boot[n // 2]) / 2.0
    assert abs(data["median_boot_to_ready_s"] - expected_median_boot) <= 0.001

    # Total cost
    expected_total_cost = sum(r["cost_usd"] for r in runs)
    assert abs(data["total_cost_usd"] - expected_total_cost) <= 0.01

    # Postmortem check
    pm_path = os.path.join(ROOT_DIR, data["postmortem_path"])
    assert os.path.exists(pm_path), "postmortem file does not exist"
    with open(pm_path, "r", encoding="utf-8") as f:
        pm_content = f.read()
    assert len(pm_content) >= 200, "postmortem must be at least 200 characters"


def test_08_containment():
    cont_path = os.path.join(ROOT_DIR, "reports", "containment.json")
    assert os.path.exists(cont_path), "reports/containment.json must exist"

    with open(cont_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["attack"] in ("prompt_injection_exfil", "destructive_command", "suspicious_package")
    assert data["blocked"] is True
    assert data["host_untouched"] is True
    assert len(data.get("evidence_paths", [])) >= 1

    for ep in data["evidence_paths"]:
        full_ep = os.path.join(ROOT_DIR, ep)
        assert os.path.exists(full_ep), f"Evidence path does not exist: {ep}"


def test_09_failure_policy():
    fp_path = os.path.join(ROOT_DIR, "reports", "failure_policy.json")
    assert os.path.exists(fp_path), "reports/failure_policy.json must exist"

    with open(fp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["failed_step"] == 7
    assert data["total_steps"] == 10
    assert data["policy"] in ("resume", "rollback", "fresh")
    assert len(data["rationale"]) >= 200, "Rationale must be at least 200 characters"

    trace_path = os.path.join(ROOT_DIR, data["trace_path"])
    assert os.path.exists(trace_path), f"Trace file does not exist: {data['trace_path']}"

    found_policy_event = False
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("event") == "policy_applied" and entry.get("policy") == data["policy"]:
                found_policy_event = True
                break

    assert found_policy_event, f"Missing policy_applied event with policy '{data['policy']}' in {data['trace_path']}"


def test_10_concurrency():
    conc_path = os.path.join(ROOT_DIR, "reports", "concurrency.json")
    assert os.path.exists(conc_path), "reports/concurrency.json must exist"

    with open(conc_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    assert len(jobs) >= 5, "Must have at least 5 jobs in reports/concurrency.json"

    names = set()
    for job in jobs:
        s_name = job["sandbox_name"]
        assert SANDBOX_REGEX.match(s_name), f"Invalid sandbox_name regex: {s_name}"
        assert s_name not in names, f"Duplicate sandbox_name: {s_name}"
        names.add(s_name)
        assert job.get("started_at"), "started_at must be non-empty"

    assert len(data.get("breakage_notes", "")) >= 40, "breakage_notes must be at least 40 characters"


def test_11_api_endpoints():
    from src.main import app

    client = TestClient(app)

    # 1. GET /health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    # 2. GET /api/runs (includes sbx-seeddemo1)
    res_runs = client.get("/api/runs")
    assert res_runs.status_code == 200
    runs = res_runs.json()
    assert isinstance(runs, list)
    names = [r["sandbox_name"] for r in runs]
    assert "sbx-seeddemo1" in names, "Seed sandbox sbx-seeddemo1 must be present in GET /api/runs"

    # 3. POST /api/runs valid
    valid_payload = {
        "run_id": "run-testverify99",
        "sandbox_name": "sbx-testverify99",
        "problem_id": "prob-test",
        "state": "running",
        "execution_target": "celesto_sandbox",
    }
    res_post = client.post("/api/runs", json=valid_payload)
    assert res_post.status_code == 201
    created = res_post.json()
    assert created["sandbox_name"] == "sbx-testverify99"
    assert created["execution_target"] == "celesto_sandbox"

    # 4. POST /api/runs with invalid execution_target (host)
    bad_target = dict(valid_payload, run_id="run-bad-target", sandbox_name="sbx-badtarget1", execution_target="host")
    res_bad_target = client.post("/api/runs", json=bad_target)
    assert res_bad_target.status_code == 400

    # 5. POST /api/runs with unknown state
    bad_state = dict(valid_payload, run_id="run-bad-state", sandbox_name="sbx-badstate1", state="unknown_state")
    res_bad_state = client.post("/api/runs", json=bad_state)
    assert res_bad_state.status_code == 400

    # 6. POST /api/runs with invalid sandbox_name
    bad_name = dict(valid_payload, run_id="run-bad-name", sandbox_name="bad-name")
    res_bad_name = client.post("/api/runs", json=bad_name)
    assert res_bad_name.status_code == 400


def test_12_readme_phrases():
    readme_path = os.path.join(ROOT_DIR, "README.md")
    assert os.path.exists(readme_path), "README.md must exist"

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_phrases = [
        "Problem statement",
        "How I used Celesto",
        "Eval report",
        "Containment test",
        "State and failure design",
        "Setup",
    ]

    for phrase in required_phrases:
        assert phrase in content, f"Required phrase '{phrase}' missing from README.md"
