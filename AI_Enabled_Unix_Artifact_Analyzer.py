import os
import re
import json
import yaml
import requests
import csv
import time
import fnmatch
import threading
import sys
import itertools
from pathlib import Path


OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "deepseek-r1:8b"
SKILLS_DIR = "./skills"


def load_skills():
    """Parses all skill files in the directory and returns their frontmatter and markdown body."""
    loaded_skills = []
    if not os.path.exists(SKILLS_DIR):
        print(f"[!] Skills directory '{SKILLS_DIR}' not found.")

        return loaded_skills

    for filename in os.listdir(SKILLS_DIR):
        if filename.endswith(".md"):
            print(filename)
            filepath = os.path.join(SKILLS_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
                if match:
                    frontmatter_raw = match.group(1)
                    body = match.group(2)
                    try:
                        metadata = yaml.safe_load(frontmatter_raw)
                        loaded_skills.append({"metadata": metadata, "instructions": body})
                    except yaml.YAMLError as e:
                        print(f"[-] Error parsing YAML in {filename}: {e}")
    return loaded_skills


def find_skill_for_file(filename, available_skills):
    """
    Finds the best matching skill for a given filename.
    It prioritizes a specific glob match over a default skill.
    """
    specific_match = None
    default_skill = None

    for skill in available_skills:
        meta = skill.get("metadata", {})

        if not meta:
            continue

        # Check for a specific filename glob match
        glob_pattern = meta.get("filename_glob")

        if glob_pattern and fnmatch.fnmatch(filename, glob_pattern):
            specific_match = skill
            break  # Found the best possible match, no need to look further

        # Separately, identify the default skill
        elif meta.get("is_default"):
            default_skill = skill

    # Return the specific match if found, otherwise return the default skill
    return specific_match if specific_match else default_skill


def analyze_with_ollama(artefact_type, artefact, playbook_instructions):
    """Sends the log data and the extracted skill playbook to the local Ollama instance."""
    payload = {
        "model": OLLAMA_MODEL,
        "keep_alive": "30m",
        "messages": [
            {
                "role": "system",
                "content": f"You are a local security operations assistant. Follow this playbook precisely:\n\n{playbook_instructions}"
            },
            {
                "role": "user",
                "content": f"Analyze the content of {artefact_type} :\n\n{json.dumps(artefact, indent=2)}"
            }
        ],
        "stream": True,
        "options": {
            "temperature": 0,
            "num_ctx": 4000,
        }
    }
    try:
        with requests.post(OLLAMA_URL, json=payload, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    try:
                        json_response = json.loads(line.decode('utf-8'))
                        if 'message' in json_response and 'content' in json_response['message']:
                            yield json_response['message']['content']
                    except json.JSONDecodeError:
                        print(f"\n[!] Warning: Could not decode JSON from line: {line.decode('utf-8')}\n")
    except requests.exceptions.RequestException as e:
        yield f"Error contacting Ollama: {e}"


def process_all_folders(root_folder_path, skills, output_csv_path="analysis_results.csv"):
    """
    Reads all files recursively within a given root directory, finds a matching skill for each,
    and writes the analysis results to a CSV.
    """
    root_dir = Path(root_folder_path)
    total_analysis_time = 0

    if not root_dir.is_dir():
        print(f"Error: The root folder '{root_folder_path}' does not exist.")
        return

    with open(output_csv_path, mode='w', newline='', encoding='utf-8') as csv_file:
        fieldnames = ['Folder', 'File Path', 'Skill Used', 'Analysis Time (s)', 'Analysis Result']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        print(f"\n--- Recursively reading all contents of: {root_dir.name} ---")

        for item in root_dir.rglob('*'):
            if item.is_file():
                relative_path = item.relative_to(root_dir)
                folder_name = relative_path.parts[0] if len(relative_path.parts) > 1 else root_dir.name

                # Find the right skill for this specific file
                matching_skill = find_skill_for_file(item.name, skills)

                if not matching_skill:
                    print(f"Warning: No matching skill found for {relative_path}, and no default skill is defined. Skipping.")
                    writer.writerow({'Folder': folder_name, 'File Path': relative_path, 'Skill Used': 'None', 'Analysis Time (s)': 0, 'Analysis Result': 'Skipped: No matching skill found'})
                    continue

                skill_name = matching_skill.get("metadata", {}).get("skill_name", "Unknown Skill")
                print(f"\nProcessing File: {relative_path} (using skill: '{skill_name}')")
                
                content = ""
                try:
                    with open(item, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    print(f"Warning: Could not decode {relative_path} as UTF-8. Extracting strings from binary.")
                    try:
                        with open(item, 'rb') as f:
                            content = "\n".join(s.decode('utf-8', 'ignore') for s in re.findall(b"[\x20-\x7E]{4,}", f.read()))
                    except Exception as e:
                        writer.writerow({'Folder': folder_name, 'File Path': relative_path, 'Skill Used': skill_name, 'Analysis Time (s)': 0, 'Analysis Result': f'Error: Could not read file: {e}'})
                        continue
                except Exception as e:
                    writer.writerow({'Folder': folder_name, 'File Path': relative_path, 'Skill Used': skill_name, 'Analysis Time (s)': 0, 'Analysis Result': f'Error: {str(e)}'})
                    continue

                if not content:
                    writer.writerow({'Folder': folder_name, 'File Path': relative_path, 'Skill Used': skill_name, 'Analysis Time (s)': 0, 'Analysis Result': 'Warning: No content extracted'})
                    continue

                start_time = time.monotonic()
                
                print(f"--- Analysis for {relative_path} ---")
                
                stop_spinner = threading.Event()
                def spinner_task():
                    spinner = itertools.cycle(['-', '\\', '|', '/'])
                    while not stop_spinner.is_set():
                        sys.stdout.write(f'\r[*] LLM is processing context and thinking... {next(spinner)}')
                        sys.stdout.flush()
                        time.sleep(0.1)
                    sys.stdout.write('\r' + ' ' * 60 + '\r')
                    sys.stdout.flush()

                spinner_thread = threading.Thread(target=spinner_task)
                spinner_thread.start()

                analysis_result_full = ""
                spinner_stopped = False
                
                try:
                    for chunk in analyze_with_ollama(str(relative_path), content, matching_skill["instructions"]):
                        analysis_result_full += chunk
                        
                        # Stop spinner only when we get the first piece of actual content
                        if not spinner_stopped and chunk.strip():
                            stop_spinner.set()
                            spinner_thread.join()
                            spinner_stopped = True
                            # Now that the spinner is gone, print the accumulated content that we held back
                            print(analysis_result_full, end='', flush=True)
                        elif spinner_stopped:
                            # For subsequent chunks, just print them
                            print(chunk, end='', flush=True)

                finally:
                    # Ensure spinner stops if an error occurs or stream ends before content
                    if not stop_spinner.is_set():
                        stop_spinner.set()
                        spinner_thread.join()
                
                end_time = time.monotonic()
                analysis_time = end_time - start_time
                total_analysis_time += analysis_time

                print(f"\n--- Analysis for {relative_path} completed (took {analysis_time:.2f}s) ---\n\n")
                
                writer.writerow({
                    'Folder': folder_name,
                    'File Path': relative_path,
                    'Skill Used': skill_name,
                    'Analysis Time (s)': f"{analysis_time:.2f}",
                    'Analysis Result': analysis_result_full.strip()
                })

    print(f"\n[*] Analysis complete. Total analysis time: {total_analysis_time:.2f}s. Results saved to '{output_csv_path}'.")


# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    my_root_folder = ".\\UAC_Artefact_scoped"

    print("[*] Loading Heuristic Skills...")
    all_skills = load_skills()
    print(f"[+] Loaded {len(all_skills)} skill(s).")

    process_all_folders(my_root_folder, all_skills)