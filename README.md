# AI-Assisted Unix Artifact Analysis

Leveraging Local LLMs for Offline, Cybersecurity Triage[cite: 2].

---

## ⚖️ The Impetus

* **Triage Consistency:** Manual analysis of voluminous Unix artifacts collected via UAC can be tedious and prone to human error, ultimately leading to inconsistent triage[cite: 2].
* **Privacy & Compliance:** Sending sensitive system artifacts to cloud-based AI poses data privacy risks[cite: 2]. This POC mitigates that by keeping data entirely on local hardware[cite: 2].

---

## 💻 POC Hardware Specifications

This Proof of Concept was evaluated on a local machine configured with the following hardware specs[cite: 2]:

* **Processor:** Intel(R) Core(TM) Ultra 7 155H (1.40 GHz)[cite: 2]
* **RAM:** 32.0 GB (31.6 GB usable)[cite: 2]
* **GPU:** NVIDIA GeForce RTX 4060 Laptop GPU (8 GB VRAM)[cite: 2]

---

## ⚙️ Consumer HW Optimization

To run efficiently on consumer-grade local machinery, the pipeline employs[cite: 2]:

* `deepseek-r1:8b`: A lightweight model selected to avoid massive hardware overhead[cite: 2].
* `num_ctx: 4000`: Context windows are managed specifically to ensure execution stays entirely inside the 8GB GPU VRAM limit[cite: 2].
* `keep_alive: 30m`: Eliminates model reload penalties between execution runs for massive speed gains[cite: 2].

---

## 🔄 Orchestration & Workflow

The Python orchestration script automatically maps and runs forensic telemetry against specific digital forensics skill markdown files[cite: 2]:

1. **Ingestion:** Recursively scans artifact folders, handling both plain-text logs (`.txt`) and binary string extraction (e.g., `/etc/profile.d`)[cite: 2].
2. **Skill Match:** Heuristically matches the file name to a specific, predefined "skill" file (`.md`)[cite: 2].
3. **AI Analysis:** Combines the file content (artifacts) and the skill instructions, sending it to the locally running LLM[cite: 2].
4. **Reporting:** Logs the file path, skill used, processing time, and the AI's analysis into a centralized CSV matrix[cite: 2].

---

## 🔬 Live Analysis Triage Examples

### 1. Local LLM Output: RPM Modification Analyzer
* **Target File:** `packages\rpm_-V._a.txt` (using skill: `'RPM Modification Analyzer'`)[cite: 2]

```text
[+] Loaded 3 skill(s).

--- Recursively reading all contents of: UAC_Artifact_scoped ---

Processing File: packages\rpm_-V._a.txt (using skill: 'RPM Modification Analyzer')
--- Analysis for packages\rpm_-V._a.txt ---

#### 1. Verdict & Summary
* **Classification:** Malicious
* **Why:** The analysis identified multiple system binaries in critical paths (e.g., `/usr/bin/teams`, `/usr/bin/python3.9`, `/usr/sbin/nologin`, `/usr/sbin/cupsd`) with modified hash (`5`) or size (`S`), which strongly indicates potential backdoors or malicious replacements. These changes fall under High Priority rules, suggesting a compromise. Additionally, critical configuration files like `/etc/sudoers` and `/etc/ssh/sshd_config` show unauthorized modifications, further supporting the malicious classification.

#### 2. Incident Response
* **Evidence Details:**
  - "S.5....T.   /usr/bin/teams"
  - ".......P   /usr/bin/python3.9"
  - "S.5....T.   /usr/sbin/nologin"
  - "S.5....T.   /usr/sbin/cupsd"
  - "S.5....T. c /etc/sudoers"
  - "S.5....T. c /etc/ssh/sshd_config"
  - "S.5....T. c /etc/crontab"

* **Recommended Next Steps:**
1. Isolate the host by disconnecting from the network and restricting access to prevent further spread or data exfiltration.
2. Re-verify binary integrity using an out-of-band method, such as downloading trusted RPM checksums from a secure repository or performing a memory dump for forensic analysis.
3. Reinstall affected RPM packages using `yum reinstall --downloadonly <package-name>` to obtain clean versions, or consider a full system rebuild if the compromise is extensive. Collect memory and disk images for deeper analysis.
