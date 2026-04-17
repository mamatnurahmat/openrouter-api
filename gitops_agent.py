import os
import subprocess
from textwrap import dedent
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# Load environment variables from .env file
load_dotenv()

# 1. Konfigurasi OpenRouter LLM (CrewAI 1.x syntax)
# Pastikan OPENROUTER_API_KEY sudah diset di environment variables (.env)
llm = LLM(
    model="openrouter/elephant-alpha", # Sesuaikan model OpenRouter yang ingin dipakai
    api_key=os.environ.get("OPENROUTER_API_KEY", "your-openrouter-key"),
    base_url="https://openrouter.ai/api/v1"
)

# 2. Definisi Custom Tools dengan Error Handler dan parameter work_dir

def run_cmd(cmd_list, work_dir="."):
    """Helper function to run shell commands with error handling."""
    try:
        result = subprocess.run(
            cmd_list, 
            cwd=work_dir, 
            check=True, 
            capture_output=True, 
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed with exit code {e.returncode}.\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}"
        return error_msg
    except Exception as e:
        return f"Unexpected error: {str(e)}"

@tool("Git Clone Tool")
def git_clone(repo_url: str, branch: str, dest_dir: str) -> str:
    """Clones a git repository to a specific directory and checks out a branch. Inputs: repo_url (e.g. Qoin-Digital-Indonesia/gitops-k8s), branch, dest_dir."""
    # Menggunakan gh repo clone untuk mendukung otentikasi bawaan gh (SSH/HTTPS)
    cmd = ["gh", "repo", "clone", repo_url, dest_dir, "--", "-b", branch]
    output = run_cmd(cmd)
    if "Command failed" in output or "Unexpected error" in output:
        return output
    return f"Successfully cloned {repo_url} branch {branch} to {dest_dir}"

@tool("Create Branch Tool")
def create_branch(branch_name: str, work_dir: str) -> str:
    """Creates a new git branch and checks it out. Inputs: branch_name, work_dir (directory of the repo)."""
    return run_cmd(["git", "checkout", "-b", branch_name], work_dir)

@tool("Update YAML Tool")
def update_yaml(file_path: str, update_query: str, work_dir: str) -> str:
    """Updates a YAML file using yq. Inputs: file_path (relative to work_dir), yq update_query, work_dir.
    Example query: '.spec.template.spec.containers[0].image = "my-app:v2.0.0"'
    """
    try:
        # Menggunakan shell=True untuk kemudahan parsing single quote di yq query
        cmd = f"yq -i '{update_query}' {file_path}"
        result = subprocess.run(cmd, shell=True, cwd=work_dir, check=True, capture_output=True, text=True)
        return f"Successfully updated {file_path} with query: {update_query}"
    except subprocess.CalledProcessError as e:
        return f"Error updating YAML with yq: {e.stderr}"

@tool("Helm Tool")
def helm_command(helm_args: str, work_dir: str) -> str:
    """Executes a helm command (e.g. 'lint chart/', 'template chart/'). Inputs: helm_args (the arguments after 'helm'), work_dir.
    Example helm_args: 'lint ./my-chart'
    """
    try:
        cmd = f"helm {helm_args}"
        result = subprocess.run(cmd, shell=True, cwd=work_dir, check=True, capture_output=True, text=True)
        return f"Helm output:\n{result.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Helm command failed. Error:\n{e.stderr}"

@tool("Commit and Push Tool")
def commit_and_push(commit_message: str, branch_name: str, work_dir: str) -> str:
    """Commits all changes and pushes them to the remote repository. Inputs: commit_message, branch_name, work_dir."""
    add_out = run_cmd(["git", "add", "."], work_dir)
    if "Command failed" in add_out: return add_out
    
    commit_out = run_cmd(["git", "commit", "-m", commit_message], work_dir)
    if "Command failed" in commit_out: return commit_out
    
    push_out = run_cmd(["git", "push", "-u", "origin", branch_name], work_dir)
    if "Command failed" in push_out: return push_out
    
    return "Successfully committed and pushed changes."

@tool("Create Pull Request Tool")
def create_pull_request(title: str, body: str, work_dir: str) -> str:
    """Creates a pull request using the GitHub CLI (gh). Inputs: PR title, PR body, work_dir."""
    # Ensure GitHub CLI can run without prompt issues
    return run_cmd(["gh", "pr", "create", "--title", title, "--body", body], work_dir)

@tool("Send Notification Tool")
def send_notification(message: str) -> str:
    """Sends a notification using ntfy.sh. Input is just the message string. The topic is handled internally."""
    try:
        topic = os.environ.get("NTFY_TOPIC", "gitops_default_alerts")
        result = subprocess.run(["curl", "-d", message, f"ntfy.sh/{topic}"], check=True, capture_output=True, text=True)
        return "Successfully sent notification."
    except subprocess.CalledProcessError as e:
        return f"Error sending notification: {e.stderr}"

# 3. Definisi Agent
gitops_manager = Agent(
    role='GitOps Manager',
    goal='Mengelola konfigurasi deployment, validasi Helm, pembuatan branch, update YAML, commit, push, PR, dan mengirim notifikasi dengan aman.',
    backstory=dedent('''\
        Kamu adalah seorang Senior DevOps dan GitOps Engineer. 
        Kamu sangat teliti dan selalu mengecek error. Jika ada perintah yang gagal, kamu akan menganalisanya
        dan mencoba memperbaiki atau melaporkan error tersebut.
        Keahlianmu: git, GitHub CLI (gh), yq (YAML), helm, dan ntfy.sh.
    '''),
    verbose=True,
    allow_delegation=False,
    tools=[git_clone, create_branch, update_yaml, helm_command, commit_and_push, create_pull_request, send_notification],
    llm=llm
)

# 4. Definisi Task dengan Flow Qoin-Digital-Indonesia Update Image
gitops_task = Task(
    description=dedent('''\
        Jalankan flow GitOps berikut dengan hati-hati dan perhatikan output dari setiap eksekusi tool. Jika terjadi error, catat errornya.
        
        Skenario: Update versi image pada file deployment k8s untuk Qoin Digital.
        
        Langkah-langkah:
        1. **Clone Repo**: Clone repository "Qoin-Digital-Indonesia/gitops-k8s" menggunakan GitHub CLI (gh) dengan branch "develop-qoin" ke folder "qoin-gitops-workdir". Pastikan menggunakan format nama repo pendek agar gh cli menggunakan koneksi SSH/HTTPS sesuai konfigurasi.
        2. **Create Branch**: Di dalam folder "qoin-gitops-workdir", buat branch baru bernama 'feat/update-be-sample-manager-image'.
        3. **Update YAML**: Di dalam folder "qoin-gitops-workdir", gunakan yq untuk mengubah file "develop-devops/devops-be-sample-manager_deployment.yaml".
           Ubah tag image dari container pertama (biasanya di path '.spec.template.spec.containers[0].image') menjadi "qoin/be-sample-manager:v1.2.3".
           (Sesuaikan path file dan query sesuai struktur yaml yang ada jika perlu)
        4. **Validasi (Opsional/Jika ada Helm)**: Jika di dalam folder tersebut terdapat chart Helm, gunakan tool Helm untuk melakukan linting (contoh: `helm lint .`). Jika bukan chart helm, lewati langkah ini.
        5. **Commit & Push**: Lakukan commit perubahan dengan pesan "feat: update be-sample-manager image to v1.2.3" lalu push branch tersebut ke origin.
        6. **Pull Request**: Buat Pull Request dengan judul "Update Image be-sample-manager v1.2.3" dan deskripsi "PR otomatis dibuat oleh GitOps Manager AI".
        7. **Notifikasi**: Kirim notifikasi via ntfy.sh berisi pesan "PR update be-sample-manager telah dibuat di repo gitops-k8s branch develop-qoin".
    '''),
    expected_output='Laporan mendetail langkah demi langkah. Jika ada langkah yang gagal (misal tidak ada akses repo), jelaskan kegagalannya beserta log error yang dikembalikan oleh tool.',
    agent=gitops_manager
)

# 5. Inisialisasi Crew
gitops_crew = Crew(
    agents=[gitops_manager],
    tasks=[gitops_task],
    process=Process.sequential
)

if __name__ == "__main__":
    print("Memulai GitOps Manager AI Agent...")
    # Pastikan Anda sudah login GitHub CLI (gh auth login) dan memiliki akses ke repo tujuan
    # Eksekusi agent
    result = gitops_crew.kickoff()
    print("######################")
    print("HASIL:")
    print(result)
